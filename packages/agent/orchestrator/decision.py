from __future__ import annotations

import json
from decimal import Decimal
from typing import Any
from uuid import UUID

from packages.agent.orchestrator.models import (
    AgentRoute,
    SessionIntent,
    SessionResponse,
    SessionUserQuery,
    SpecialistResult,
)
from packages.agent.orchestrator.parsing import _iso_now


async def _synthesize_response(
    orchestrator: Any,
    session_id: UUID,
    query: SessionUserQuery,
    intent: SessionIntent,
    route: AgentRoute,
    agent_results: dict[str, SpecialistResult],
) -> SessionResponse:
    from langchain_core.messages import HumanMessage, SystemMessage

    lc_messages = [
        SystemMessage(
            content=(
                "Synthesize the agent results into a concise assistant reply. "
                "Use the same language as the user. Do not invent raw inventory rows."
            )
        ),
        HumanMessage(
            content=json.dumps(
                {
                    "query": query.text,
                    "intent": intent.model_dump(),
                    "agent_results": {k: v.output for k, v in agent_results.items()},
                },
                default=lambda o: float(o) if isinstance(o, Decimal) else str(o),
            )
        ),
    ]
    parts: list[str] = []
    async for chunk in orchestrator._llm_client.astream(lc_messages):
        delta = chunk.content if isinstance(chunk.content, str) else ""
        if delta:
            parts.append(delta)
            await orchestrator._push({
                "type": "text_delta",
                "session_id": str(session_id),
                "delta": delta,
                "timestamp": _iso_now(),
            })
    response_text = "".join(parts)
    await orchestrator._push(
        {"type": "response_ready", "mode": route.mode, "timestamp": _iso_now()}
    )
    orchestrator._schedule_status_update(session_id, "completed")
    return SessionResponse(
        mode=route.mode,
        reply=response_text,
        intent=intent,
        route=route,
        agent_results=agent_results,
    )
