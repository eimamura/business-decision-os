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

# Maximum characters of a single agent output entry included in the synthesize
# prompt.  The synthesize call needs only the agent's text conclusion plus
# lightweight metadata — raw tool_results are stripped before this cap is applied
# so in practice the serialized entry will be far smaller.  The cap is a hard
# safety net against future regressions (e.g. an unusually long reply text).
#
# Budget rationale (P97 T-592):
#   _OLLAMA_NUM_CTX = 16384 tokens; target ≤ 70% = 11469 tokens.
#   Synthesize system prompt ≈ 50 tokens.
#   Intent + query envelope ≈ 200 tokens.
#   Remaining budget for all agent outputs: 11469 - 250 = ~11219 tokens.
#   At ~4 chars/token that is ~44876 chars across all agents (typically 1 agent).
#   We set the per-agent cap to 8000 chars (~2000 tokens) — well within budget
#   and large enough to hold any reasonable text reply from ControlAgent.
_SYNTHESIZE_AGENT_OUTPUT_MAX_CHARS = 8_000


def _slim_agent_output(output: dict[str, Any] | None) -> dict[str, Any]:
    """Return a slimmed copy of an agent output for use in the synthesize prompt.

    Strips ``tool_results`` (raw DB data — dominant contributor at 86% of
    num_ctx in the P94 session) and any other keys not needed by synthesis.
    Keeps: ``text``, ``specialist``, ``verification``.

    If the remaining serialized entry still exceeds _SYNTHESIZE_AGENT_OUTPUT_MAX_CHARS
    (e.g. an unusually long reply text), the ``text`` field is hard-truncated with
    a marker so the LLM knows it was cut.
    """
    if output is None:
        return {}

    slim: dict[str, Any] = {}
    if "text" in output:
        slim["text"] = output["text"]
    if "specialist" in output:
        slim["specialist"] = output["specialist"]
    if "verification" in output:
        slim["verification"] = output["verification"]

    # Hard cap: if text alone is too large, truncate it.
    text = slim.get("text", "")
    if isinstance(text, str) and len(text) > _SYNTHESIZE_AGENT_OUTPUT_MAX_CHARS:
        slim["text"] = text[:_SYNTHESIZE_AGENT_OUTPUT_MAX_CHARS] + " ...[truncated]"

    return slim


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
                    # Strip raw tool_results before building the synthesize prompt.
                    # tool_results were the dominant context contributor in the P94
                    # session (analyze_forecast_deviation output: 30 SKUs × weekly
                    # breakdown ≈ 22 739 chars, 86% of num_ctx 16384).  The synthesize
                    # call only needs the agent's text conclusion; the control agent
                    # has already consumed and condensed the raw data into that text.
                    "agent_results": {
                        k: _slim_agent_output(v.output)
                        for k, v in agent_results.items()
                    },
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
