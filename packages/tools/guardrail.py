from __future__ import annotations

from typing import Literal

from packages.persistence.users_repo import UserRepository
from packages.schemas.recommendation import Candidate

# ---------------------------------------------------------------------------
# Risk threshold configuration
# ---------------------------------------------------------------------------
# Each key is a KPI name.  The nested dict has two keys:
#   "high"   – threshold value that maps to "high" risk
#   "medium" – threshold value that maps to "medium" risk
#
# Direction semantics:
#   service_level         → lower_better (below threshold = higher risk)
#   total_supply_chain_cost → higher_better (above threshold = higher risk)
#   stockout_rate         → higher_better (above threshold = higher risk)
_RISK_THRESHOLDS: dict[str, dict[str, float]] = {
    "service_level": {"high": 0.85, "medium": 0.95},
    "total_supply_chain_cost": {"high": 1_000_000.0, "medium": 500_000.0},
    "stockout_rate": {"high": 0.15, "medium": 0.05},
}

_AUDIT_ACTIONS: frozenset[str] = frozenset({
    "approve_recommendation",
    "reject_recommendation",
    "replenishment_recommendation",
})

# ---------------------------------------------------------------------------
# Module-level role map – populated from DB on startup via ``load_roles``.
# Provides a sync-safe fallback for ``_resolve_role``.
# ---------------------------------------------------------------------------
_role_map: dict[str, str] = {
    "dev-approver": "approver",
    "dev-admin": "approver",
}


def load_roles(mapping: dict[str, str]) -> None:
    """Overwrite the in-memory role map (call once at application startup)."""
    _role_map.clear()
    _role_map.update(mapping)


async def resolve_role_async(user_id: str | None) -> str:
    """Return the role for *user_id* via a DB lookup.

    Falls back to ``"analyst"`` for unknown users or when *user_id* is
    ``None``.
    """
    if user_id is None:
        return "analyst"
    # Check the in-memory map first (fast path / startup-loaded data).
    if user_id in _role_map:
        return _role_map[user_id]
    repo = UserRepository()
    return await repo.get_role(user_id)


async def can_execute(action: str, actor: str | None) -> bool:
    """True if actor is authorised to perform action."""
    if action == "approve_recommendation":
        role = await resolve_role_async(actor)
        return role in ("approver", "admin")
    return True


def needs_approval(risk_level: Literal["low", "medium", "high"]) -> bool:
    """True if risk level requires human sign-off before execution."""
    return risk_level in ("high", "medium")


def audit_required(action: str) -> bool:
    """True if action must produce an audit log entry."""
    return action in _AUDIT_ACTIONS


def classify_risk(primary: Candidate) -> Literal["low", "medium", "high"]:
    """Derive risk level from KPI scores on the primary candidate.

    All KPI scores are evaluated against ``_RISK_THRESHOLDS``.  If *any* KPI
    triggers the "high" threshold the result is ``"high"``; if *any* triggers
    "medium" the result is ``"medium"``; otherwise ``"low"``.
    """
    overall: Literal["low", "medium", "high"] = "low"
    for score in primary.kpi_scores:
        thresholds = _RISK_THRESHOLDS.get(score.name)
        if thresholds is None:
            continue
        level = _score_risk(score.name, score.value, thresholds)
        if level == "high":
            return "high"
        if level == "medium":
            overall = "medium"
    return overall


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _score_risk(
    name: str,
    value: float,
    thresholds: dict[str, float],
) -> Literal["low", "medium", "high"]:
    """Return the risk level for a single KPI value.

    ``service_level`` is *lower_better* (a lower value is riskier).
    All other KPIs in the threshold config are *higher_better* (a higher value
    is riskier).
    """
    if name == "service_level":
        if value < thresholds["high"]:
            return "high"
        if value < thresholds["medium"]:
            return "medium"
        return "low"
    # higher value = higher risk
    if value > thresholds["high"]:
        return "high"
    if value > thresholds["medium"]:
        return "medium"
    return "low"


def _resolve_role(user_id: str | None) -> str:
    """Sync role lookup against the in-memory map.

    Retained for internal use where an async call is not possible.  The map
    is populated by ``load_roles`` at startup; unknown users default to
    ``"analyst"``.
    """
    if user_id is None:
        return "analyst"
    return _role_map.get(user_id, "analyst")
