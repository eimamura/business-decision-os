from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from packages.tools.base import ToolContext
from packages.tools.forecast_accuracy_tool import ForecastAccuracyTool


def make_ctx() -> ToolContext:
    return ToolContext(
        session_id=uuid4(),
        agent_step_id=uuid4(),
        specialist_role="demand",
        actor="test",
        correlation_id=uuid4(),
    )


def _make_pool_two_calls(fetch_return: list, fetchval_return: int) -> MagicMock:
    """Mock pool where conn.fetch returns fetch_return and conn.fetchval returns fetchval_return.

    ForecastAccuracyTool calls get_pool() twice (once for joined rows, once for demand count),
    each time acquiring a connection separately.
    """
    mock_conn = AsyncMock()
    mock_conn.fetch.return_value = fetch_return
    mock_conn.fetchval.return_value = fetchval_return

    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_pool


def _joined_row(date: datetime.date, forecast_qty: float, actual_qty: float) -> dict:
    return {"target_date": date, "forecast_qty": forecast_qty, "actual_qty": actual_qty}


async def test_accuracy_perfect_forecast_returns_zero_error():
    rows = [
        _joined_row(datetime.date(2025, 1, i + 1), 100.0, 100.0)
        for i in range(10)
    ]
    mock_pool = _make_pool_two_calls(rows, 10)

    with patch("packages.tools.forecast_accuracy_tool.get_pool", return_value=mock_pool):
        tool = ForecastAccuracyTool()
        result = await tool.handle({"sku_id": "SKU-A", "lookback_days": 90}, make_ctx())

    assert result.output["mape"] == 0.0
    assert result.output["wape"] == 0.0
    assert result.output["bias"] == 0.0


async def test_accuracy_over_forecast_returns_positive_bias():
    # Forecast is always 20% above actual
    rows = [
        _joined_row(datetime.date(2025, 1, i + 1), 120.0, 100.0)
        for i in range(10)
    ]
    mock_pool = _make_pool_two_calls(rows, 10)

    with patch("packages.tools.forecast_accuracy_tool.get_pool", return_value=mock_pool):
        tool = ForecastAccuracyTool()
        result = await tool.handle({"sku_id": "SKU-A", "lookback_days": 90}, make_ctx())

    assert result.output["bias"] > 0


async def test_accuracy_zero_actual_quantity_mape_is_none():
    # All actual_qty = 0; no positive-actual rows for MAPE
    rows = [
        _joined_row(datetime.date(2025, 1, i + 1), 50.0, 0.0)
        for i in range(5)
    ]
    mock_pool = _make_pool_two_calls(rows, 5)

    with patch("packages.tools.forecast_accuracy_tool.get_pool", return_value=mock_pool):
        tool = ForecastAccuracyTool()
        result = await tool.handle({"sku_id": "SKU-A", "lookback_days": 90}, make_ctx())

    assert result.output["mape"] is None
    assert result.output["wape"] == 0.0


async def test_accuracy_identifies_worst_period():
    # One row with 50% error, rest with 5% error
    rows = [
        _joined_row(datetime.date(2025, 1, 1), 150.0, 100.0),  # 50% error — worst
    ] + [
        _joined_row(datetime.date(2025, 1, i + 2), 105.0, 100.0)  # 5% error
        for i in range(9)
    ]
    mock_pool = _make_pool_two_calls(rows, 10)

    with patch("packages.tools.forecast_accuracy_tool.get_pool", return_value=mock_pool):
        tool = ForecastAccuracyTool()
        result = await tool.handle({"sku_id": "SKU-A", "lookback_days": 90}, make_ctx())

    assert result.output["worst_period"] is not None


async def test_accuracy_no_forecast_rows_returns_zero_sample_size():
    # Joined rows query returns no rows (no matching forecast+demand pairs)
    mock_pool = _make_pool_two_calls([], 10)

    with patch("packages.tools.forecast_accuracy_tool.get_pool", return_value=mock_pool):
        tool = ForecastAccuracyTool()
        result = await tool.handle({"sku_id": "SKU-A", "lookback_days": 90}, make_ctx())

    assert result.output["sample_size"] == 0
