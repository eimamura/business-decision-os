from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from packages.tools.base import ToolContext
from packages.tools.finance_holding_cost_tool import CalculateHoldingCostImpactTool
from packages.tools.finance_stockout_cost_tool import CalculateStockoutCostImpactTool


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
# CalculateHoldingCostImpactTool
# ---------------------------------------------------------------------------


async def test_holding_cost_computes_correctly():
    mock_row = {
        "holding_cost": 5.0,
        "period_start": datetime.date(2026, 1, 1),
    }
    mock_pool = make_fetchrow_pool(mock_row)

    with patch("packages.tools.finance_holding_cost_tool.get_pool", return_value=mock_pool):
        tool = CalculateHoldingCostImpactTool()
        result = await tool.handle({"sku_id": "SKU-X", "excess_units": 100}, make_ctx())

    assert result.output["unit_holding_cost"] == 5.0
    assert result.output["total_holding_cost"] == 500.0
    assert result.output["annualized_holding_cost"] == 6000.0
    assert result.output["period_label"] == "2026-01-01"


async def test_holding_cost_missing_sku_returns_nulls():
    mock_pool = make_fetchrow_pool(None)

    with patch("packages.tools.finance_holding_cost_tool.get_pool", return_value=mock_pool):
        tool = CalculateHoldingCostImpactTool()
        result = await tool.handle({"sku_id": "SKU-MISSING", "excess_units": 50}, make_ctx())

    assert result.output["unit_holding_cost"] is None
    assert result.output["total_holding_cost"] is None
    assert result.output["annualized_holding_cost"] is None
    assert result.output["period_label"] is None
    assert "error" not in result.output


async def test_holding_cost_db_error_returns_error_key():
    with patch(
        "packages.tools.finance_holding_cost_tool.get_pool",
        side_effect=RuntimeError("database_url not set"),
    ):
        tool = CalculateHoldingCostImpactTool()
        result = await tool.handle({"sku_id": "SKU-Y", "excess_units": 10}, make_ctx())

    assert "error" in result.output


# ---------------------------------------------------------------------------
# CalculateStockoutCostImpactTool
# ---------------------------------------------------------------------------


async def test_stockout_cost_computes_correctly():
    mock_row = {
        "stockout_cost": 8.0,
        "cogs": 15.0,
        "period_start": datetime.date(2026, 2, 1),
    }
    mock_pool = make_fetchrow_pool(mock_row)

    with patch("packages.tools.finance_stockout_cost_tool.get_pool", return_value=mock_pool):
        tool = CalculateStockoutCostImpactTool()
        result = await tool.handle({"sku_id": "SKU-A", "shortage_units": 50}, make_ctx())

    assert result.output["unit_stockout_cost"] == 8.0
    assert result.output["total_stockout_cost"] == 400.0
    assert result.output["opportunity_cost_estimate"] == 750.0
    assert result.output["period_label"] == "2026-02-01"


async def test_stockout_cost_missing_sku_returns_nulls():
    mock_pool = make_fetchrow_pool(None)

    with patch("packages.tools.finance_stockout_cost_tool.get_pool", return_value=mock_pool):
        tool = CalculateStockoutCostImpactTool()
        result = await tool.handle({"sku_id": "SKU-NONE", "shortage_units": 20}, make_ctx())

    assert result.output["unit_stockout_cost"] is None
    assert result.output["total_stockout_cost"] is None
    assert result.output["opportunity_cost_estimate"] is None
    assert result.output["period_label"] is None
    assert "error" not in result.output


async def test_stockout_cost_db_error_returns_error_key():
    with patch(
        "packages.tools.finance_stockout_cost_tool.get_pool",
        side_effect=RuntimeError("database_url not set"),
    ):
        tool = CalculateStockoutCostImpactTool()
        result = await tool.handle({"sku_id": "SKU-Z", "shortage_units": 30}, make_ctx())

    assert "error" in result.output
