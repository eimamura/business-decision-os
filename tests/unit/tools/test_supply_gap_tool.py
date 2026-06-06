from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from packages.tools.base import ToolContext
from packages.tools.supply_gap_tool import CalculateSupplyGapTool


def make_ctx() -> ToolContext:
    return ToolContext(
        session_id=uuid4(),
        agent_step_id=uuid4(),
        specialist_role="data_engineer",
        actor="test",
        correlation_id=uuid4(),
    )


def make_pool_with_fetchrow_side_effect(side_effects: list) -> MagicMock:
    """Build a pool mock where conn.fetchrow is called sequentially via side_effect."""
    mock_conn = AsyncMock()
    mock_conn.fetchrow.side_effect = side_effects
    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_pool


async def test_gap_shortage_detected_returns_high_risk():
    # on_hand=100, incoming=50 → total_available=150
    # avg_daily=10 → forecast over 30d = 300 → gap_units = 150 → gap_pct = 50%
    # _classify_risk: gap_pct >= 50 → "critical"
    on_hand_row = {"on_hand_qty": 100}
    incoming_row = {"incoming_qty": 50}
    demand_row = {"avg_daily": 10}

    mock_pool = make_pool_with_fetchrow_side_effect([on_hand_row, incoming_row, demand_row])

    with patch("packages.tools.supply_gap_tool.get_pool", return_value=mock_pool):
        tool = CalculateSupplyGapTool()
        result = await tool.handle({"sku_id": "SKU-A", "horizon_days": 30}, make_ctx())

    assert result.output["gap_units"] > 0
    assert result.output["risk_level"] in ("medium", "high", "critical")


async def test_gap_surplus_returns_none_risk():
    # on_hand=500, incoming=0 → total_available=500
    # avg_daily=3.33 → forecast over 30d = 99.9 → gap_units = -400.1 (surplus)
    on_hand_row = {"on_hand_qty": 500}
    incoming_row = {"incoming_qty": 0}
    demand_row = {"avg_daily": 3.33}

    mock_pool = make_pool_with_fetchrow_side_effect([on_hand_row, incoming_row, demand_row])

    with patch("packages.tools.supply_gap_tool.get_pool", return_value=mock_pool):
        tool = CalculateSupplyGapTool()
        result = await tool.handle({"sku_id": "SKU-B", "horizon_days": 30}, make_ctx())

    assert result.output["gap_units"] < 0
    assert result.output["risk_level"] == "none"


async def test_gap_zero_forecast_gap_pct_is_none():
    # avg_daily_demand=0 → forecast_demand=0 → gap_pct must be None
    on_hand_row = {"on_hand_qty": 50}
    incoming_row = {"incoming_qty": 0}
    demand_row = {"avg_daily": 0}

    mock_pool = make_pool_with_fetchrow_side_effect([on_hand_row, incoming_row, demand_row])

    with patch("packages.tools.supply_gap_tool.get_pool", return_value=mock_pool):
        tool = CalculateSupplyGapTool()
        result = await tool.handle({"sku_id": "SKU-C", "horizon_days": 30}, make_ctx())

    assert result.output["gap_pct"] is None
