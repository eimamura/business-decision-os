from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from packages.tools.base import ToolContext
from packages.tools.finance_expedite_cost_tool import CalculateExpediteCostTool
from packages.tools.finance_scenario_tool import CompareCostScenariosTool


def make_ctx() -> ToolContext:
    return ToolContext(
        session_id=uuid4(),
        agent_step_id=uuid4(),
        specialist_role="finance_impact",
        actor="test",
        correlation_id=uuid4(),
    )


def make_fetchrow_pool(return_value: object) -> MagicMock:
    mock_conn = AsyncMock()
    mock_conn.fetchrow.return_value = return_value
    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_pool


# ---------------------------------------------------------------------------
# CalculateExpediteCostTool
# ---------------------------------------------------------------------------


async def test_expedite_cost_computes_with_default_multiplier():
    # ordering_cost=10.0, stockout_cost=25.0, expedite_units=100, multiplier=2.0 (default)
    # base = 100 * 10 = 1000; premium = 1000 * (2.0 - 1.0) = 1000; total = 1000 * 2.0 = 2000
    # stockout_total = 100 * 25 = 2500; expedite(2000) < stockout(2500) → expedite is cheaper
    mock_row = {"ordering_cost": 10.0, "stockout_cost": 25.0}
    mock_pool = make_fetchrow_pool(mock_row)

    with patch("packages.tools.finance_expedite_cost_tool.get_pool", return_value=mock_pool):
        tool = CalculateExpediteCostTool()
        result = await tool.handle({"sku_id": "SKU-A", "expedite_units": 100}, make_ctx())

    assert result.output["base_ordering_cost"] == 1000.0
    assert result.output["expedite_premium"] == 1000.0
    assert result.output["total_expedite_cost"] == 2000.0
    assert "expedite is cheaper than stockout" in result.output["cost_vs_stockout_comparison"]


async def test_expedite_cost_with_custom_multiplier():
    # ordering_cost=10.0, stockout_cost=8.0, expedite_units=100, multiplier=1.5
    # base = 100 * 10 = 1000; premium = 1000 * (1.5 - 1.0) = 500; total = 1000 * 1.5 = 1500
    # stockout_total = 100 * 8.0 = 800; expedite(1500) > stockout(800) → stockout is cheaper
    mock_row = {"ordering_cost": 10.0, "stockout_cost": 8.0}
    mock_pool = make_fetchrow_pool(mock_row)

    with patch("packages.tools.finance_expedite_cost_tool.get_pool", return_value=mock_pool):
        tool = CalculateExpediteCostTool()
        result = await tool.handle(
            {"sku_id": "SKU-B", "expedite_units": 100, "expedite_multiplier": 1.5},
            make_ctx(),
        )

    assert result.output["base_ordering_cost"] == 1000.0
    assert result.output["expedite_premium"] == 500.0
    assert result.output["total_expedite_cost"] == 1500.0
    assert "stockout is cheaper than expedite" in result.output["cost_vs_stockout_comparison"]


async def test_expedite_cost_db_error_returns_error_key():
    with patch(
        "packages.tools.finance_expedite_cost_tool.get_pool",
        side_effect=RuntimeError("database_url not set"),
    ):
        tool = CalculateExpediteCostTool()
        result = await tool.handle({"sku_id": "SKU-C", "expedite_units": 50}, make_ctx())

    assert "error" in result.output


# ---------------------------------------------------------------------------
# CompareCostScenariosTool
# ---------------------------------------------------------------------------


async def test_compare_scenarios_recommends_lowest_cost():
    # stockout_cost=20.0, ordering_cost=5.0, shortage_units=100
    # do_nothing = 100 * 20 = 2000
    # full_expedite = 100 * 5 * 2.0 = 1000
    # partial_fulfill = 100 * 0.5 * 5 * 2.0 + 100 * 0.5 * 20 = 500 + 1000 = 1500
    # recommended = full_expedite (lowest)
    mock_row = {"stockout_cost": 20.0, "ordering_cost": 5.0, "holding_cost": 0.0}
    mock_pool = make_fetchrow_pool(mock_row)

    with patch("packages.tools.finance_scenario_tool.get_pool", return_value=mock_pool):
        tool = CompareCostScenariosTool()
        result = await tool.handle({"sku_id": "SKU-D", "shortage_units": 100}, make_ctx())

    scenarios_by_name = {s["name"]: s for s in result.output["scenarios"]}
    assert scenarios_by_name["do_nothing"]["total_cost"] == 2000.0
    assert scenarios_by_name["full_expedite"]["total_cost"] == 1000.0
    assert scenarios_by_name["partial_fulfill"]["total_cost"] == 1500.0
    assert result.output["recommended_scenario"] == "full_expedite"
    assert result.output["recommendation_reason"] is not None


async def test_compare_scenarios_missing_sku_returns_null_costs():
    mock_pool = make_fetchrow_pool(None)

    with patch("packages.tools.finance_scenario_tool.get_pool", return_value=mock_pool):
        tool = CompareCostScenariosTool()
        result = await tool.handle({"sku_id": "SKU-NONE", "shortage_units": 50}, make_ctx())

    for scenario in result.output["scenarios"]:
        assert scenario["total_cost"] is None
    assert result.output["recommended_scenario"] is None
    assert "error" not in result.output


async def test_compare_scenarios_db_error_returns_error_key():
    with patch(
        "packages.tools.finance_scenario_tool.get_pool",
        side_effect=RuntimeError("database_url not set"),
    ):
        tool = CompareCostScenariosTool()
        result = await tool.handle({"sku_id": "SKU-E", "shortage_units": 10}, make_ctx())

    assert "error" in result.output
