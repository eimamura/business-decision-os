from __future__ import annotations

import asyncio
import json
import logging
from typing import Any
from uuid import UUID

from packages.agent.orchestrator.models import (
    AgentRoute,
    SessionGoal,
    SessionIntent,
    SessionResponse,
    SessionUserQuery,
)
from packages.agent.orchestrator.parsing import _iso_now, _json_obj, json_safe
from packages.agent.orchestrator.prompts import INTENT_SYSTEM, ROUTER_SYSTEM
from packages.agent.orchestrator.roles import VALID_AGENT_ROLES
from packages.agent.orchestrator.runtime import (
    _run_agents_in_order,
    _synthesize_response,
    run_dag_execution,
    run_direct_chat,
    run_planned_execution,
)
from packages.persistence.sessions_repo import DecisionSessionRepository

_log = logging.getLogger(__name__)


class SessionOrchestrator:
    def __init__(
        self,
        llm_client: Any,
        tool_registry: Any,
        memory_store: Any,
        sse_queue: Any | None = None,
        event_persister: Any | None = None,
    ) -> None:
        self._llm_client = llm_client
        self._tool_registry = tool_registry
        self._memory_store = memory_store
        self._sse_queue = sse_queue
        self._event_persister = event_persister

    async def _push(self, event: dict[str, Any]) -> None:
        safe = json_safe(event)
        if self._sse_queue is not None:
            await self._sse_queue.put(safe)
        if self._event_persister is not None:
            await self._event_persister(safe)

    def _query_text(self, query: SessionUserQuery) -> str:
        if query.conversation_context:
            return f"[Conversation context: {query.conversation_context}]\n\n{query.text}"
        return query.text

    def _schedule_status_update(self, session_id: UUID, status: str) -> None:
        """Fire-and-forget DB status update; logs a warning on failure."""

        async def _persist() -> None:
            try:
                await DecisionSessionRepository().update_status(str(session_id), status)
            except Exception as exc:
                _log.warning(
                    "session status update to %r failed for %s: %s", status, session_id, exc
                )

        asyncio.create_task(_persist())

    async def classify_intent(self, query: SessionUserQuery, session_id: UUID) -> SessionIntent:
        from packages.agent.llm import LLMMessage
        from packages.persistence.agent_steps_repo import make_step

        step_id = await make_step(str(session_id), "intent_classification")
        response = await self._llm_client.complete(
            messages=[
                LLMMessage(role="system", content=INTENT_SYSTEM),
                LLMMessage(role="user", content=self._query_text(query)),
            ],
            tools=None,
            temperature=0.0,
            max_tokens=512,
            prompt_cache=False,
            specialist_role="orchestrator",
            agent_step_id=step_id,
        )
        intent = SessionIntent(**_json_obj(response.text))
        await self._push({
            "type": "intent_classified",
            "category": intent.category,
            "confidence": intent.confidence,
            "rationale": intent.rationale,
            "goal_text": intent.goal_text,
            "timestamp": _iso_now(),
        })
        return intent

    async def select_execution_mode(
        self, query: SessionUserQuery, intent: SessionIntent, session_id: UUID
    ) -> AgentRoute:
        from packages.agent.llm import LLMMessage
        from packages.persistence.agent_steps_repo import make_step

        step_id = await make_step(str(session_id), "routing")
        response = await self._llm_client.complete(
            messages=[
                LLMMessage(role="system", content=ROUTER_SYSTEM),
                LLMMessage(
                    role="user",
                    content=json.dumps(
                        {
                            "query": self._query_text(query),
                            "intent": intent.model_dump(),
                        }
                    ),
                ),
            ],
            tools=None,
            temperature=0.0,
            max_tokens=512,
            prompt_cache=False,
            specialist_role="orchestrator",
            agent_step_id=step_id,
        )
        route = AgentRoute(**_json_obj(response.text))
        self._validate_route(route)
        await self._push({
            "type": "execution_mode_selected",
            "mode": route.mode,
            "agents": route.agents,
            "requires_planning": route.requires_planning,
            "requires_dag": route.requires_dag,
            "rationale": route.rationale,
            "timestamp": _iso_now(),
        })
        return route

    def _validate_route(self, route: AgentRoute) -> None:
        if route.mode == "direct_chat" and route.agents:
            raise ValueError("direct_chat route must not include agents")
        if route.mode == "single_agent" and len(route.agents) != 1:
            raise ValueError("single_agent route requires exactly one agent")
        if route.mode == "sequential_agents" and len(route.agents) < 1:
            raise ValueError("sequential_agents route requires at least one agent")
        unknown = [agent for agent in route.agents if agent not in VALID_AGENT_ROLES]
        if unknown:
            raise ValueError(f"unknown agent role(s): {', '.join(unknown)}")

    async def run(self, session_id: UUID, query: SessionUserQuery) -> SessionResponse:
        if isinstance(query, SessionGoal):
            query = SessionUserQuery(
                text=query.text,
                weight_override_json=query.weight_override_json,
            )

        self._schedule_status_update(session_id, "active")
        await self._push({
            "type": "query_received",
            "session_id": str(session_id),
            "timestamp": _iso_now(),
        })

        try:
            intent = await self.classify_intent(query, session_id)
            route = await self.select_execution_mode(query, intent, session_id)
            if route.mode == "direct_chat":
                result = await run_direct_chat(self, session_id, query, intent, route)
            elif route.mode == "single_agent":
                results = await _run_agents_in_order(self, session_id, query, route.agents, intent)
                result = await _synthesize_response(self, session_id, query, intent, route, results)
            elif route.mode == "sequential_agents":
                results = await _run_agents_in_order(self, session_id, query, route.agents, intent)
                result = await _synthesize_response(self, session_id, query, intent, route, results)
            elif route.mode == "planned_execution":
                result = await run_planned_execution(self, session_id, query, intent, route)
            elif route.mode == "dag_execution":
                result = await run_dag_execution(self, session_id, query, intent, route)
            else:
                raise ValueError(f"unknown execution mode: {route.mode}")
        except Exception as exc:
            self._schedule_status_update(session_id, "failed")
            await self._push({
                "type": "error",
                "code": "orchestration_failed",
                "message": str(exc),
                "recoverable": False,
                "timestamp": _iso_now(),
            })
            raise
        self._schedule_status_update(session_id, "completed")
        return result

    async def resume(self, session_id: UUID, approval_id: UUID) -> SessionResponse:
        query = SessionUserQuery(
            text="Resume the approved decision.",
            metadata={"approval_id": str(approval_id)},
        )
        return await self.run(session_id, query)
