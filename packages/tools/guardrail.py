from __future__ import annotations

from typing import Literal

from packages.schemas.recommendation import Candidate


def can_execute(action: str, actor: str | None) -> bool:
    """True if actor is authorised to perform action."""
    if action == "approve_recommendation":
        return _resolve_role(actor) in ("approver", "admin")
    return True


def needs_approval(risk_level: Literal["low", "medium", "high"]) -> bool:
    """True if risk level requires human sign-off before execution."""
    return risk_level in ("high", "medium")


def audit_required(action: str) -> bool:
    """True if action must produce an audit log entry."""
    return action in _AUDIT_ACTIONS


def classify_risk(primary: Candidate) -> Literal["low", "medium", "high"]:
    """Derive risk level from KPI scores on the primary candidate."""
    for score in primary.kpi_scores:
        if score.name == "service_level":
            if score.value < 0.85:
                return "high"
            if score.value < 0.95:
                return "medium"
    return "low"


_AUDIT_ACTIONS: frozenset[str] = frozenset({
    "approve_recommendation",
    "reject_recommendation",
    "replenishment_recommendation",
})


def _resolve_role(user_id: str | None) -> str:
    if user_id in ("dev-approver", "dev-admin"):
        return "approver"
    return "analyst"
