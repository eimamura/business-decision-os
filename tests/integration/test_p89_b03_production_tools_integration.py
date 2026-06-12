"""T-561: Integration tests for P89 production analysis tools against a real PostgreSQL DB.

Requires a running PostgreSQL instance reachable via DATABASE_URL with migration 0020
applied and the P89 seed data loaded (scripts/seed_db.py).

Deterministic seed scenarios (scripts/generate_sample_data.py constants):
    PRODUCTION_OVERPRODUCTION_SKU  = "SKU-026"   planned=200/wk, demand≈10/wk  → overproduction
    PRODUCTION_UNDERPRODUCTION_SKU = "SKU-001"   planned=10/wk,  demand≈70/wk  → underproduction
    PRODUCTION_SATURATED_LOCATION  = "WH-001"    week 0: Σplanned=2250 > cap=2000 → binding constraint

Run with:
    docker compose up -d db && DATABASE_URL=postgresql+asyncpg://bdos:bdos_dev@localhost:5432/bdos \\
        uv run pytest tests/integration/test_p89_b03_production_tools_integration.py -v
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
# analyze_production_plan_gap — smoke tests
# ===========================================================================


@_SKIP_NO_DB
async def test_analyze_production_plan_gap_returns_no_error() -> None:
    """Tool executes against the real DB without returning an error key."""
    from packages.tools.analyze_production_plan_gap_tool import AnalyzeProductionPlanGapTool

    tool = AnalyzeProductionPlanGapTool()
    result = await tool.handle({}, _ctx())

    assert "error" not in result.output, (
        f"Unexpected error from analyze_production_plan_gap: {result.output.get('error')}"
    )


@_SKIP_NO_DB
async def test_analyze_production_plan_gap_output_has_required_schema_fields() -> None:
    """Tool output includes all required top-level contract fields with correct types."""
    from packages.tools.analyze_production_plan_gap_tool import AnalyzeProductionPlanGapTool

    tool = AnalyzeProductionPlanGapTool()
    result = await tool.handle({}, _ctx())

    out = result.output
    assert "horizon_weeks" in out, "missing_field: horizon_weeks"
    assert "items" in out, "missing_field: items"
    assert "summary" in out, "missing_field: summary"
    assert "truncated" in out, "missing_field: truncated"
    assert "missing_data" in out, "missing_field: missing_data"

    assert isinstance(out["items"], list)
    assert isinstance(out["truncated"], bool)
    assert isinstance(out["missing_data"], list)

    s = out["summary"]
    assert "overproduction_count" in s
    assert "underproduction_count" in s
    assert "balanced_count" in s


# ===========================================================================
# analyze_production_plan_gap — scenario assertions
# ===========================================================================


@_SKIP_NO_DB
async def test_analyze_production_plan_gap_sku026_is_overproduction() -> None:
    """SKU-026 (seeded at 200/wk, demand≈10/wk) must appear with classification=overproduction.

    Seed: PRODUCTION_OVERPRODUCTION_PLANNED_QTY=200, demand_mean≈1.5/day → ~10/wk.
    Gap ≈ +190/wk → gap_pct ≈ +1900% >> +25% threshold.
    """
    from packages.tools.analyze_production_plan_gap_tool import AnalyzeProductionPlanGapTool

    tool = AnalyzeProductionPlanGapTool()
    result = await tool.handle({"horizon_weeks": 1}, _ctx())

    items = result.output["items"]
    sku026_items = [i for i in items if i["sku_id"] == "SKU-026"]

    assert len(sku026_items) >= 1, (
        f"SKU-026 not found in items. sku_ids present: {[i['sku_id'] for i in items[:10]]}"
    )

    for item in sku026_items:
        assert item["classification"] == "overproduction", (
            f"SKU-026 expected overproduction, got {item['classification']!r} "
            f"(planned={item['planned_qty']}, expected_demand={item['expected_demand']})"
        )


@_SKIP_NO_DB
async def test_analyze_production_plan_gap_sku026_overproduction_in_summary_count() -> None:
    """summary.overproduction_count >= 1 when SKU-026 overproduction is seeded."""
    from packages.tools.analyze_production_plan_gap_tool import AnalyzeProductionPlanGapTool

    tool = AnalyzeProductionPlanGapTool()
    result = await tool.handle({"horizon_weeks": 1}, _ctx())

    assert result.output["summary"]["overproduction_count"] >= 1, (
        "Expected at least one overproduction item from seeded SKU-026 data"
    )


@_SKIP_NO_DB
async def test_analyze_production_plan_gap_sku001_is_underproduction() -> None:
    """SKU-001 (seeded at 10/wk, demand≈70/wk) must appear with classification=underproduction.

    Seed: PRODUCTION_UNDERPRODUCTION_PLANNED_QTY=10, demand_mean≈10/day → ~70/wk.
    Gap ≈ -60/wk → gap_pct ≈ -86% << -25% threshold.
    """
    from packages.tools.analyze_production_plan_gap_tool import AnalyzeProductionPlanGapTool

    tool = AnalyzeProductionPlanGapTool()
    # SKU-001 underproduction only seeded at WH-001; use location filter for precision
    result = await tool.handle({"horizon_weeks": 1, "location_id": "WH-001"}, _ctx())

    items = result.output["items"]
    sku001_items = [i for i in items if i["sku_id"] == "SKU-001"]

    assert len(sku001_items) >= 1, (
        f"SKU-001 not found in WH-001 items. sku_ids present: {[i['sku_id'] for i in items[:10]]}"
    )

    for item in sku001_items:
        assert item["classification"] == "underproduction", (
            f"SKU-001 expected underproduction, got {item['classification']!r} "
            f"(planned={item['planned_qty']}, expected_demand={item['expected_demand']})"
        )


@_SKIP_NO_DB
async def test_analyze_production_plan_gap_sku001_underproduction_in_summary_count() -> None:
    """summary.underproduction_count >= 1 when SKU-001 underproduction is seeded at WH-001."""
    from packages.tools.analyze_production_plan_gap_tool import AnalyzeProductionPlanGapTool

    tool = AnalyzeProductionPlanGapTool()
    result = await tool.handle({"horizon_weeks": 1, "location_id": "WH-001"}, _ctx())

    assert result.output["summary"]["underproduction_count"] >= 1, (
        "Expected at least one underproduction item from seeded SKU-001 data at WH-001"
    )


# ===========================================================================
# identify_binding_constraint — smoke tests
# ===========================================================================


@_SKIP_NO_DB
async def test_identify_binding_constraint_returns_no_error() -> None:
    """Tool executes against the real DB without returning an error key."""
    from packages.tools.identify_binding_constraint_tool import IdentifyBindingConstraintTool

    tool = IdentifyBindingConstraintTool()
    result = await tool.handle({}, _ctx())

    assert "error" not in result.output, (
        f"Unexpected error from identify_binding_constraint: {result.output.get('error')}"
    )


@_SKIP_NO_DB
async def test_identify_binding_constraint_output_has_required_schema_fields() -> None:
    """Tool output includes constraints, truncated, missing_data fields with correct types."""
    from packages.tools.identify_binding_constraint_tool import IdentifyBindingConstraintTool

    tool = IdentifyBindingConstraintTool()
    result = await tool.handle({}, _ctx())

    out = result.output
    assert "constraints" in out, "missing_field: constraints"
    assert "truncated" in out, "missing_field: truncated"
    assert "missing_data" in out, "missing_field: missing_data"

    assert isinstance(out["constraints"], list)
    assert isinstance(out["truncated"], bool)
    assert isinstance(out["missing_data"], list)


@_SKIP_NO_DB
async def test_identify_binding_constraint_each_item_has_required_fields() -> None:
    """Every constraint record has constraint_type, subject, impact_estimate, evidence."""
    from packages.tools.identify_binding_constraint_tool import IdentifyBindingConstraintTool

    tool = IdentifyBindingConstraintTool()
    result = await tool.handle({}, _ctx())

    for i, c in enumerate(result.output["constraints"]):
        assert "constraint_type" in c, f"constraints[{i}] missing constraint_type"
        assert "subject" in c, f"constraints[{i}] missing subject"
        assert "impact_estimate" in c, f"constraints[{i}] missing impact_estimate"
        assert "evidence" in c, f"constraints[{i}] missing evidence"
        assert c["constraint_type"] in (
            "production_capacity",
            "supply_gap",
            "inventory_stockout",
        ), f"constraints[{i}] unexpected constraint_type: {c['constraint_type']!r}"


# ===========================================================================
# identify_binding_constraint — WH-001 binding constraint scenario
# ===========================================================================


@_SKIP_NO_DB
async def test_identify_binding_constraint_wh001_present_as_production_capacity() -> None:
    """WH-001 current-week overload must appear as a production_capacity constraint.

    Seed: WH-001 week 0 has Σplanned=2250 > capacity=2000 (utilization=1.125).
    At least one constraint with constraint_type=production_capacity and
    subject containing 'WH-001' must be present in the output.
    """
    from packages.tools.identify_binding_constraint_tool import IdentifyBindingConstraintTool

    tool = IdentifyBindingConstraintTool()
    result = await tool.handle({}, _ctx())

    constraints = result.output["constraints"]
    wh001_cap = [
        c for c in constraints
        if c["constraint_type"] == "production_capacity" and "WH-001" in c["subject"]
    ]

    assert len(wh001_cap) >= 1, (
        f"No production_capacity constraint found for WH-001. "
        f"All constraints: {[(c['constraint_type'], c['subject']) for c in constraints]}"
    )


@_SKIP_NO_DB
async def test_identify_binding_constraint_wh001_has_positive_impact_estimate() -> None:
    """WH-001 production_capacity constraint must have impact_estimate > 0.

    Seed: overload_units = 2250 - 2000 = 250; avg_stockout_cost > 0 from cost_master.
    """
    from packages.tools.identify_binding_constraint_tool import IdentifyBindingConstraintTool

    tool = IdentifyBindingConstraintTool()
    result = await tool.handle({}, _ctx())

    constraints = result.output["constraints"]
    wh001_cap = [
        c for c in constraints
        if c["constraint_type"] == "production_capacity" and "WH-001" in c["subject"]
    ]

    assert len(wh001_cap) >= 1, "No WH-001 production_capacity constraint found"
    for c in wh001_cap:
        assert c["impact_estimate"] > 0, (
            f"WH-001 production_capacity constraint has zero or negative impact_estimate: "
            f"{c['impact_estimate']} (evidence: {c['evidence']})"
        )


@_SKIP_NO_DB
async def test_identify_binding_constraint_wh001_is_ranked_first() -> None:
    """WH-001 current-week production_capacity constraint must be ranked #1 (index 0).

    Seed guarantees: overload=250 units × avg_stockout_cost produces the highest
    impact_estimate among all constraint candidates because:
      - WH-001 week 0 Σplanned=2250 vs capacity=2000 → 250-unit overload
      - The planned SKU mix has stockout_costs in cost_master
    The ranking is impact_estimate DESC, subject ASC.
    """
    from packages.tools.identify_binding_constraint_tool import IdentifyBindingConstraintTool

    tool = IdentifyBindingConstraintTool()
    result = await tool.handle({}, _ctx())

    constraints = result.output["constraints"]
    assert len(constraints) >= 1, "No constraints returned; cannot verify rank-1 position"

    top = constraints[0]
    assert top["constraint_type"] == "production_capacity", (
        f"Expected rank-1 constraint_type='production_capacity', got {top['constraint_type']!r}"
    )
    assert "WH-001" in top["subject"], (
        f"Expected rank-1 subject to contain 'WH-001', got {top['subject']!r}"
    )


@_SKIP_NO_DB
async def test_identify_binding_constraint_wh001_evidence_has_overload_units() -> None:
    """WH-001 constraint evidence must include overload_units, utilization, planned_units."""
    from packages.tools.identify_binding_constraint_tool import IdentifyBindingConstraintTool

    tool = IdentifyBindingConstraintTool()
    result = await tool.handle({}, _ctx())

    constraints = result.output["constraints"]
    wh001_cap = next(
        (c for c in constraints
         if c["constraint_type"] == "production_capacity" and "WH-001" in c["subject"]),
        None,
    )

    assert wh001_cap is not None, "No WH-001 production_capacity constraint found"

    ev = wh001_cap["evidence"]
    assert "overload_units" in ev, f"evidence missing overload_units: {ev}"
    assert "utilization" in ev, f"evidence missing utilization: {ev}"
    assert "planned_units" in ev, f"evidence missing planned_units: {ev}"
    assert "capacity_units" in ev, f"evidence missing capacity_units: {ev}"

    # Seed: planned=2250, capacity=2000 → overload=250, utilization≈1.125
    assert ev["overload_units"] > 0, f"Expected overload_units > 0, got {ev['overload_units']}"
    assert ev["utilization"] > 1.0, f"Expected utilization > 1.0, got {ev['utilization']}"
