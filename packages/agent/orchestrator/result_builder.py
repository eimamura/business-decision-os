from __future__ import annotations

from typing import Any

from packages.agent.orchestrator.models import (
    AgentRoute,
    SessionIntent,
    SessionResponse,
    SpecialistResult,
)
from packages.schemas.recommendation import Candidate, TradeoffExplanation


def build_response(
    intent: SessionIntent,
    route: AgentRoute,
    primary: Candidate,
    alternatives: list[Candidate],
    tradeoff: TradeoffExplanation,
    risk_level: str,
    requires_approval: bool,
    agent_results: dict[str, SpecialistResult],
) -> SessionResponse:
    """Assemble a SessionResponse from pre-computed decision components.

    This function is pure assembly: no LLM calls, no DB writes, no SSE events.
    All side-effects (memory writes, SSE pushes) remain in the caller.
    """
    reply = (
        f"Selected candidate {primary.id} for: {intent.goal_text or 'N/A'}\n\n"
        f"Primary action: {primary.action}\n"
        f"Risk level: {risk_level}"
    )
    return SessionResponse(
        mode=route.mode,
        reply=reply,
        intent=intent,
        route=route,
        agent_results=agent_results,
        primary=primary,
        alternatives=alternatives,
        tradeoff=tradeoff,
        risk_level=risk_level,  # type: ignore[arg-type]
        requires_approval=requires_approval,
    )


def build_job_result_reply(
    job_type: str,
    result: dict[str, Any] | None,
    files: list[dict[str, Any]],
) -> str:
    """Build a chat reply string for a completed job.

    Includes a one-line summary of the result and markdown links for each file.
    """
    summary_lines: list[str] = [f"Job `{job_type}` completed."]

    if result:
        # Include up to 3 top-level scalar fields from result as key: value
        shown = 0
        for k, v in result.items():
            if shown >= 3:
                break
            if isinstance(v, (str, int, float, bool)):
                summary_lines.append(f"- {k}: {v}")
                shown += 1

    if files:
        summary_lines.append(f"\n{len(files)} file(s) generated:")
        for f in files:
            name = f.get("file_name", "file")
            url = f.get("download_url", "")
            if url:
                summary_lines.append(f"- [{name}]({url})")
            else:
                summary_lines.append(f"- {name}")

    return "\n".join(summary_lines)
