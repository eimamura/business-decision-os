"""T-552: Integration tests for detect_demand_shift_tool against a real PostgreSQL database.

Requires a running PostgreSQL instance reachable via DATABASE_URL with migration 0019
applied and the P88 seed data loaded (scripts/seed_db.py).

Deterministic seed scenarios (scripts/generate_sample_data.py constants):
    CUST-009 (Kanto)  — growth:  1 prior order × 50 qty → 3 current orders × 50 qty
    CUST-010 (Kansai) — decline: 3 prior orders × 50 qty → 1 current order × 50 qty

Seed window alignment (default window_days=28, end_date_offset=1):
    current window : [today-28, today-1]
    prior window   : [today-56, today-29]

    CO-DS01 (CUST-009, today-45) → prior window  (prior_qty += 50)
    CO-DS02 (CUST-009, today-20) → current window (current_qty += 50)
    CO-DS03 (CUST-009, today-15) → current window (current_qty += 50)
    CO-DS04 (CUST-009, today-10) → current window (current_qty += 50)
    CO-DS05 (CUST-010, today-50) → prior window  (prior_qty += 50)
    CO-DS06 (CUST-010, today-45) → prior window  (prior_qty += 50)
    CO-DS07 (CUST-010, today-40) → prior window  (prior_qty += 50)
    CO-DS08 (CUST-010, today-10) → current window (current_qty += 50)

Run with:
    docker compose up -d db && uv run pytest tests/integration/test_p88_detect_demand_shift_integration.py -v
"""
from __future__ import annotations

import os
from uuid import uuid4

import pytest

from packages.tools.base import ToolContext

_HAS_DB = bool(os.environ.get("DATABASE_URL"))
_SKIP_NO_DB = pytest.mark.skipif(not _HAS_DB, reason="DATABASE_URL not set")


def _ctx() -> ToolContext:
    return ToolContext(
        session_id=uuid4(),
        agent_step_id=uuid4(),
        specialist_role="control",
        actor="integration_test",
        correlation_id=uuid4(),
    )


@pytest.fixture(autouse=True)
async def reset_db_pool() -> None:  # type: ignore[misc]
    """Reset the global asyncpg pool before and after each test.

    pytest-asyncio creates a new event loop per test function. The global pool
    singleton in packages/persistence/db.py is bound to the event loop in which
    it was created, so reusing it across tests causes 'loop is closed' errors.
    Resetting the module-level variable forces pool recreation in the current loop.
    """
    import packages.persistence.db as db_module

    db_module._pool = None
    yield  # type: ignore[misc]
    if db_module._pool is not None:
        await db_module._pool.close()
        db_module._pool = None


# ===========================================================================
# Basic smoke tests
# ===========================================================================


@_SKIP_NO_DB
async def test_detect_demand_shift_returns_no_error() -> None:
    """Tool executes against the real DB without returning an error key."""
    from packages.tools.detect_demand_shift_tool import DetectDemandShiftTool

    tool = DetectDemandShiftTool()
    result = await tool.handle({}, _ctx())

    assert "error" not in result.output, (
        f"Unexpected error from detect_demand_shift: {result.output.get('error')}"
    )


@_SKIP_NO_DB
async def test_detect_demand_shift_output_has_required_schema_fields() -> None:
    """Tool output has all required top-level fields with correct types."""
    from packages.tools.detect_demand_shift_tool import DetectDemandShiftTool

    tool = DetectDemandShiftTool()
    result = await tool.handle({}, _ctx())

    assert "window" in result.output
    assert "customer_shifts" in result.output
    assert "region_shifts" in result.output
    assert "missing_data" in result.output
    assert isinstance(result.output["missing_data"], list)

    for axis in ("customer_shifts", "region_shifts"):
        assert "growth" in result.output[axis], f"{axis} missing 'growth'"
        assert "decline" in result.output[axis], f"{axis} missing 'decline'"
        assert "truncated" in result.output[axis], f"{axis} missing 'truncated'"
        assert isinstance(result.output[axis]["growth"], list)
        assert isinstance(result.output[axis]["decline"], list)
        assert isinstance(result.output[axis]["truncated"], bool)


# ===========================================================================
# T-552: CUST-009 appears in customer growth
# ===========================================================================


@_SKIP_NO_DB
async def test_detect_demand_shift_cust009_appears_in_customer_growth() -> None:
    """CUST-009 must appear in customer_shifts.growth (seeded 50→150 qty shift)."""
    from packages.tools.detect_demand_shift_tool import DetectDemandShiftTool

    tool = DetectDemandShiftTool()
    result = await tool.handle({}, _ctx())

    growth_ids = {r["id"] for r in result.output["customer_shifts"]["growth"]}
    assert "CUST-009" in growth_ids, (
        f"CUST-009 not found in customer growth. Growth IDs: {growth_ids}"
    )


@_SKIP_NO_DB
async def test_detect_demand_shift_cust009_growth_prior_qty_is_50() -> None:
    """CUST-009 growth record: prior_qty must equal 50 (1 order × 50 in seed)."""
    from packages.tools.detect_demand_shift_tool import DetectDemandShiftTool

    tool = DetectDemandShiftTool()
    result = await tool.handle({}, _ctx())

    growth = result.output["customer_shifts"]["growth"]
    cust009 = next((r for r in growth if r["id"] == "CUST-009"), None)
    assert cust009 is not None, "CUST-009 not found in customer growth"
    assert cust009["prior_qty"] == 50, (
        f"Expected prior_qty=50 for CUST-009, got {cust009['prior_qty']}"
    )


@_SKIP_NO_DB
async def test_detect_demand_shift_cust009_growth_current_qty_is_150() -> None:
    """CUST-009 growth record: current_qty must equal 150 (3 orders × 50 in seed)."""
    from packages.tools.detect_demand_shift_tool import DetectDemandShiftTool

    tool = DetectDemandShiftTool()
    result = await tool.handle({}, _ctx())

    growth = result.output["customer_shifts"]["growth"]
    cust009 = next((r for r in growth if r["id"] == "CUST-009"), None)
    assert cust009 is not None, "CUST-009 not found in customer growth"
    assert cust009["current_qty"] == 150, (
        f"Expected current_qty=150 for CUST-009, got {cust009['current_qty']}"
    )


@_SKIP_NO_DB
async def test_detect_demand_shift_cust009_not_in_decline() -> None:
    """CUST-009 must NOT appear in customer_shifts.decline."""
    from packages.tools.detect_demand_shift_tool import DetectDemandShiftTool

    tool = DetectDemandShiftTool()
    result = await tool.handle({}, _ctx())

    decline_ids = {r["id"] for r in result.output["customer_shifts"]["decline"]}
    assert "CUST-009" not in decline_ids, (
        f"CUST-009 incorrectly appears in customer decline: {decline_ids}"
    )


# ===========================================================================
# T-552: CUST-010 appears in customer decline
# ===========================================================================


@_SKIP_NO_DB
async def test_detect_demand_shift_cust010_appears_in_customer_decline() -> None:
    """CUST-010 must appear in customer_shifts.decline (seeded 150→50 qty shift)."""
    from packages.tools.detect_demand_shift_tool import DetectDemandShiftTool

    tool = DetectDemandShiftTool()
    result = await tool.handle({}, _ctx())

    decline_ids = {r["id"] for r in result.output["customer_shifts"]["decline"]}
    assert "CUST-010" in decline_ids, (
        f"CUST-010 not found in customer decline. Decline IDs: {decline_ids}"
    )


@_SKIP_NO_DB
async def test_detect_demand_shift_cust010_decline_prior_qty_is_150() -> None:
    """CUST-010 decline record: prior_qty must equal 150 (3 orders × 50 in seed)."""
    from packages.tools.detect_demand_shift_tool import DetectDemandShiftTool

    tool = DetectDemandShiftTool()
    result = await tool.handle({}, _ctx())

    decline = result.output["customer_shifts"]["decline"]
    cust010 = next((r for r in decline if r["id"] == "CUST-010"), None)
    assert cust010 is not None, "CUST-010 not found in customer decline"
    assert cust010["prior_qty"] == 150, (
        f"Expected prior_qty=150 for CUST-010, got {cust010['prior_qty']}"
    )


@_SKIP_NO_DB
async def test_detect_demand_shift_cust010_decline_current_qty_is_50() -> None:
    """CUST-010 decline record: current_qty must equal 50 (1 order × 50 in seed)."""
    from packages.tools.detect_demand_shift_tool import DetectDemandShiftTool

    tool = DetectDemandShiftTool()
    result = await tool.handle({}, _ctx())

    decline = result.output["customer_shifts"]["decline"]
    cust010 = next((r for r in decline if r["id"] == "CUST-010"), None)
    assert cust010 is not None, "CUST-010 not found in customer decline"
    assert cust010["current_qty"] == 50, (
        f"Expected current_qty=50 for CUST-010, got {cust010['current_qty']}"
    )


@_SKIP_NO_DB
async def test_detect_demand_shift_cust010_not_in_growth() -> None:
    """CUST-010 must NOT appear in customer_shifts.growth."""
    from packages.tools.detect_demand_shift_tool import DetectDemandShiftTool

    tool = DetectDemandShiftTool()
    result = await tool.handle({}, _ctx())

    growth_ids = {r["id"] for r in result.output["customer_shifts"]["growth"]}
    assert "CUST-010" not in growth_ids, (
        f"CUST-010 incorrectly appears in customer growth: {growth_ids}"
    )


# ===========================================================================
# T-552: Region axis — Kanto appears in growth
# ===========================================================================


@_SKIP_NO_DB
async def test_detect_demand_shift_kanto_appears_in_region_growth() -> None:
    """Kanto must appear in region_shifts.growth (CUST-009 orders are in Kanto).

    Note: other seeded orders in Kanto may contribute; we only assert direction.
    """
    from packages.tools.detect_demand_shift_tool import DetectDemandShiftTool

    tool = DetectDemandShiftTool()
    result = await tool.handle({}, _ctx())

    region_growth_ids = {r["id"] for r in result.output["region_shifts"]["growth"]}
    assert "Kanto" in region_growth_ids, (
        f"Kanto not found in region growth. Region growth IDs: {region_growth_ids}"
    )


@_SKIP_NO_DB
async def test_detect_demand_shift_kanto_growth_direction_positive() -> None:
    """Kanto growth record must have positive abs_change (demand increased)."""
    from packages.tools.detect_demand_shift_tool import DetectDemandShiftTool

    tool = DetectDemandShiftTool()
    result = await tool.handle({}, _ctx())

    region_growth = result.output["region_shifts"]["growth"]
    kanto = next((r for r in region_growth if r["id"] == "Kanto"), None)
    assert kanto is not None, "Kanto not found in region growth"
    assert kanto["abs_change"] > 0, (
        f"Expected positive abs_change for Kanto growth, got {kanto['abs_change']}"
    )


# ===========================================================================
# Shift record schema conformance
# ===========================================================================


@_SKIP_NO_DB
async def test_detect_demand_shift_shift_records_have_required_fields() -> None:
    """Every shift record in growth and decline lists must contain required fields."""
    from packages.tools.detect_demand_shift_tool import DetectDemandShiftTool

    tool = DetectDemandShiftTool()
    result = await tool.handle({}, _ctx())

    required_keys = {"id", "prior_qty", "current_qty", "abs_change", "pct_change"}
    for axis in ("customer_shifts", "region_shifts"):
        for direction in ("growth", "decline"):
            for rec in result.output[axis][direction]:
                missing = required_keys - rec.keys()
                assert not missing, (
                    f"{axis}.{direction} record missing keys {missing}: {rec}"
                )
