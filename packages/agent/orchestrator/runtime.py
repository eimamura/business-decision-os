from __future__ import annotations
# ruff: noqa: I001

import asyncio
import logging
import time
from typing import Any, cast
from uuid import UUID, uuid4

from packages.agent.orchestrator.models import (
    AgentRoute,
    SessionIntent,
    SessionResponse,
    SessionUserQuery,
    SpecialistResult,
    SpecialistTask,
)
from datetime import datetime, timezone

from packages.agent.orchestrator.parsing import _iso_now
from packages.agent.orchestrator.roles import (
    CROSS_DOMAIN_AGENT_CLASSES,
    DOMAIN_AGENT_ROLES,
)

logger = logging.getLogger(__name__)


def _default_tools(agent_role: str) -> list[str]:
    from packages.tools.base import _ROLE_TOOL_ALLOWLIST
    return list(_ROLE_TOOL_ALLOWLIST.get(agent_role, []))


def _make_agent(orchestrator: Any, agent_role: str) -> Any:
    if agent_role in CROSS_DOMAIN_AGENT_CLASSES:
        return CROSS_DOMAIN_AGENT_CLASSES[agent_role](
            orchestrator._llm_client, orchestrator._tool_registry, orchestrator._sse_queue
        )
    if agent_role in DOMAIN_AGENT_ROLES:
        from packages.agent.domain import create_domain_agents

        for agent in create_domain_agents(
            orchestrator._llm_client, orchestrator._tool_registry, sse_queue=orchestrator._sse_queue
        ):
            if agent.role == agent_role:
                return agent
    raise ValueError(f"unknown agent role: {agent_role}")


async def _run_agent(
    orchestrator: Any,
    session_id: UUID,
    agent_role: str,
    instruction: str,
    context_payload: dict[str, Any],
    allowed_tools: list[str],
) -> SpecialistResult:
    from packages.persistence.agent_steps_repo import AgentStepsRepository
    from packages.tools.base import ToolContext

    agent = _make_agent(orchestrator, agent_role)
    task_id = uuid4()
    started_at = datetime.now(timezone.utc)
    await orchestrator._push({
        "type": "agent_started",
        "agent_name": getattr(agent, "name", agent_role).replace("_", " ").title(),
        "agent_role": agent_role,
        "task_id": str(task_id),
        "started_at": started_at.isoformat(),
        "input_summary": instruction[:200],
    })

    async def _persist_create() -> None:
        try:
            await AgentStepsRepository().create(
                step_id=str(task_id),
                session_id=str(session_id),
                specialist_role=agent_role,
                step_type="specialist_execution",
                input_json={"instruction": instruction[:500]},
                started_at=started_at,
            )
        except Exception as exc:
            logger.warning("agent_steps INSERT failed for task %s: %s", task_id, exc)

    await _persist_create()

    ctx = ToolContext(
        session_id=session_id,
        agent_step_id=task_id,
        specialist_role=agent_role,  # type: ignore[arg-type]
        actor="orchestrator",
        correlation_id=uuid4(),
    )
    task = SpecialistTask(
        task_id=task_id,
        instruction=instruction,
        context_payload=context_payload,
        allowed_tools=allowed_tools,
    )
    t0 = time.monotonic()
    result = cast(SpecialistResult, await agent.run(task, ctx))
    ended_at = datetime.now(timezone.utc)

    _usage = result.usage or {}
    await orchestrator._push({
        "type": "agent_completed",
        "agent_name": getattr(agent, "name", agent_role).replace("_", " ").title(),
        "agent_role": agent_role,
        "task_id": str(task_id),
        "duration_ms": int((time.monotonic() - t0) * 1000),
        "output_summary": str(result.output.get("text", ""))[:200] if result.output else None,
        "timestamp": ended_at.isoformat(),
        "input_tokens": _usage.get("input_tokens"),
        "output_tokens": _usage.get("output_tokens"),
        "cost_usd": _usage.get("cost_usd"),
    })

    if result.status == "failed":
        output_json: dict[str, Any] = {"error": result.error or "unknown"}
        await orchestrator._push({
            "type": "error",
            "code": "agent_failed",
            "message": f"Agent {agent_role} failed: {result.error}",
            "recoverable": False,
            "timestamp": ended_at.isoformat(),
        })
    else:
        output_json = {"summary": str(result.output.get("text", ""))[:500]}

    async def _persist_update() -> None:
        try:
            await AgentStepsRepository().update_ended(
                step_id=str(task_id),
                ended_at=ended_at,
                output_json=output_json,
            )
        except Exception:
            logger.warning("agent_steps UPDATE failed for task %s", task_id)

    asyncio.create_task(_persist_update())

    return result


async def run_direct_chat(
    orchestrator: Any,
    session_id: UUID,
    query: SessionUserQuery,
    intent: SessionIntent,
    route: AgentRoute,
) -> SessionResponse:
    from packages.agent.llm import LLMMessage
    from packages.persistence.agent_steps_repo import make_step

    step_id = await make_step(str(session_id), "direct_chat")
    parts: list[str] = []
    async for evt in await orchestrator._llm_client.stream(
        messages=[
            LLMMessage(
                role="system",
                content=(
                    "You are a helpful supply chain decision assistant. Reply briefly "
                    "and naturally in the same language the user writes in. Do not make "
                    "a decision recommendation unless the user asks for one."
                ),
            ),
            LLMMessage(role="user", content=orchestrator._query_text(query)),
        ],
        tools=None,
        temperature=0.0,
        max_tokens=512,
        specialist_role="orchestrator",
        agent_step_id=step_id,
    ):
        if evt.get("event") == "text_delta" and evt.get("data"):
            parts.append(evt["data"])
            await orchestrator._push({
                "type": "text_delta",
                "session_id": str(session_id),
                "delta": evt["data"],
                "timestamp": _iso_now(),
            })
    full_text = "".join(parts)
    await orchestrator._push(
        {"type": "response_ready", "mode": route.mode, "timestamp": _iso_now()}
    )
    return SessionResponse(mode=route.mode, reply=full_text, intent=intent, route=route)


from packages.agent.orchestrator.decision import (  # noqa: E402
    _build_decision_response as _build_decision_response,
    _resolve_weights_with_memory as _resolve_weights_with_memory,
    _synthesize_response as _synthesize_response,
    _write_decision_memory as _write_decision_memory,
)
from packages.agent.orchestrator.planning import (  # noqa: E402
    _run_agents_in_order as _run_agents_in_order,
    create_execution_plan as create_execution_plan,
    create_task_nodes as create_task_nodes,
    run_dag_execution as run_dag_execution,
    run_planned_execution as run_planned_execution,
)
