from __future__ import annotations

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
