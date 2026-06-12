"""T-557 / T-558 / T-559: Unit tests for P89 B-02 production analysis tools.

Covers:
- analyze_production_plan_gap:
  - Schema contract: required keys in output.
  - Gap classification thresholds: overproduction (>+25%), underproduction (<-25%), balanced.
  - expected_demand == 0 + planned > 0 → overproduction, gap_pct=None.
  - expected_demand == 0 + planned == 0 → balanced.
  - Forecast basis preferred over run-rate when forecast rows exist.
  - Missing data: SKU in plan with zero demand and no forecast → missing_data entry.
  - Cap + truncated: >100 items → truncated=True, items capped.
  - DB error → output contains error key.
  - horizon_weeks parameter respected.

- identify_binding_constraint:
  - Schema contract: required keys (constraints, truncated, missing_data).
  - Capacity overload: utilization > 100% → non-zero impact_estimate.
  - No overload: all capacity rows within limits → no production_capacity constraint.
  - Supply gap: forecast > on_hand + incoming → supply_gap record with impact.
  - Inventory stockout: critical/high risk → inventory_stockout record with impact.
  - Ranking: higher impact first; deterministic tie-break subject ASC.
  - DB error on cost_map → error in output.
  - missing_data: SKU without cost_master row noted.
  - Cap + truncated: >50 constraints → truncated=True, list capped.

- T-559 Wiring:
  - analyze_production_plan_gap registered in create_tool_registry.
  - identify_binding_constraint registered in create_tool_registry.
  - Both present in domain_analysis, cross_domain_analysis, decision_support.
  - identify_binding_constraint also in supply_chain.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from packages.tools.analyze_production_plan_gap_tool import (
    _classify_gap,
    AnalyzeProductionPlanGapTool,
)
from packages.tools.base import ToolContext


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_ctx() -> ToolContext:
    return ToolContext(
        session_id=uuid4(),
        agent_step_id=uuid4(),
        specialist_role="control",
        actor="test",
        correlation_id=uuid4(),
    )


def _make_pool_single_fetch(rows: list[Any]) -> MagicMock:
    """Pool mock whose conn.fetch always returns `rows`."""
    mock_conn = AsyncMock()
    mock_conn.fetch.return_value = rows
    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_pool


def _make_pool_seq(*fetch_seqs: list[Any]) -> MagicMock:
    """Pool mock with each fetch() call returning the next sequence."""
    mock_conn = AsyncMock()
    mock_conn.fetch.side_effect = list(fetch_seqs)
    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_pool


def _plan_row(sku_id: str, location_id: str, planned_qty: int) -> dict[str, Any]:
    return {"sku_id": sku_id, "location_id": location_id, "planned_qty": planned_qty}


def _forecast_row(sku_id: str, total_forecast: float) -> dict[str, Any]:
    return {"sku_id": sku_id, "total_forecast": total_forecast}


def _runrate_row(sku_id: str, avg_daily: float) -> dict[str, Any]:
    return {"sku_id": sku_id, "avg_daily": avg_daily}


# ===========================================================================
# _classify_gap unit tests (pure function)
# ===========================================================================


class TestClassifyGap:
    def test_classify_gap_overproduction_above_threshold(self) -> None:
        """planned > expected * 1.25 → overproduction."""
        cls, gap_qty, gap_pct = _classify_gap(130.0, 100.0)
        assert cls == "overproduction"
        assert gap_qty == pytest.approx(30.0)
        assert gap_pct == pytest.approx(30.0)

    def test_classify_gap_underproduction_below_threshold(self) -> None:
        """planned < expected * 0.75 → underproduction."""
        cls, gap_qty, gap_pct = _classify_gap(70.0, 100.0)
        assert cls == "underproduction"
        assert gap_qty == pytest.approx(-30.0)
        assert gap_pct == pytest.approx(-30.0)

    def test_classify_gap_balanced_within_threshold(self) -> None:
        """planned within ±25% of expected → balanced."""
        cls, gap_qty, gap_pct = _classify_gap(110.0, 100.0)
        assert cls == "balanced"
        assert gap_qty == pytest.approx(10.0)
        assert gap_pct == pytest.approx(10.0)

    def test_classify_gap_exactly_at_threshold_positive(self) -> None:
        """gap_pct == +25.0 exactly → balanced (threshold is strict >)."""
        cls, gap_qty, gap_pct = _classify_gap(125.0, 100.0)
        assert cls == "balanced"

    def test_classify_gap_exactly_at_threshold_negative(self) -> None:
        """gap_pct == -25.0 exactly → balanced (threshold is strict <)."""
        cls, gap_qty, gap_pct = _classify_gap(75.0, 100.0)
        assert cls == "balanced"

    def test_classify_gap_just_over_threshold(self) -> None:
        """gap_pct just above +25% → overproduction."""
        cls, _, _ = _classify_gap(125.1, 100.0)
        assert cls == "overproduction"

    def test_classify_gap_just_under_threshold(self) -> None:
        """gap_pct just below -25% → underproduction."""
        cls, _, _ = _classify_gap(74.9, 100.0)
        assert cls == "underproduction"

    def test_classify_gap_zero_expected_demand_with_planned(self) -> None:
        """expected_demand == 0 and planned > 0 → overproduction, gap_pct=None."""
        cls, gap_qty, gap_pct = _classify_gap(100.0, 0.0)
        assert cls == "overproduction"
        assert gap_qty == pytest.approx(100.0)
        assert gap_pct is None

    def test_classify_gap_zero_expected_demand_zero_planned(self) -> None:
        """expected_demand == 0 and planned == 0 → balanced."""
        cls, gap_qty, gap_pct = _classify_gap(0.0, 0.0)
        assert cls == "balanced"
        assert gap_qty == 0.0
        assert gap_pct is None


# ===========================================================================
# AnalyzeProductionPlanGapTool integration-style unit tests (mocked DB)
# ===========================================================================


class TestAnalyzeProductionPlanGapTool:
    @pytest.fixture
    def tool(self) -> AnalyzeProductionPlanGapTool:
        return AnalyzeProductionPlanGapTool()

    async def test_schema_contract_required_keys(self, tool: AnalyzeProductionPlanGapTool) -> None:
        """Output must contain horizon_weeks, items, summary, truncated, missing_data."""
        plan_rows = [_plan_row("SKU-001", "WH-001", 100)]
        forecast_rows = [_forecast_row("SKU-001", 100.0)]
        runrate_rows: list[Any] = []

        mock_pool = _make_pool_seq(plan_rows, forecast_rows, runrate_rows)

        with patch("packages.tools.analyze_production_plan_gap_tool.get_pool", return_value=mock_pool):
            result = await tool.handle({}, make_ctx())

        out = result.output
        assert "horizon_weeks" in out
        assert "items" in out
        assert "summary" in out
        assert "truncated" in out
        assert "missing_data" in out

    async def test_overproduction_detected(self, tool: AnalyzeProductionPlanGapTool) -> None:
        """SKU with planned >> forecast should be classified as overproduction."""
        # SKU-026: planned 200/week over 4 weeks = 800 total; demand = ~10/week = 40 total
        plan_rows = [_plan_row("SKU-026", "WH-001", 800)]
        forecast_rows = [_forecast_row("SKU-026", 40.0)]
        runrate_rows: list[Any] = []

        mock_pool = _make_pool_seq(plan_rows, forecast_rows, runrate_rows)

        with patch("packages.tools.analyze_production_plan_gap_tool.get_pool", return_value=mock_pool):
            result = await tool.handle({"horizon_weeks": 4}, make_ctx())

        out = result.output
        assert out["summary"]["overproduction_count"] == 1
        item = out["items"][0]
        assert item["classification"] == "overproduction"
        assert item["sku_id"] == "SKU-026"
        assert item["demand_basis"] == "forecast"
        assert item["gap_qty"] == pytest.approx(760.0)

    async def test_underproduction_detected(self, tool: AnalyzeProductionPlanGapTool) -> None:
        """SKU with planned << forecast should be classified as underproduction."""
        # SKU-001: planned 10/week × 4 = 40 total; demand ~70/week = 280 total
        plan_rows = [_plan_row("SKU-001", "WH-001", 40)]
        forecast_rows = [_forecast_row("SKU-001", 280.0)]
        runrate_rows: list[Any] = []

        mock_pool = _make_pool_seq(plan_rows, forecast_rows, runrate_rows)

        with patch("packages.tools.analyze_production_plan_gap_tool.get_pool", return_value=mock_pool):
            result = await tool.handle({"horizon_weeks": 4}, make_ctx())

        out = result.output
        assert out["summary"]["underproduction_count"] == 1
        item = out["items"][0]
        assert item["classification"] == "underproduction"
        assert item["sku_id"] == "SKU-001"
        assert item["gap_qty"] == pytest.approx(-240.0)

    async def test_balanced_classification(self, tool: AnalyzeProductionPlanGapTool) -> None:
        """SKU with planned within ±25% of forecast → balanced."""
        plan_rows = [_plan_row("SKU-010", "WH-001", 100)]
        forecast_rows = [_forecast_row("SKU-010", 95.0)]
        runrate_rows: list[Any] = []

        mock_pool = _make_pool_seq(plan_rows, forecast_rows, runrate_rows)

        with patch("packages.tools.analyze_production_plan_gap_tool.get_pool", return_value=mock_pool):
            result = await tool.handle({}, make_ctx())

        out = result.output
        assert out["summary"]["balanced_count"] == 1
        assert out["items"][0]["classification"] == "balanced"

    async def test_run_rate_fallback_when_no_forecast(
        self, tool: AnalyzeProductionPlanGapTool
    ) -> None:
        """When no forecast row exists, run-rate demand is used (demand_basis='run_rate')."""
        plan_rows = [_plan_row("SKU-A", "WH-001", 500)]
        forecast_rows: list[Any] = []  # no forecast
        runrate_rows = [_runrate_row("SKU-A", 10.0)]  # avg_daily=10 → 4w×7d=280 expected

        mock_pool = _make_pool_seq(plan_rows, forecast_rows, runrate_rows)

        with patch("packages.tools.analyze_production_plan_gap_tool.get_pool", return_value=mock_pool):
            result = await tool.handle({"horizon_weeks": 4}, make_ctx())

        item = result.output["items"][0]
        assert item["demand_basis"] == "run_rate"
        assert item["expected_demand"] == pytest.approx(280.0)
        assert item["classification"] == "overproduction"

    async def test_missing_data_when_no_demand_history_and_no_forecast(
        self, tool: AnalyzeProductionPlanGapTool
    ) -> None:
        """SKU with planned > 0 but zero demand and no forecast → missing_data entry."""
        plan_rows = [_plan_row("SKU-Z", "WH-001", 100)]
        forecast_rows: list[Any] = []
        runrate_rows: list[Any] = []  # no demand history → avg_daily=0

        mock_pool = _make_pool_seq(plan_rows, forecast_rows, runrate_rows)

        with patch("packages.tools.analyze_production_plan_gap_tool.get_pool", return_value=mock_pool):
            result = await tool.handle({}, make_ctx())

        out = result.output
        assert len(out["missing_data"]) == 1
        assert "SKU-Z" in out["missing_data"][0]

    async def test_db_error_returns_error_key(self, tool: AnalyzeProductionPlanGapTool) -> None:
        """DB error on plan fetch → output contains error key."""
        mock_pool = MagicMock()
        mock_pool.acquire.side_effect = RuntimeError("no database connection")

        with patch("packages.tools.analyze_production_plan_gap_tool.get_pool", return_value=mock_pool):
            result = await tool.handle({}, make_ctx())

        assert "error" in result.output

    async def test_truncated_flag_when_over_cap(self, tool: AnalyzeProductionPlanGapTool) -> None:
        """More than 100 items → truncated=True, items capped at 100."""
        plan_rows = [_plan_row(f"SKU-{i:03d}", "WH-001", 200) for i in range(101)]
        # All forecast at 100 → overproduction for all
        forecast_rows = [_forecast_row(f"SKU-{i:03d}", 100.0) for i in range(101)]
        runrate_rows: list[Any] = []

        mock_pool = _make_pool_seq(plan_rows, forecast_rows, runrate_rows)

        with patch("packages.tools.analyze_production_plan_gap_tool.get_pool", return_value=mock_pool):
            result = await tool.handle({}, make_ctx())

        out = result.output
        assert out["truncated"] is True
        assert len(out["items"]) == 100

    async def test_summary_counts_reflect_full_list_when_truncated(
        self, tool: AnalyzeProductionPlanGapTool
    ) -> None:
        """With >100 items, truncated=True AND summary counts sum to the pre-cap total."""
        # 101 items: 60 overproduction (planned=200, forecast=100) +
        #            30 underproduction (planned=50, forecast=100)  +
        #            11 balanced        (planned=110, forecast=100)
        n_over = 60
        n_under = 30
        n_balanced = 11
        total = n_over + n_under + n_balanced  # 101

        plan_rows = (
            [_plan_row(f"O-{i:03d}", "WH-001", 200) for i in range(n_over)]
            + [_plan_row(f"U-{i:03d}", "WH-001", 50) for i in range(n_under)]
            + [_plan_row(f"B-{i:03d}", "WH-001", 110) for i in range(n_balanced)]
        )
        forecast_rows = (
            [_forecast_row(f"O-{i:03d}", 100.0) for i in range(n_over)]
            + [_forecast_row(f"U-{i:03d}", 100.0) for i in range(n_under)]
            + [_forecast_row(f"B-{i:03d}", 100.0) for i in range(n_balanced)]
        )
        runrate_rows: list[Any] = []

        mock_pool = _make_pool_seq(plan_rows, forecast_rows, runrate_rows)

        with patch(
            "packages.tools.analyze_production_plan_gap_tool.get_pool",
            return_value=mock_pool,
        ):
            result = await tool.handle({}, make_ctx())

        out = result.output
        assert out["truncated"] is True
        assert len(out["items"]) == 100

        s = out["summary"]
        # Counts must reflect the full 101-item list, not the 100-item cap.
        assert s["overproduction_count"] == n_over
        assert s["underproduction_count"] == n_under
        assert s["balanced_count"] == n_balanced
        assert s["overproduction_count"] + s["underproduction_count"] + s["balanced_count"] == total

    async def test_empty_plan_returns_empty_items(
        self, tool: AnalyzeProductionPlanGapTool
    ) -> None:
        """No production_plan rows within horizon → empty items, not truncated."""
        mock_pool = _make_pool_seq([], [], [])

        with patch("packages.tools.analyze_production_plan_gap_tool.get_pool", return_value=mock_pool):
            result = await tool.handle({}, make_ctx())

        out = result.output
        assert out["items"] == []
        assert out["truncated"] is False

    async def test_horizon_weeks_default_is_4(
        self, tool: AnalyzeProductionPlanGapTool
    ) -> None:
        """horizon_weeks defaults to 4 when not specified."""
        mock_pool = _make_pool_seq([], [], [])

        with patch("packages.tools.analyze_production_plan_gap_tool.get_pool", return_value=mock_pool):
            result = await tool.handle({}, make_ctx())

        assert result.output["horizon_weeks"] == 4


# ===========================================================================
# IdentifyBindingConstraintTool unit tests
# ===========================================================================


class TestIdentifyBindingConstraintTool:
    @pytest.fixture
    def tool(self) -> Any:
        from packages.tools.identify_binding_constraint_tool import IdentifyBindingConstraintTool
        return IdentifyBindingConstraintTool()

    def _make_cap_pool(
        self,
        cost_rows: list[Any],
        cap_rows: list[Any],
        sku_in_plan_rows: list[Any],
        supply_rows: list[Any],
        inv_rows: list[Any],
    ) -> MagicMock:
        """Build a pool mock for the five sequential fetch calls in identify_binding_constraint."""
        mock_conn = AsyncMock()
        # Order: cost_map, capacity+plan aggregate, per-location sku rows (one per overload),
        #        supply gap, inventory stockout
        mock_conn.fetch.side_effect = [
            cost_rows,
            cap_rows,
            sku_in_plan_rows,
            supply_rows,
            inv_rows,
        ]
        mock_pool = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
        return mock_pool

    async def test_schema_contract_required_keys(self, tool: Any) -> None:
        """Output must contain constraints, truncated, missing_data."""
        mock_pool = _make_pool_seq([], [], [], [])

        with patch(
            "packages.tools.identify_binding_constraint_tool.get_pool",
            return_value=mock_pool,
        ):
            result = await tool.handle({}, make_ctx())

        out = result.output
        assert "constraints" in out
        assert "truncated" in out
        assert "missing_data" in out

    async def test_capacity_overload_produces_non_zero_impact(self, tool: Any) -> None:
        """A location-week with planned > capacity and known stockout cost → positive impact."""
        # cost_map: SKU-001 has stockout_cost=500
        cost_rows = [{"sku_id": "SKU-001", "stockout_cost": 500.0}]
        # capacity: WH-001 current week, capacity=2000, planned=2250 → overload=250
        cap_rows = [{
            "location_id": "WH-001",
            "week_start": "2026-06-09",
            "capacity_units": 2000,
            "planned_units": 2250,
        }]
        # SKUs in plan for WH-001 that week
        sku_in_plan_rows = [{"sku_id": "SKU-001"}]
        # no supply gaps, no stockout
        supply_rows: list[Any] = []
        inv_rows: list[Any] = []

        mock_conn = AsyncMock()
        mock_conn.fetch.side_effect = [
            cost_rows, cap_rows, sku_in_plan_rows, supply_rows, inv_rows
        ]
        mock_pool = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "packages.tools.identify_binding_constraint_tool.get_pool",
            return_value=mock_pool,
        ):
            result = await tool.handle({}, make_ctx())

        out = result.output
        constraints = out["constraints"]
        cap_c = [c for c in constraints if c["constraint_type"] == "production_capacity"]
        assert len(cap_c) == 1
        assert cap_c[0]["impact_estimate"] > 0
        assert cap_c[0]["evidence"]["overload_units"] == pytest.approx(250.0)
        assert cap_c[0]["evidence"]["avg_stockout_cost"] == pytest.approx(500.0)
        assert cap_c[0]["impact_estimate"] == pytest.approx(250.0 * 500.0)

    async def test_no_overload_when_planned_within_capacity(self, tool: Any) -> None:
        """Location-week with planned <= capacity → no production_capacity constraint."""
        cost_rows = [{"sku_id": "SKU-001", "stockout_cost": 500.0}]
        cap_rows = [{
            "location_id": "WH-001",
            "week_start": "2026-06-09",
            "capacity_units": 2000,
            "planned_units": 1500,
        }]
        supply_rows: list[Any] = []
        inv_rows: list[Any] = []

        # No sku_in_plan call because no overload
        mock_conn = AsyncMock()
        mock_conn.fetch.side_effect = [cost_rows, cap_rows, supply_rows, inv_rows]
        mock_pool = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "packages.tools.identify_binding_constraint_tool.get_pool",
            return_value=mock_pool,
        ):
            result = await tool.handle({}, make_ctx())

        cap_c = [
            c for c in result.output["constraints"]
            if c["constraint_type"] == "production_capacity"
        ]
        assert cap_c == []

    async def test_supply_gap_constraint_recorded(self, tool: Any) -> None:
        """SKU with supply gap > 0 and known stockout cost → supply_gap constraint record."""
        cost_rows = [{"sku_id": "SKU-A", "stockout_cost": 200.0}]
        # no capacity overload
        cap_rows: list[Any] = []
        # supply gap: on_hand=10, incoming=5, avg_daily=5 → demand=35, total=15, gap=20
        supply_rows = [{
            "sku_id": "SKU-A",
            "on_hand": 10.0,
            "incoming_qty": 5.0,
            "avg_daily": 5.0,
        }]
        inv_rows: list[Any] = []

        mock_conn = AsyncMock()
        mock_conn.fetch.side_effect = [cost_rows, cap_rows, supply_rows, inv_rows]
        mock_pool = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "packages.tools.identify_binding_constraint_tool.get_pool",
            return_value=mock_pool,
        ):
            result = await tool.handle({}, make_ctx())

        sg_c = [c for c in result.output["constraints"] if c["constraint_type"] == "supply_gap"]
        assert len(sg_c) == 1
        assert sg_c[0]["subject"] == "SKU-A"
        # demand=5*7=35, total=15, gap=20, impact=20*200=4000
        assert sg_c[0]["impact_estimate"] == pytest.approx(20.0 * 200.0)
        assert sg_c[0]["evidence"]["supply_gap_units"] == pytest.approx(20.0)

    async def test_inventory_stockout_constraint_recorded(self, tool: Any) -> None:
        """Critical-risk SKU with shortfall and known cost → inventory_stockout record."""
        cost_rows = [{"sku_id": "SKU-B", "stockout_cost": 300.0}]
        cap_rows: list[Any] = []
        supply_rows: list[Any] = []
        # on_hand=0, avg_daily=10, incoming=5 → projected=-65 (critical) shortfall=65
        inv_rows = [{
            "sku_id": "SKU-B",
            "on_hand_qty": 0.0,
            "avg_daily": 10.0,
            "incoming_supply": 5.0,
        }]

        mock_conn = AsyncMock()
        mock_conn.fetch.side_effect = [cost_rows, cap_rows, supply_rows, inv_rows]
        mock_pool = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "packages.tools.identify_binding_constraint_tool.get_pool",
            return_value=mock_pool,
        ):
            result = await tool.handle({}, make_ctx())

        inv_c = [
            c for c in result.output["constraints"]
            if c["constraint_type"] == "inventory_stockout"
        ]
        assert len(inv_c) == 1
        assert inv_c[0]["subject"] == "SKU-B"
        # projected = 0 + 5 - 70 = -65; shortfall=65; impact=65*300=19500
        assert inv_c[0]["impact_estimate"] == pytest.approx(65.0 * 300.0)

    async def test_ranking_higher_impact_first(self, tool: Any) -> None:
        """Constraint with higher impact_estimate appears before lower-impact constraint."""
        cost_rows = [
            {"sku_id": "SKU-A", "stockout_cost": 100.0},
            {"sku_id": "SKU-B", "stockout_cost": 100.0},
        ]
        cap_rows: list[Any] = []
        # supply gap: SKU-A gap=50 → impact=5000; SKU-B gap=10 → impact=1000
        supply_rows = [
            {"sku_id": "SKU-A", "on_hand": 0.0, "incoming_qty": 0.0, "avg_daily": 50.0 / 7},
            {"sku_id": "SKU-B", "on_hand": 60.0, "incoming_qty": 0.0, "avg_daily": 10.0},
        ]
        inv_rows: list[Any] = []

        mock_conn = AsyncMock()
        mock_conn.fetch.side_effect = [cost_rows, cap_rows, supply_rows, inv_rows]
        mock_pool = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "packages.tools.identify_binding_constraint_tool.get_pool",
            return_value=mock_pool,
        ):
            result = await tool.handle({}, make_ctx())

        constraints = result.output["constraints"]
        sg_constraints = [c for c in constraints if c["constraint_type"] == "supply_gap"]
        assert len(sg_constraints) >= 1
        # Highest impact must come first
        impacts = [c["impact_estimate"] for c in sg_constraints]
        assert impacts == sorted(impacts, reverse=True)

    async def test_deterministic_tiebreak_subject_ascending(self, tool: Any) -> None:
        """When impact_estimate is equal, constraints are ordered by subject ASC."""
        cost_rows = [
            {"sku_id": "SKU-Z", "stockout_cost": 100.0},
            {"sku_id": "SKU-A", "stockout_cost": 100.0},
        ]
        cap_rows: list[Any] = []
        # Both have gap=7 → same impact
        supply_rows = [
            {"sku_id": "SKU-Z", "on_hand": 0.0, "incoming_qty": 0.0, "avg_daily": 1.0},
            {"sku_id": "SKU-A", "on_hand": 0.0, "incoming_qty": 0.0, "avg_daily": 1.0},
        ]
        inv_rows: list[Any] = []

        mock_conn = AsyncMock()
        mock_conn.fetch.side_effect = [cost_rows, cap_rows, supply_rows, inv_rows]
        mock_pool = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "packages.tools.identify_binding_constraint_tool.get_pool",
            return_value=mock_pool,
        ):
            result = await tool.handle({}, make_ctx())

        subjects = [c["subject"] for c in result.output["constraints"]]
        assert subjects == sorted(subjects)

    async def test_missing_data_when_no_cost_master_row(self, tool: Any) -> None:
        """SKU without cost_master row → missing_data entry, impact_estimate = 0."""
        cost_rows: list[Any] = []  # no cost rows
        cap_rows: list[Any] = []
        supply_rows = [{
            "sku_id": "SKU-X",
            "on_hand": 0.0,
            "incoming_qty": 0.0,
            "avg_daily": 10.0,
        }]
        inv_rows: list[Any] = []

        mock_conn = AsyncMock()
        mock_conn.fetch.side_effect = [cost_rows, cap_rows, supply_rows, inv_rows]
        mock_pool = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "packages.tools.identify_binding_constraint_tool.get_pool",
            return_value=mock_pool,
        ):
            result = await tool.handle({}, make_ctx())

        out = result.output
        assert any("SKU-X" in note for note in out["missing_data"])
        sg = [c for c in out["constraints"] if c["subject"] == "SKU-X"]
        assert len(sg) == 1
        assert sg[0]["impact_estimate"] == 0.0

    async def test_db_error_on_cost_map_returns_error(self, tool: Any) -> None:
        """DB error during cost_map fetch → output contains error key."""
        mock_pool = MagicMock()
        mock_pool.acquire.side_effect = RuntimeError("no database connection")

        with patch(
            "packages.tools.identify_binding_constraint_tool.get_pool",
            return_value=mock_pool,
        ):
            result = await tool.handle({}, make_ctx())

        assert "error" in result.output

    async def test_truncated_flag_when_over_cap(self, tool: Any) -> None:
        """More than 50 constraints → truncated=True, list capped at 50."""
        # Generate 51 supply-gap constraints
        cost_rows = [{"sku_id": f"SKU-{i:03d}", "stockout_cost": 10.0} for i in range(51)]
        cap_rows: list[Any] = []
        supply_rows = [
            {"sku_id": f"SKU-{i:03d}", "on_hand": 0.0, "incoming_qty": 0.0, "avg_daily": 1.0}
            for i in range(51)
        ]
        inv_rows: list[Any] = []

        mock_conn = AsyncMock()
        mock_conn.fetch.side_effect = [cost_rows, cap_rows, supply_rows, inv_rows]
        mock_pool = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "packages.tools.identify_binding_constraint_tool.get_pool",
            return_value=mock_pool,
        ):
            result = await tool.handle({}, make_ctx())

        out = result.output
        assert out["truncated"] is True
        assert len(out["constraints"]) == 50

    async def test_no_constraints_when_all_within_limits(self, tool: Any) -> None:
        """No overload, no supply gap, no stockout → empty constraints list."""
        cost_rows = [{"sku_id": "SKU-A", "stockout_cost": 100.0}]
        cap_rows: list[Any] = []
        supply_rows = [{
            "sku_id": "SKU-A",
            "on_hand": 1000.0,
            "incoming_qty": 500.0,
            "avg_daily": 5.0,
        }]  # total=1500 >> demand=35; no gap
        inv_rows = [{
            "sku_id": "SKU-A",
            "on_hand_qty": 1000.0,
            "avg_daily": 5.0,
            "incoming_supply": 500.0,
        }]  # projected=1465 >> 0; no stockout

        mock_conn = AsyncMock()
        mock_conn.fetch.side_effect = [cost_rows, cap_rows, supply_rows, inv_rows]
        mock_pool = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "packages.tools.identify_binding_constraint_tool.get_pool",
            return_value=mock_pool,
        ):
            result = await tool.handle({}, make_ctx())

        assert result.output["constraints"] == []
        assert result.output["truncated"] is False


# ===========================================================================
# T-559 Wiring: registry registration
# ===========================================================================


def test_analyze_production_plan_gap_registered_in_registry() -> None:
    """analyze_production_plan_gap must appear in create_tool_registry() (T-559)."""
    from packages.tools import create_tool_registry
    registry = create_tool_registry()
    assert "analyze_production_plan_gap" in registry._tools


def test_identify_binding_constraint_registered_in_registry() -> None:
    """identify_binding_constraint must appear in create_tool_registry() (T-559)."""
    from packages.tools import create_tool_registry
    registry = create_tool_registry()
    assert "identify_binding_constraint" in registry._tools


def test_analyze_production_plan_gap_safety_level_is_read_only() -> None:
    """analyze_production_plan_gap must be read_only."""
    from packages.tools.analyze_production_plan_gap_tool import AnalyzeProductionPlanGapTool
    assert AnalyzeProductionPlanGapTool.safety_level == "read_only"


def test_identify_binding_constraint_safety_level_is_read_only() -> None:
    """identify_binding_constraint must be read_only."""
    from packages.tools.identify_binding_constraint_tool import IdentifyBindingConstraintTool
    assert IdentifyBindingConstraintTool.safety_level == "read_only"
