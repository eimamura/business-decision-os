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
from packages.agent.orchestrator.parsing import _iso_now
from packages.agent.orchestrator.roles import (
    CROSS_DOMAIN_AGENT_CLASSES,
    DOMAIN_AGENT_ROLES,
)

logger = logging.getLogger(__name__)


def _default_tools(agent_role: str) -> list[str]:
    if agent_role == "data_engineer":
        return ["sql_query", "nl_query", "forecast"]
    if agent_role == "simulation_optimizer":
        return ["simulate_inventory", "optimize_replenishment"]
    if agent_role == "evaluator":
        return ["evaluate_candidates", "write_audit_log"]
    if agent_role == "anomaly_detector":
        return ["sql_query", "nl_query"]
    return []


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


async def _run_specialist_with_retry(
    orchestrator: Any,
    specialist: Any,
    task: SpecialistTask,
    ctx: Any,
) -> SpecialistResult:
    delays = [1, 4]
    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            return cast(SpecialistResult, await specialist.run(task, ctx))
        except Exception as exc:
            last_exc = exc
            logger.warning(
                "Agent %s attempt %d failed: %s",
                getattr(specialist, "role", "?"),
                attempt + 1,
                exc,
            )
            if attempt < len(delays):
                await asyncio.sleep(delays[attempt])
    return SpecialistResult(
        task_id=task.task_id,
        output={},
        tool_calls_made=[],
        status="failed",
        error=str(last_exc),
    )


async def _run_agent(
    orchestrator: Any,
    session_id: UUID,
    agent_role: str,
    instruction: str,
    context_payload: dict[str, Any],
    allowed_tools: list[str],
) -> SpecialistResult:
    from packages.tools.base import ToolContext

    agent = _make_agent(orchestrator, agent_role)
    task_id = uuid4()
    started_at = _iso_now()
    await orchestrator._push({
        "type": "agent_started",
        "agent_name": getattr(agent, "name", agent_role).replace("_", " ").title(),
        "agent_role": agent_role,
        "task_id": str(task_id),
        "started_at": started_at,
        "input_summary": instruction[:200],
    })
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
    result = await _run_specialist_with_retry(orchestrator, agent, task, ctx)
    await orchestrator._push({
        "type": "agent_completed",
        "agent_name": getattr(agent, "name", agent_role).replace("_", " ").title(),
        "agent_role": agent_role,
        "task_id": str(task_id),
        "duration_ms": int((time.monotonic() - t0) * 1000),
        "output_summary": str(result.output.get("text", ""))[:200] if result.output else None,
        "timestamp": _iso_now(),
    })
    if result.status == "failed":
        await orchestrator._push({
            "type": "error",
            "code": "agent_failed",
            "message": f"Agent {agent_role} failed: {result.error}",
            "recoverable": False,
            "timestamp": _iso_now(),
        })
    return result


async def run_direct_chat(
    orchestrator: Any,
    session_id: UUID,
    query: SessionUserQuery,
    intent: SessionIntent,
    route: AgentRoute,
) -> SessionResponse:
    from packages.agent.llm import LLMMessage

    response = await orchestrator._llm_client.complete(
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
    )
    await orchestrator._push(
        {"type": "response_ready", "mode": route.mode, "timestamp": _iso_now()}
    )
    orchestrator._sessions[session_id]["status"] = "completed"
    return SessionResponse(mode=route.mode, reply=response.text, intent=intent, route=route)


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
