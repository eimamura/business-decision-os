from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from packages.tools.base import ToolContext
from packages.tools.demand_trend_tool import DemandTrendTool


def make_ctx() -> ToolContext:
    return ToolContext(
        session_id=uuid4(),
        agent_step_id=uuid4(),
        specialist_role="demand",
        actor="test",
        correlation_id=uuid4(),
    )


def make_pool(fetch_return: list) -> MagicMock:
    mock_conn = AsyncMock()
    mock_conn.fetch.return_value = fetch_return
    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_pool


def _row(date: datetime.date, quantity: float) -> dict:
    return {"date": date, "quantity": quantity}


async def test_trend_increasing_data_returns_up_direction():
    # 30 rows with strictly increasing quantity: slope will be large positive
    base = datetime.date(2025, 1, 6)  # Monday
    rows = [_row(base + datetime.timedelta(days=i), float(i + 1) * 10) for i in range(30)]

    mock_pool = make_pool(rows)
    with patch("packages.tools.demand_trend_tool.get_pool", return_value=mock_pool):
        tool = DemandTrendTool()
        result = await tool.handle(
            {"sku_id": "SKU-A", "lookback_days": 90, "granularity": "weekly"}, make_ctx()
        )

    assert result.output["trend_direction"] == "up"


async def test_trend_decreasing_data_returns_down_direction():
    base = datetime.date(2025, 1, 6)  # Monday
    rows = [_row(base + datetime.timedelta(days=i), float(30 - i) * 10) for i in range(30)]

    mock_pool = make_pool(rows)
    with patch("packages.tools.demand_trend_tool.get_pool", return_value=mock_pool):
        tool = DemandTrendTool()
        result = await tool.handle(
            {"sku_id": "SKU-A", "lookback_days": 90, "granularity": "weekly"}, make_ctx()
        )

    assert result.output["trend_direction"] == "down"


async def test_trend_flat_data_returns_flat_direction():
    base = datetime.date(2025, 1, 6)  # Monday
    rows = [_row(base + datetime.timedelta(days=i), 50.0) for i in range(28)]

    mock_pool = make_pool(rows)
    with patch("packages.tools.demand_trend_tool.get_pool", return_value=mock_pool):
        tool = DemandTrendTool()
        result = await tool.handle(
            {"sku_id": "SKU-A", "lookback_days": 90, "granularity": "weekly"}, make_ctx()
        )

    assert result.output["trend_direction"] == "flat"


async def test_trend_weekly_granularity_groups_by_week():
    # 3 ISO weeks: use Mondays as anchors for weeks 2, 3, 4 of 2025
    # Week 1: 2025-01-06 to 2025-01-12 (ISO week 2)
    # Week 2: 2025-01-13 to 2025-01-19 (ISO week 3)
    # Week 3: 2025-01-20 to 2025-01-26 (ISO week 4)
    rows = []
    for week_offset in range(3):
        week_start = datetime.date(2025, 1, 6) + datetime.timedelta(weeks=week_offset)
        # Add one row per week to ensure each maps to a distinct ISO week label
        rows.append(_row(week_start, 10.0))

    mock_pool = make_pool(rows)
    with patch("packages.tools.demand_trend_tool.get_pool", return_value=mock_pool):
        tool = DemandTrendTool()
        result = await tool.handle(
            {"sku_id": "SKU-A", "lookback_days": 90, "granularity": "weekly"}, make_ctx()
        )

    assert len(result.output["periods"]) == 3


async def test_trend_monthly_granularity_groups_by_month():
    # 2 months: January and February 2025
    rows = [
        _row(datetime.date(2025, 1, 15), 100.0),
        _row(datetime.date(2025, 2, 15), 120.0),
    ]

    mock_pool = make_pool(rows)
    with patch("packages.tools.demand_trend_tool.get_pool", return_value=mock_pool):
        tool = DemandTrendTool()
        result = await tool.handle(
            {"sku_id": "SKU-A", "lookback_days": 90, "granularity": "monthly"}, make_ctx()
        )

    assert len(result.output["periods"]) == 2


async def test_trend_fewer_than_2_periods_returns_defaults():
    # All rows fall in the same ISO week — only 1 period
    rows = [
        _row(datetime.date(2025, 1, 6), 10.0),
        _row(datetime.date(2025, 1, 7), 15.0),
        _row(datetime.date(2025, 1, 8), 12.0),
    ]

    mock_pool = make_pool(rows)
    with patch("packages.tools.demand_trend_tool.get_pool", return_value=mock_pool):
        tool = DemandTrendTool()
        result = await tool.handle(
            {"sku_id": "SKU-A", "lookback_days": 90, "granularity": "weekly"}, make_ctx()
        )

    assert result.output["r_squared"] == 0.0
