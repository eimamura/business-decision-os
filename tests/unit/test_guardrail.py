from __future__ import annotations

import pytest

from packages.persistence.users_repo import UserRepository
from packages.schemas.recommendation import Candidate, KpiScore
from packages.tools.guardrail import (
    _resolve_role,
    audit_required,
    can_execute,
    classify_risk,
    load_roles,
    needs_approval,
    resolve_role_async,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_candidate(*kpi_pairs: tuple[str, float]) -> Candidate:
    """Build a minimal Candidate with the supplied KPI name/value pairs."""
    scores: list[KpiScore] = []
    for name, value in kpi_pairs:
        direction: str = "lower_better" if name == "service_level" else "higher_better"
        scores.append(
            KpiScore(name=name, value=value, unit="", direction=direction)  # type: ignore[arg-type]
        )
    return Candidate(
        id="c1",
        action={},
        kpi_scores=scores,
        constraints_satisfied=[],
        constraints_violated=[],
    )


# ---------------------------------------------------------------------------
# classify_risk – parametrised KPI combinations
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "kpi_pairs, expected",
    [
        # service_level well above both thresholds → low
        ([("service_level", 0.99)], "low"),
        # service_level between medium and high thresholds → medium
        ([("service_level", 0.90)], "medium"),
        # service_level below high threshold → high
        ([("service_level", 0.80)], "high"),
        # cost above high threshold → high
        ([("total_supply_chain_cost", 1_500_000.0)], "high"),
        # cost between medium and high → medium
        ([("total_supply_chain_cost", 750_000.0)], "medium"),
        # cost below medium threshold → low
        ([("total_supply_chain_cost", 200_000.0)], "low"),
        # stockout_rate above high threshold → high
        ([("stockout_rate", 0.20)], "high"),
        # stockout_rate between thresholds → medium
        ([("stockout_rate", 0.10)], "medium"),
        # stockout_rate below medium threshold → low
        ([("stockout_rate", 0.02)], "low"),
        # service_level medium AND cost below thresholds → medium
        ([("service_level", 0.90), ("total_supply_chain_cost", 200_000.0)], "medium"),
        # service_level OK but cost is high → high
        ([("service_level", 0.99), ("total_supply_chain_cost", 1_500_000.0)], "high"),
        # service_level below high threshold AND cost above high → high (first KPI already high)
        ([("service_level", 0.80), ("total_supply_chain_cost", 1_500_000.0)], "high"),
        # unknown KPI alone → low (not in threshold config)
        ([("unknown_kpi", 999.0)], "low"),
        # no KPIs at all → low
        ([], "low"),
    ],
)
def test_classify_risk_kpi_combinations(
    kpi_pairs: list[tuple[str, float]],
    expected: str,
) -> None:
    candidate = _make_candidate(*kpi_pairs)
    assert classify_risk(candidate) == expected


# ---------------------------------------------------------------------------
# needs_approval
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "risk_level, expected",
    [
        ("high", True),
        ("medium", True),
        ("low", False),
    ],
)
def test_needs_approval(risk_level: str, expected: bool) -> None:
    assert needs_approval(risk_level) == expected  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# audit_required
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "action, expected",
    [
        ("approve_recommendation", True),
        ("reject_recommendation", True),
        ("replenishment_recommendation", True),
        ("some_other_action", False),
        ("", False),
    ],
)
def test_audit_required(action: str, expected: bool) -> None:
    assert audit_required(action) == expected


# ---------------------------------------------------------------------------
# _resolve_role (sync, in-memory map)
# ---------------------------------------------------------------------------

def test_resolve_role_returns_approver_for_dev_users() -> None:
    load_roles({"dev-approver": "approver", "dev-admin": "approver"})
    assert _resolve_role("dev-approver") == "approver"
    assert _resolve_role("dev-admin") == "approver"


def test_resolve_role_returns_analyst_for_unknown() -> None:
    load_roles({})
    assert _resolve_role("unknown-user") == "analyst"


def test_resolve_role_returns_analyst_for_none() -> None:
    assert _resolve_role(None) == "analyst"


# ---------------------------------------------------------------------------
# resolve_role_async
# ---------------------------------------------------------------------------

async def test_resolve_role_async_uses_in_memory_map() -> None:
    load_roles({"trusted-approver": "approver"})
    role = await resolve_role_async("trusted-approver")
    assert role == "approver"


async def test_resolve_role_async_returns_analyst_for_unknown() -> None:
    load_roles({})
    role = await resolve_role_async("no-such-user")
    assert role == "analyst"


async def test_resolve_role_async_returns_analyst_for_none() -> None:
    role = await resolve_role_async(None)
    assert role == "analyst"


# ---------------------------------------------------------------------------
# UserRepository.get_role (DB-backed stub)
# ---------------------------------------------------------------------------

async def test_user_repository_get_role_returns_analyst_for_any_user() -> None:
    repo = UserRepository()
    assert await repo.get_role("any-user-id") == "analyst"


async def test_user_repository_get_role_consistent_for_known_id() -> None:
    repo = UserRepository()
    # The stub always returns "analyst"; when the users table is added this
    # test should be updated with a fixture that seeds a real user row.
    result = await repo.get_role("dev-approver")
    assert result == "analyst"


# ---------------------------------------------------------------------------
# can_execute (async)
# ---------------------------------------------------------------------------

async def test_can_execute_approve_recommendation_for_approver() -> None:
    load_roles({"alice": "approver"})
    assert await can_execute("approve_recommendation", "alice") is True


async def test_can_execute_approve_recommendation_denies_analyst() -> None:
    load_roles({})
    assert await can_execute("approve_recommendation", "bob") is False


async def test_can_execute_any_other_action_always_true() -> None:
    load_roles({})
    assert await can_execute("view_dashboard", None) is True
    assert await can_execute("run_simulation", "unknown") is True
