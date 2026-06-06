from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from packages.tools.base import ToolContext
from packages.tools.demand_profile_tool import DemandProfileTool


def make_ctx() -> ToolContext:
    return ToolContext(
        session_id=uuid4(),
        agent_step_id=uuid4(),
        specialist_role="data_engineer",
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


def _row(date: datetime.date, quantity: int, is_missing: bool = False) -> dict:
    return {"date": date, "quantity": quantity, "is_missing": is_missing}


async def test_profile_normal_data_computes_correct_metrics():
    # 10 rows: 1 is_missing=True (with non-zero qty), 2 quantity=0
    base = datetime.date(2025, 1, 1)
    rows = [_row(base + datetime.timedelta(days=i), 10) for i in range(7)]
    rows.append(_row(base + datetime.timedelta(days=7), 0))
    rows.append(_row(base + datetime.timedelta(days=8), 0))
    # is_missing=True with qty=5 — counts as missing but not zero_demand
    rows.append(_row(base + datetime.timedelta(days=9), 5, is_missing=True))

    mock_pool = make_pool(rows)
    with patch("packages.tools.demand_profile_tool.get_pool", return_value=mock_pool):
        tool = DemandProfileTool()
        result = await tool.handle({"sku_id": "SKU-A", "lookback_days": 30}, make_ctx())

    assert result.output["missing_rate"] == 0.1
    assert result.output["zero_demand_days"] == 2
    assert result.output["stockout_suspected_days"] == 1
    assert result.output["cv"] is not None


async def test_profile_sku_id_none_fetches_all_skus():
    base = datetime.date(2025, 1, 1)
    rows = [_row(base + datetime.timedelta(days=i), 5) for i in range(5)]

    mock_pool = make_pool(rows)
    with patch("packages.tools.demand_profile_tool.get_pool", return_value=mock_pool):
        tool = DemandProfileTool()
        result = await tool.handle({"lookback_days": 30}, make_ctx())

    assert "record_count" in result.output


async def test_profile_empty_result_returns_zero_metrics():
    mock_pool = make_pool([])
    with patch("packages.tools.demand_profile_tool.get_pool", return_value=mock_pool):
        tool = DemandProfileTool()
        result = await tool.handle({"sku_id": "SKU-NONE", "lookback_days": 30}, make_ctx())

    assert result.output["record_count"] == 0
    assert result.output["mean"] is None
    assert 0.0 <= result.output["data_quality_score"] <= 1.0


async def test_profile_db_error_returns_error_key():
    with patch(
        "packages.tools.demand_profile_tool.get_pool",
        side_effect=RuntimeError("no DATABASE_URL configured"),
    ):
        tool = DemandProfileTool()
        result = await tool.handle({"sku_id": "SKU-A", "lookback_days": 30}, make_ctx())

    assert "error" in result.output
