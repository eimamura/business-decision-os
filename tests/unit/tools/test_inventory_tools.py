from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from packages.tools.base import ToolContext
from packages.tools.inventory_atp_tool import GetAvailableToPromiseTool
from packages.tools.inventory_doi_tool import CalculateDaysOfInventoryTool
from packages.tools.inventory_excess_tool import CalculateExcessInventoryRiskTool
from packages.tools.inventory_stockout_risk_tool import CalculateStockoutRiskTool


def make_ctx() -> ToolContext:
    return ToolContext(
        session_id=uuid4(),
        agent_step_id=uuid4(),
        specialist_role="inventory",
        actor="test",
        correlation_id=uuid4(),
    )


def make_pool(side_effects: list) -> MagicMock:
    mock_conn = AsyncMock()
    mock_conn.fetchrow.side_effect = side_effects
    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_pool


# ---------------------------------------------------------------------------
# T-235: CalculateDaysOfInventoryTool
# ---------------------------------------------------------------------------


async def test_doi_reorder_signal_true_when_doi_below_threshold():
    # on_hand=50, avg_daily=5 → doi=10; lead_time=14 → threshold=14 → signal=True
    on_hand_row = {"on_hand_qty": 50}
    demand_row = {"avg_daily": 5}
    sku_row = {"lead_time_days_mean": 14}

    mock_pool = make_pool([on_hand_row, demand_row, sku_row])

    with patch("packages.tools.inventory_doi_tool.get_pool", return_value=mock_pool):
        tool = CalculateDaysOfInventoryTool()
        result = await tool.handle({"sku_id": "SKU-A"}, make_ctx())

    assert result.output["days_of_inventory"] == pytest.approx(10.0)
    assert result.output["reorder_signal"] is True
    assert result.output["warehouse_id"] is None


async def test_doi_reorder_signal_false_when_doi_above_threshold():
    # on_hand=300, avg_daily=5 → doi=60; lead_time=7 → threshold=14 → signal=False
    on_hand_row = {"on_hand_qty": 300}
    demand_row = {"avg_daily": 5}
    sku_row = {"lead_time_days_mean": 7}

    mock_pool = make_pool([on_hand_row, demand_row, sku_row])

    with patch("packages.tools.inventory_doi_tool.get_pool", return_value=mock_pool):
        tool = CalculateDaysOfInventoryTool()
        result = await tool.handle({"sku_id": "SKU-B"}, make_ctx())

    assert result.output["days_of_inventory"] == pytest.approx(60.0)
    assert result.output["reorder_signal"] is False


async def test_doi_none_demand_returns_null_doi_and_no_signal():
    # avg_daily=None → doi=None, reorder_signal=False
    on_hand_row = {"on_hand_qty": 100}
    demand_row = {"avg_daily": None}
    sku_row = {"lead_time_days_mean": None}

    mock_pool = make_pool([on_hand_row, demand_row, sku_row])

    with patch("packages.tools.inventory_doi_tool.get_pool", return_value=mock_pool):
        tool = CalculateDaysOfInventoryTool()
        result = await tool.handle({"sku_id": "SKU-C"}, make_ctx())

    assert result.output["days_of_inventory"] is None
    assert result.output["avg_daily_demand"] is None
    assert result.output["reorder_signal"] is False


async def test_doi_warehouse_id_passed_through():
    on_hand_row = {"on_hand_qty": 20}
    demand_row = {"avg_daily": 2}
    sku_row = {"lead_time_days_mean": 10}

    mock_pool = make_pool([on_hand_row, demand_row, sku_row])

    with patch("packages.tools.inventory_doi_tool.get_pool", return_value=mock_pool):
        tool = CalculateDaysOfInventoryTool()
        result = await tool.handle({"sku_id": "SKU-D", "warehouse_id": "WH-01"}, make_ctx())

    assert result.output["warehouse_id"] == "WH-01"


async def test_doi_db_error_returns_error_key():
    with patch(
        "packages.tools.inventory_doi_tool.get_pool",
        side_effect=RuntimeError("DATABASE_URL not configured"),
    ):
        tool = CalculateDaysOfInventoryTool()
        result = await tool.handle({"sku_id": "SKU-ERR"}, make_ctx())

    assert "error" in result.output
    assert "database" in result.output["error"].lower()


# ---------------------------------------------------------------------------
# T-236: CalculateStockoutRiskTool
# ---------------------------------------------------------------------------


async def test_stockout_risk_low_when_ample_stock():
    # on_hand=1000, avg_daily=5 → forecast=150 over 30d; incoming=0 → ending=850
    # ratio = 850/150 ≈ 5.67 ≥ 0.5 → "low"
    on_hand_row = {"on_hand_qty": 1000}
    demand_row = {"avg_daily": 5}
    supply_row = {"incoming_supply": 0}

    mock_pool = make_pool([on_hand_row, demand_row, supply_row])

    with patch(
        "packages.tools.inventory_stockout_risk_tool.get_pool", return_value=mock_pool
    ):
        tool = CalculateStockoutRiskTool()
        result = await tool.handle({"sku_id": "SKU-A", "horizon_days": 30}, make_ctx())

    assert result.output["risk_level"] == "low"
    assert result.output["stockout_date_estimate"] is None
    assert result.output["projected_ending_stock"] > 0


async def test_stockout_risk_critical_when_stock_negative():
    # on_hand=10, avg_daily=10 → forecast=300 over 30d; incoming=0 → ending=-290 → "critical"
    on_hand_row = {"on_hand_qty": 10}
    demand_row = {"avg_daily": 10}
    supply_row = {"incoming_supply": 0}

    mock_pool = make_pool([on_hand_row, demand_row, supply_row])

    with patch(
        "packages.tools.inventory_stockout_risk_tool.get_pool", return_value=mock_pool
    ):
        tool = CalculateStockoutRiskTool()
        result = await tool.handle({"sku_id": "SKU-B", "horizon_days": 30}, make_ctx())

    assert result.output["risk_level"] == "critical"
    assert result.output["stockout_date_estimate"] is not None
    # stockout in 1 day: (10+0)/10 = 1 day from today
    expected_date = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
    assert result.output["stockout_date_estimate"] == expected_date


async def test_stockout_risk_none_when_zero_demand():
    # avg_daily=0 → demand_forecast=0 → risk_level="none"
    on_hand_row = {"on_hand_qty": 50}
    demand_row = {"avg_daily": 0}
    supply_row = {"incoming_supply": 0}

    mock_pool = make_pool([on_hand_row, demand_row, supply_row])

    with patch(
        "packages.tools.inventory_stockout_risk_tool.get_pool", return_value=mock_pool
    ):
        tool = CalculateStockoutRiskTool()
        result = await tool.handle({"sku_id": "SKU-C"}, make_ctx())

    assert result.output["risk_level"] == "none"
    assert result.output["stockout_date_estimate"] is None


async def test_stockout_risk_default_horizon_is_30():
    on_hand_row = {"on_hand_qty": 200}
    demand_row = {"avg_daily": 5}
    supply_row = {"incoming_supply": 0}

    mock_pool = make_pool([on_hand_row, demand_row, supply_row])

    with patch(
        "packages.tools.inventory_stockout_risk_tool.get_pool", return_value=mock_pool
    ):
        tool = CalculateStockoutRiskTool()
        result = await tool.handle({"sku_id": "SKU-D"}, make_ctx())

    assert result.output["horizon_days"] == 30


async def test_stockout_risk_db_error_returns_error_key():
    with patch(
        "packages.tools.inventory_stockout_risk_tool.get_pool",
        side_effect=RuntimeError("DATABASE_URL not configured"),
    ):
        tool = CalculateStockoutRiskTool()
        result = await tool.handle({"sku_id": "SKU-ERR"}, make_ctx())

    assert "error" in result.output


# ---------------------------------------------------------------------------
# T-237: CalculateExcessInventoryRiskTool
# ---------------------------------------------------------------------------


async def test_excess_high_risk_when_stock_far_above_demand():
    # on_hand=1000, avg_daily=2 → excess_units=1000-60=940; excess_days=940/2=470 > 60 → "high"
    on_hand_row = {"on_hand_qty": 1000}
    demand_row = {"avg_daily": 2}

    mock_pool = make_pool([on_hand_row, demand_row])

    with patch("packages.tools.inventory_excess_tool.get_pool", return_value=mock_pool):
        tool = CalculateExcessInventoryRiskTool()
        result = await tool.handle({"sku_id": "SKU-A"}, make_ctx())

    assert result.output["excess_risk_level"] == "high"
    assert result.output["excess_units"] == pytest.approx(940.0)
    assert result.output["excess_days"] == pytest.approx(470.0)


async def test_excess_none_risk_when_stock_below_30d_demand():
    # on_hand=50, avg_daily=2 → normal=60 → excess_units=50-60=-10 ≤ 0 → "none"
    on_hand_row = {"on_hand_qty": 50}
    demand_row = {"avg_daily": 2}

    mock_pool = make_pool([on_hand_row, demand_row])

    with patch("packages.tools.inventory_excess_tool.get_pool", return_value=mock_pool):
        tool = CalculateExcessInventoryRiskTool()
        result = await tool.handle({"sku_id": "SKU-B"}, make_ctx())

    assert result.output["excess_risk_level"] == "none"
    assert result.output["excess_days"] is None


async def test_excess_unknown_when_no_demand_data():
    # avg_daily=None → "unknown"
    on_hand_row = {"on_hand_qty": 200}
    demand_row = {"avg_daily": None}

    mock_pool = make_pool([on_hand_row, demand_row])

    with patch("packages.tools.inventory_excess_tool.get_pool", return_value=mock_pool):
        tool = CalculateExcessInventoryRiskTool()
        result = await tool.handle({"sku_id": "SKU-C"}, make_ctx())

    assert result.output["excess_risk_level"] == "unknown"
    assert result.output["excess_units"] is None
    assert result.output["avg_daily_demand"] is None


async def test_excess_medium_risk():
    # on_hand=200, avg_daily=3 → normal=90 → excess=110; excess_days≈36.67 (30<36.67≤60) → "medium"
    on_hand_row = {"on_hand_qty": 200}
    demand_row = {"avg_daily": 3}

    mock_pool = make_pool([on_hand_row, demand_row])

    with patch("packages.tools.inventory_excess_tool.get_pool", return_value=mock_pool):
        tool = CalculateExcessInventoryRiskTool()
        result = await tool.handle({"sku_id": "SKU-D"}, make_ctx())

    assert result.output["excess_risk_level"] == "medium"


async def test_excess_db_error_returns_error_key():
    with patch(
        "packages.tools.inventory_excess_tool.get_pool",
        side_effect=RuntimeError("DATABASE_URL not configured"),
    ):
        tool = CalculateExcessInventoryRiskTool()
        result = await tool.handle({"sku_id": "SKU-ERR"}, make_ctx())

    assert "error" in result.output


# ---------------------------------------------------------------------------
# T-238: GetAvailableToPromiseTool
# ---------------------------------------------------------------------------


async def test_atp_sums_on_hand_and_incoming():
    # on_hand=300, incoming=200 → atp=500
    on_hand_row = {"on_hand_qty": 300}
    supply_row = {"on_order_incoming": 200}

    mock_pool = make_pool([on_hand_row, supply_row])

    with patch("packages.tools.inventory_atp_tool.get_pool", return_value=mock_pool):
        tool = GetAvailableToPromiseTool()
        result = await tool.handle({"sku_id": "SKU-A"}, make_ctx())

    assert result.output["atp_units"] == pytest.approx(500.0)
    assert result.output["on_hand_qty"] == pytest.approx(300.0)
    assert result.output["on_order_incoming"] == pytest.approx(200.0)
    assert result.output["warehouse_id"] is None


async def test_atp_date_horizon_is_30_days_from_today():
    on_hand_row = {"on_hand_qty": 100}
    supply_row = {"on_order_incoming": 50}

    mock_pool = make_pool([on_hand_row, supply_row])

    with patch("packages.tools.inventory_atp_tool.get_pool", return_value=mock_pool):
        tool = GetAvailableToPromiseTool()
        result = await tool.handle({"sku_id": "SKU-B"}, make_ctx())

    expected_horizon = (datetime.date.today() + datetime.timedelta(days=30)).isoformat()
    assert result.output["atp_date_horizon"] == expected_horizon


async def test_atp_warehouse_id_passed_through():
    on_hand_row = {"on_hand_qty": 50}
    supply_row = {"on_order_incoming": 10}

    mock_pool = make_pool([on_hand_row, supply_row])

    with patch("packages.tools.inventory_atp_tool.get_pool", return_value=mock_pool):
        tool = GetAvailableToPromiseTool()
        result = await tool.handle({"sku_id": "SKU-C", "warehouse_id": "WH-02"}, make_ctx())

    assert result.output["warehouse_id"] == "WH-02"
    assert result.output["atp_units"] == pytest.approx(60.0)


async def test_atp_db_error_returns_error_key():
    with patch(
        "packages.tools.inventory_atp_tool.get_pool",
        side_effect=RuntimeError("DATABASE_URL not configured"),
    ):
        tool = GetAvailableToPromiseTool()
        result = await tool.handle({"sku_id": "SKU-ERR"}, make_ctx())

    assert "error" in result.output
    assert "database" in result.output["error"].lower()
