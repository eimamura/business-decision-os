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
from packages.agent.orchestrator.roles import DOMAIN_AGENT_ROLES

logger = logging.getLogger(__name__)

# Human role carried by interactive decision sessions when building ToolContext
# for specialist execution (D-026 fix).
#
# "manager" is the minimum role whose Layer-1 tool filter includes hitl-safety
# tools (see ToolRegistry.filter_for_user_role: analyst=read_only,
# manager=read_only+hitl, admin=unrestricted). P101 made HITL job flows a
# product feature of interactive sessions (approval queue UI + background jobs),
# so session-driven control turns must be able to bind job_dispatch and
# request_approval. Deliberately NOT "admin": that would additionally bind
# write-safety tools inline, bypassing the approval-gated dispatch design.
# Non-user-facing executors keep their own explicit roles (job_executor.py and
# screening.py pass "admin"; direct ToolContext users default to "analyst").
SESSION_USER_ROLE: str = "manager"


def _default_tools(agent_role: str) -> list[str]:
    from packages.tools.base import _ROLE_TOOL_ALLOWLIST
    return list(_ROLE_TOOL_ALLOWLIST.get(agent_role, []))


def _make_agent(orchestrator: Any, agent_role: str) -> Any:
    model_registry = getattr(orchestrator, "_model_registry", None)
    if agent_role in DOMAIN_AGENT_ROLES:
        from packages.agent.domain import create_domain_agents

        for agent in create_domain_agents(
            orchestrator._llm_client,
            orchestrator._tool_registry,
            sse_queue=orchestrator._sse_queue,
            model_registry=model_registry,
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
    agent_run_id = str(task_id)
    started_at = datetime.now(timezone.utc)
    model_name: str | None = getattr(orchestrator._llm_client, "_model", None)
    await orchestrator._push({
        "type": "graph_node", "event": "start",
        "kind": "agent", "name": agent_role,
        "run_id": agent_run_id,
        "timestamp": started_at.isoformat(),
        "input_summary": instruction[:200],
        "status": "ok", "meta": {"model_name": model_name},
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
        specialist_role=agent_role,
        actor="orchestrator",
        correlation_id=uuid4(),
        user_role=SESSION_USER_ROLE,
    )
    task = SpecialistTask(
        task_id=task_id,
        instruction=instruction,
        context_payload=context_payload,
        allowed_tools=allowed_tools,
    )
    t0 = time.monotonic()
    result = cast(SpecialistResult, await agent.run(task, ctx, agent_run_id=agent_run_id))
    ended_at = datetime.now(timezone.utc)

    _usage = result.usage or {}
    token_cost: dict[str, Any] | None = None
    if _usage.get("input_tokens") is not None:
        # peak_input_tokens: max single-call Ollama context-window usage for this run.
        # This is the authoritative saturation signal for the ≤90% threshold check.
        # input_tokens is the operator.add SUM of all calls (always > num_ctx for multi-call
        # runs) and MUST NOT be used for saturation evaluation.
        peak = _usage.get("peak_input_tokens") or 0
        token_cost = {
            "input_tokens": peak if peak > 0 else _usage.get("input_tokens", 0),
            "output_tokens": _usage.get("output_tokens", 0),
            "cost_usd": _usage.get("cost_usd", 0.0),
            "peak_input_tokens": peak,
            "total_input_tokens": _usage.get("input_tokens", 0),
        }
    await orchestrator._push({
        "type": "graph_node", "event": "end",
        "kind": "agent", "name": agent_role,
        "run_id": agent_run_id,
        "timestamp": ended_at.isoformat(),
        "duration_ms": int((time.monotonic() - t0) * 1000),
        "status": "error" if result.status == "failed" else "ok",
        "meta": {"model_name": model_name}, "token_cost": token_cost,
        **({"error": result.error} if result.status == "failed" else {}),
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
    from langchain_core.messages import HumanMessage, SystemMessage

    parts: list[str] = []
    async for chunk in orchestrator._llm_client.astream([
        SystemMessage(
            content=(
                "You are a helpful supply chain decision assistant. Reply briefly "
                "and naturally in the same language the user writes in. Do not make "
                "a decision recommendation unless the user asks for one."
            )
        ),
        HumanMessage(content=orchestrator._query_text(query)),
    ]):
        delta = chunk.content if isinstance(chunk.content, str) else ""
        if delta:
            parts.append(delta)
            await orchestrator._push({
                "type": "text_delta",
                "session_id": str(session_id),
                "delta": delta,
                "timestamp": _iso_now(),
            })
    full_text = "".join(parts)
    await orchestrator._push(
        {"type": "response_ready", "mode": route.mode, "timestamp": _iso_now()}
    )
    return SessionResponse(mode=route.mode, reply=full_text, intent=intent, route=route)


from packages.agent.orchestrator.decision import (  # noqa: E402
    _synthesize_response as _synthesize_response,
)
from packages.agent.orchestrator.planning import (  # noqa: E402
    _run_agents_in_order as _run_agents_in_order,
)
