from __future__ import annotations

import asyncio
import json as _json
from typing import Any, cast
from uuid import UUID

import structlog
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from packages.agent.orchestrator.clarification import (
    build_clarification_event,
    clarification_exhausted,
    needs_clarification,
)
from packages.agent.orchestrator.models import (
    AgentRoute,
    SessionGoal,
    SessionIntent,
    SessionResponse,
    SessionUserQuery,
)
from packages.agent.orchestrator.parsing import _iso_now, _json_obj, json_safe
from packages.agent.orchestrator.prompts import INTENT_SYSTEM, ROUTER_SYSTEM
from packages.agent.orchestrator.routing import validate_route
from packages.agent.orchestrator.runtime import (
    _run_agents_in_order,
    _synthesize_response,
    run_dag_execution,
    run_direct_chat,
    run_planned_execution,
)
from packages.persistence.sessions_repo import DecisionSessionRepository

_log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# OrchestratorState
# ---------------------------------------------------------------------------


class OrchestratorState(TypedDict):
    session_id: str
    query: SessionUserQuery
    intent: SessionIntent | None
    route: AgentRoute | None
    result: SessionResponse | None
    clarification_round: int
    error: str | None


# ---------------------------------------------------------------------------
# SessionOrchestrator
# ---------------------------------------------------------------------------


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
        self._graph: Any = None  # lazily initialised by _get_graph()

    async def _push(self, event: dict[str, Any], sse_queue: Any = None) -> None:
        q = sse_queue if sse_queue is not None else self._sse_queue
        safe = json_safe(event)
        if q is not None:
            await q.put(safe)
        if sse_queue is None and self._event_persister is not None:
            await self._event_persister(safe)

    def _query_text(self, query: SessionUserQuery) -> str:
        if query.conversation_context:
            return f"[Conversation context: {query.conversation_context}]\n\n{query.text}"
        return query.text

    def _schedule_status_update(self, session_id: UUID | str, status: str) -> None:
        """Fire-and-forget DB status update; logs a warning on failure."""
        sid = str(session_id)

        async def _persist() -> None:
            try:
                await DecisionSessionRepository().update_status(sid, status)
            except Exception as exc:
                _log.warning(
                    "session status update failed",
                    target_status=status,
                    session_id=sid,
                    error=str(exc),
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
                    content=_json.dumps(
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
        validate_route(route)

    # ------------------------------------------------------------------
    # Graph nodes
    # ------------------------------------------------------------------

    async def _node_classify_intent(
        self, state: OrchestratorState, config: RunnableConfig
    ) -> dict[str, Any]:
        session_id = UUID(state["session_id"])
        sse_queue = (config.get("configurable") or {}).get("sse_queue")
        # Use config sse_queue if provided
        original_queue = self._sse_queue
        if sse_queue is not None:
            self._sse_queue = sse_queue
        try:
            intent = await self.classify_intent(state["query"], session_id)
        finally:
            self._sse_queue = original_queue
        return {"intent": intent}

    async def _node_handle_clarification(
        self, state: OrchestratorState, config: RunnableConfig
    ) -> dict[str, Any]:
        """No-op node — routing logic is in the conditional edge."""
        intent = state.get("intent")
        if intent is None:
            return {}
        session_id = UUID(state["session_id"])
        clarification_round: int = state.get("clarification_round", 0)

        sse_queue = (config.get("configurable") or {}).get("sse_queue")

        if needs_clarification(intent.category, intent.goal_text):
            if not clarification_exhausted(clarification_round):
                event = build_clarification_event(session_id, clarification_round + 1)
                if sse_queue is not None:
                    await sse_queue.put(json_safe(event))
                self._schedule_status_update(session_id, "completed")
                result = SessionResponse(
                    mode="direct_chat",
                    reply=event["message"],
                    intent=intent,
                    route=AgentRoute(
                        mode="direct_chat",
                        agents=[],
                        requires_planning=False,
                        requires_dag=False,
                        rationale="clarification",
                    ),
                )
                return {"result": result}
        return {}

    async def _node_select_mode(
        self, state: OrchestratorState, config: RunnableConfig
    ) -> dict[str, Any]:
        session_id = UUID(state["session_id"])
        intent = state["intent"]
        assert intent is not None

        sse_queue = (config.get("configurable") or {}).get("sse_queue")
        original_queue = self._sse_queue
        if sse_queue is not None:
            self._sse_queue = sse_queue
        try:
            route = await self.select_execution_mode(state["query"], intent, session_id)
        finally:
            self._sse_queue = original_queue
        return {"route": route}

    async def _node_run_direct_chat(
        self, state: OrchestratorState, config: RunnableConfig
    ) -> dict[str, Any]:
        session_id = UUID(state["session_id"])
        intent = state["intent"]
        route = state["route"]
        assert intent is not None
        assert route is not None

        sse_queue = (config.get("configurable") or {}).get("sse_queue")
        original_queue = self._sse_queue
        if sse_queue is not None:
            self._sse_queue = sse_queue
        try:
            result = await run_direct_chat(self, session_id, state["query"], intent, route)
            self._schedule_status_update(session_id, "completed")
        finally:
            self._sse_queue = original_queue
        return {"result": result}

    async def _node_run_sequential(
        self, state: OrchestratorState, config: RunnableConfig
    ) -> dict[str, Any]:
        session_id = UUID(state["session_id"])
        intent = state["intent"]
        route = state["route"]
        assert intent is not None
        assert route is not None

        sse_queue = (config.get("configurable") or {}).get("sse_queue")
        original_queue = self._sse_queue
        if sse_queue is not None:
            self._sse_queue = sse_queue
        try:
            results = await _run_agents_in_order(
                self, session_id, state["query"], route.agents, intent
            )
            result = await _synthesize_response(
                self, session_id, state["query"], intent, route, results
            )
        finally:
            self._sse_queue = original_queue
        return {"result": result}

    async def _node_run_planned(
        self, state: OrchestratorState, config: RunnableConfig
    ) -> dict[str, Any]:
        session_id = UUID(state["session_id"])
        intent = state["intent"]
        route = state["route"]
        assert intent is not None
        assert route is not None

        sse_queue = (config.get("configurable") or {}).get("sse_queue")
        original_queue = self._sse_queue
        if sse_queue is not None:
            self._sse_queue = sse_queue
        try:
            result = await run_planned_execution(self, session_id, state["query"], intent, route)
            self._schedule_status_update(session_id, "completed")
        finally:
            self._sse_queue = original_queue
        return {"result": result}

    async def _node_run_dag(
        self, state: OrchestratorState, config: RunnableConfig
    ) -> dict[str, Any]:
        """Bridge node — calls run_dag_execution unchanged; T-068 upgrades the internals."""
        session_id = UUID(state["session_id"])
        intent = state["intent"]
        route = state["route"]
        assert intent is not None
        assert route is not None

        sse_queue = (config.get("configurable") or {}).get("sse_queue")
        original_queue = self._sse_queue
        if sse_queue is not None:
            self._sse_queue = sse_queue
        try:
            result = await run_dag_execution(self, session_id, state["query"], intent, route)
            self._schedule_status_update(session_id, "completed")
        finally:
            self._sse_queue = original_queue
        return {"result": result}

    # ------------------------------------------------------------------
    # Conditional edges
    # ------------------------------------------------------------------

    def _edge_after_clarification(self, state: OrchestratorState) -> str:
        """If a clarification result was set, we end. Otherwise continue to select_mode."""
        if state.get("result") is not None:
            return END
        return "select_mode"

    def _edge_after_select_mode(self, state: OrchestratorState) -> str:
        route = state.get("route")
        if route is None:
            return END
        mode = route.mode
        if mode == "direct_chat":
            return "run_direct_chat"
        if mode in ("single_agent", "sequential_agents"):
            return "run_sequential"
        if mode == "planned_execution":
            return "run_planned"
        if mode == "dag_execution":
            return "run_dag"
        # Unknown mode — end
        return END

    # ------------------------------------------------------------------
    # Graph builder
    # ------------------------------------------------------------------

    def _build_graph(self, checkpointer: Any = None) -> Any:
        sg: StateGraph = StateGraph(OrchestratorState)  # type: ignore[type-arg]

        sg.add_node("classify_intent", self._node_classify_intent)
        sg.add_node("handle_clarification", self._node_handle_clarification)
        sg.add_node("select_mode", self._node_select_mode)
        sg.add_node("run_direct_chat", self._node_run_direct_chat)
        sg.add_node("run_sequential", self._node_run_sequential)
        sg.add_node("run_planned", self._node_run_planned)
        sg.add_node("run_dag", self._node_run_dag)

        sg.add_edge(START, "classify_intent")
        sg.add_edge("classify_intent", "handle_clarification")
        sg.add_conditional_edges(
            "handle_clarification",
            self._edge_after_clarification,
            {
                END: END,
                "select_mode": "select_mode",
            },
        )
        sg.add_conditional_edges(
            "select_mode",
            self._edge_after_select_mode,
            {
                "run_direct_chat": "run_direct_chat",
                "run_sequential": "run_sequential",
                "run_planned": "run_planned",
                "run_dag": "run_dag",
                END: END,
            },
        )
        sg.add_edge("run_direct_chat", END)
        sg.add_edge("run_sequential", END)
        sg.add_edge("run_planned", END)
        sg.add_edge("run_dag", END)

        return sg.compile(checkpointer=checkpointer)

    async def _get_graph(self) -> Any:
        """Return the compiled graph, building it lazily with a checkpointer.

        When DATABASE_URL is set, uses AsyncPostgresSaver backed by an
        AsyncConnectionPool so that checkpoint state persists across HTTP
        requests (required for cross-request HITL resume).

        Falls back to MemorySaver when DATABASE_URL is absent (unit tests,
        CI without DB).

        The compiled graph is cached on ``self._graph`` after the first call.
        """
        if self._graph is not None:
            return self._graph

        import os

        database_url = os.environ.get("DATABASE_URL", "")
        if database_url:
            # Use the async Postgres checkpointer so graph state survives across HTTP requests.
            # psycopg v3 expects plain postgresql:// — strip the SQLAlchemy +asyncpg driver prefix.
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
            from psycopg import AsyncConnection
            from psycopg.rows import dict_row
            from psycopg_pool import AsyncConnectionPool

            psycopg_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
            pool: AsyncConnectionPool[AsyncConnection[dict[str, Any]]] = (
                AsyncConnectionPool(
                    psycopg_url,
                    max_size=5,
                    kwargs={
                        "autocommit": True,
                        "prepare_threshold": 0,
                        "row_factory": dict_row,
                    },
                    open=False,
                )
            )
            await pool.open()
            checkpointer: Any = AsyncPostgresSaver(conn=pool)
        else:
            from langgraph.checkpoint.memory import MemorySaver

            checkpointer = MemorySaver()

        self._graph = self._build_graph(checkpointer=checkpointer)
        return self._graph

    # ------------------------------------------------------------------
    # Public run()
    # ------------------------------------------------------------------

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

        clarification_round: int = query.metadata.get("clarification_round", 0)

        initial_state: OrchestratorState = {
            "session_id": str(session_id),
            "query": query,
            "intent": None,
            "route": None,
            "result": None,
            "clarification_round": clarification_round,
            "error": None,
        }

        config = {
            "configurable": {
                "thread_id": str(session_id),
                "sse_queue": self._sse_queue,
            }
        }

        graph = await self._get_graph()

        try:
            final_state: dict[str, Any] = await graph.ainvoke(initial_state, config=config)
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

        raw_result = final_state.get("result")
        if raw_result is None:
            raise RuntimeError("Orchestrator graph produced no result")
        if not isinstance(raw_result, SessionResponse):
            raise RuntimeError(f"Orchestrator graph returned unexpected type: {type(raw_result)}")
        return raw_result

    async def resume(self, session_id: UUID, approval_id: UUID) -> SessionResponse:
        """Resume graph execution from the last LangGraph checkpoint for this session.

        Passes ``None`` as the input to ``astream`` so LangGraph continues from the
        interrupted node (``wait_for_approval``) rather than re-running from START.
        The ``approval_id`` parameter is kept for API compatibility; the graph already
        holds it in the checkpoint state written by ``prepare_hitl``.
        """
        config: dict[str, Any] = {
            "configurable": {
                "thread_id": str(session_id),
                "sse_queue": self._sse_queue,
            }
        }

        graph = await self._get_graph()

        try:
            result_state: dict[str, Any] = {}
            async for chunk in graph.astream(None, config=config, stream_mode="updates"):
                result_state.update(chunk)
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

        result = result_state.get("result") or result_state.get("run_dag", {}).get("result")
        if result is None:
            raise RuntimeError(f"Graph resume produced no result for session {session_id}")
        return cast(SessionResponse, result)
