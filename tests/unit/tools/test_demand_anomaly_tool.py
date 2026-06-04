from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from packages.tools.base import ToolContext
from packages.tools.demand_anomaly_tool import DemandAnomalyTool


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


def _row(date: datetime.date, quantity: int | None, is_missing: bool = False) -> dict:
    return {"date": date, "quantity": quantity, "is_missing": is_missing}


async def test_anomaly_spike_detected_above_threshold():
    # 19 rows with quantity=10, 1 spike at quantity=50
    # mean=10, std is low -> z_score of 50 is well above 2.5
    base = datetime.date(2025, 1, 1)
    rows = [_row(base + datetime.timedelta(days=i), 10) for i in range(19)]
    rows.append(_row(base + datetime.timedelta(days=19), 50))

    mock_pool = make_pool(rows)
    with patch("packages.tools.demand_anomaly_tool.get_pool", return_value=mock_pool):
        tool = DemandAnomalyTool()
        result = await tool.handle(
            {"sku_id": "SKU-A", "lookback_days": 90, "z_threshold": 2.5}, make_ctx()
        )

    assert result.output["anomaly_count"] >= 1
    anomaly_types = [a["anomaly_type"] for a in result.output["anomalies"]]
    assert "spike" in anomaly_types


async def test_anomaly_drop_detected_below_threshold():
    # 19 rows with quantity=50, 1 drop at quantity=1
    base = datetime.date(2025, 1, 1)
    rows = [_row(base + datetime.timedelta(days=i), 50) for i in range(19)]
    rows.append(_row(base + datetime.timedelta(days=19), 1))

    mock_pool = make_pool(rows)
    with patch("packages.tools.demand_anomaly_tool.get_pool", return_value=mock_pool):
        tool = DemandAnomalyTool()
        result = await tool.handle(
            {"sku_id": "SKU-A", "lookback_days": 90, "z_threshold": 2.5}, make_ctx()
        )

    anomaly_types = [a["anomaly_type"] for a in result.output["anomalies"]]
    assert "drop" in anomaly_types


async def test_anomaly_missing_flag_classified_as_missing():
    # 3 rows minimum; one with is_missing=True
    base = datetime.date(2025, 1, 1)
    rows = [
        _row(base, 10),
        _row(base + datetime.timedelta(days=1), 10),
        _row(base + datetime.timedelta(days=2), None, is_missing=True),
    ]

    mock_pool = make_pool(rows)
    with patch("packages.tools.demand_anomaly_tool.get_pool", return_value=mock_pool):
        tool = DemandAnomalyTool()
        result = await tool.handle(
            {"sku_id": "SKU-A", "lookback_days": 90}, make_ctx()
        )

    anomaly_types = [a["anomaly_type"] for a in result.output["anomalies"]]
    assert "missing" in anomaly_types


async def test_anomaly_stockout_zero_quantity_not_missing():
    # quantity=0 with is_missing=False -> stockout
    base = datetime.date(2025, 1, 1)
    rows = [
        _row(base, 10),
        _row(base + datetime.timedelta(days=1), 10),
        _row(base + datetime.timedelta(days=2), 0, is_missing=False),
    ]

    mock_pool = make_pool(rows)
    with patch("packages.tools.demand_anomaly_tool.get_pool", return_value=mock_pool):
        tool = DemandAnomalyTool()
        result = await tool.handle(
            {"sku_id": "SKU-A", "lookback_days": 90}, make_ctx()
        )

    anomaly_types = [a["anomaly_type"] for a in result.output["anomalies"]]
    assert "stockout" in anomaly_types


async def test_anomaly_fewer_than_3_rows_returns_empty():
    base = datetime.date(2025, 1, 1)
    rows = [
        _row(base, 10),
        _row(base + datetime.timedelta(days=1), 20),
    ]

    mock_pool = make_pool(rows)
    with patch("packages.tools.demand_anomaly_tool.get_pool", return_value=mock_pool):
        tool = DemandAnomalyTool()
        result = await tool.handle(
            {"sku_id": "SKU-A", "lookback_days": 90}, make_ctx()
        )

    assert result.output["anomaly_count"] == 0
