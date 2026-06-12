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

# Maximum total characters for the bounded tool_results digest included in the
# synthesize prompt as a safety net (D-011 fix, approach B).
# When the agent text is the blocked fallback or very short (< 50 chars), the
# synthesize call would have no grounding data at all.  This digest provides
# recoverable signal without risking context saturation.
#
# Budget: synthesize prompt already fits comfortably under 70% of num_ctx after
# P97-B-01 slimming; this digest adds at most ~1000 tokens (4000 chars / 4).
# Combined with _SYNTHESIZE_AGENT_OUTPUT_MAX_CHARS=8000 the total headroom is
# well within the 11469-token target.
_SYNTHESIZE_TOOL_DIGEST_MAX_CHARS = 4_000

# Agent text is considered a blocked/degenerate fallback when it is shorter than
# this length; in that case the tool_results digest is included in the slim output
# so the synthesize LLM has grounding data to work with.
_FALLBACK_TEXT_MIN_LEN = 50


def _build_tool_digest(
    tool_results: Any,
    max_chars: int = _SYNTHESIZE_TOOL_DIGEST_MAX_CHARS,
) -> str:
    """Build a bounded, deterministic digest of tool_results for the synthesize prompt.

    Serialises each tool result entry to JSON, taking entries in order until the
    character budget is exhausted.  A truncation marker is appended when the budget
    is hit so the LLM knows the digest is not complete.

    Returns an empty string when tool_results is falsy or not a list.
    """
    if not tool_results or not isinstance(tool_results, list):
        return ""

    parts: list[str] = []
    used = 0
    for entry in tool_results:
        chunk = json.dumps(entry, default=lambda o: float(o) if isinstance(o, Decimal) else str(o))
        if used + len(chunk) > max_chars:
            remaining = max_chars - used
            if remaining > 0:
                parts.append(chunk[:remaining] + " ...[truncated]")
            break
        parts.append(chunk)
        used += len(chunk)
        if used >= max_chars:
            break

    return "\n".join(parts)


def _slim_agent_output(output: dict[str, Any] | None) -> dict[str, Any]:
    """Return a slimmed copy of an agent output for use in the synthesize prompt.

    Strips raw ``tool_results`` (dominant context contributor at 86% of num_ctx in
    the P94 session) and any keys not needed by synthesis.
    Keeps: ``text``, ``specialist``, ``verification``.

    Safety net (D-011 fix, approach B):
    When ``text`` is absent, empty, or shorter than _FALLBACK_TEXT_MIN_LEN
    (indicating the control-agent produced a blocked/degenerate fallback), a bounded
    digest of ``tool_results`` (capped at _SYNTHESIZE_TOOL_DIGEST_MAX_CHARS) is
    included so the synthesize LLM has recoverable grounding data.

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
        text = slim["text"]

    # Safety net: when agent text is a fallback/very short, inject a bounded tool digest.
    text_is_fallback = not isinstance(text, str) or len(text.strip()) < _FALLBACK_TEXT_MIN_LEN
    if text_is_fallback and output.get("tool_results"):
        digest = _build_tool_digest(output["tool_results"])
        if digest:
            slim["tool_results_digest"] = digest

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
