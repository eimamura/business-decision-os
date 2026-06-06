from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from packages.tools.base import ToolContext
from packages.tools.demand_seasonality_tool import DemandSeasonalityTool
from packages.tools.demand_drivers_tool import DemandDriversTool
from packages.tools.demand_segment_tool import DemandSegmentTool
from packages.tools.demand_compare_tool import DemandCompareTool


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


# ============================================================
# DemandSeasonalityTool
# ============================================================

async def test_seasonality_low_variance_returns_no_pattern():
    # 28 rows with uniform quantity=10, spread across days Mon-Sun in 4 weeks
    # CV for both weekly and monthly groupings will be 0 -> no pattern
    base = datetime.date(2025, 1, 6)  # Monday
    rows = [
        {"date": base + datetime.timedelta(days=i), "quantity": 10}
        for i in range(28)
    ]

    mock_pool = make_pool(rows)
    with patch("packages.tools.demand_seasonality_tool.get_pool", return_value=mock_pool):
        tool = DemandSeasonalityTool()
        result = await tool.handle(
            {"sku_id": "SKU-A", "lookback_days": 365}, make_ctx()
        )

    assert result.output["has_weekly_pattern"] is False
    assert result.output["has_monthly_pattern"] is False


async def test_seasonality_index_is_zero_below_14_records():
    # Only 10 rows — below the 14-record threshold
    base = datetime.date(2025, 1, 1)
    rows = [
        {"date": base + datetime.timedelta(days=i), "quantity": 10}
        for i in range(10)
    ]

    mock_pool = make_pool(rows)
    with patch("packages.tools.demand_seasonality_tool.get_pool", return_value=mock_pool):
        tool = DemandSeasonalityTool()
        result = await tool.handle(
            {"sku_id": "SKU-A", "lookback_days": 365}, make_ctx()
        )

    assert result.output["seasonality_index"] == 0.0


# ============================================================
# DemandDriversTool
# ============================================================

def _make_drivers_pool(total_qty: float, customer_rows: list) -> MagicMock:
    """DemandDriversTool calls get_pool() twice:
    1. _fetch_total_demand  -> conn.fetchrow returns {"total_qty": total_qty}
    2. _fetch_customer_rows -> conn.fetch returns customer_rows
    """
    mock_conn = AsyncMock()
    mock_conn.fetchrow.return_value = {"total_qty": total_qty}
    mock_conn.fetch.return_value = customer_rows

    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_pool


async def test_drivers_no_customers_with_sku_affinity_returns_empty():
    # customer_master rows whose sku_affinity_json does NOT match the requested sku_id
    customer_rows = [
        {"customer_id": "C1", "segment": "retail", "sku_affinity_json": '{"SKU-OTHER": 1.0}'},
        {"customer_id": "C2", "segment": "wholesale", "sku_affinity_json": '{"SKU-X": 2.0}'},
    ]
    mock_pool = _make_drivers_pool(500.0, customer_rows)

    with patch("packages.tools.demand_drivers_tool.get_pool", return_value=mock_pool):
        tool = DemandDriversTool()
        result = await tool.handle(
            {"sku_id": "SKU-A", "lookback_days": 90}, make_ctx()
        )

    assert result.output["top_customers"] == []


async def test_drivers_concentration_is_1_for_single_customer():
    # Only 1 customer with affinity for the requested SKU
    customer_rows = [
        {"customer_id": "C1", "segment": "retail", "sku_affinity_json": '{"SKU-A": 1.0}'},
    ]
    mock_pool = _make_drivers_pool(1000.0, customer_rows)

    with patch("packages.tools.demand_drivers_tool.get_pool", return_value=mock_pool):
        tool = DemandDriversTool()
        result = await tool.handle(
            {"sku_id": "SKU-A", "lookback_days": 90}, make_ctx()
        )

    # Single customer: share=1.0, HHI = 1.0^2 = 1.0
    assert result.output["customer_concentration"] == 1.0
    assert result.output["sku_risk_level"] == "high"


# ============================================================
# DemandSegmentTool
# ============================================================

async def test_segment_sku_dimension_shares_sum_to_1():
    # 3 SKUs with known quantities — demand_share should sum to 1.0
    # SKU-A: 3 rows each qty=10 -> total=30
    # SKU-B: 3 rows each qty=20 -> total=60
    # SKU-C: 3 rows each qty=10 -> total=10  (using single row for simplicity)
    base = datetime.date(2025, 1, 1)
    rows = [
        {"sku_id": "SKU-A", "date": base, "quantity": 30.0},
        {"sku_id": "SKU-B", "date": base, "quantity": 60.0},
        {"sku_id": "SKU-C", "date": base, "quantity": 10.0},
    ]

    mock_pool = make_pool(rows)
    with patch("packages.tools.demand_segment_tool.get_pool", return_value=mock_pool):
        tool = DemandSegmentTool()
        result = await tool.handle(
            {"dimension": "sku", "lookback_days": 90, "top_n": 10}, make_ctx()
        )

    total_share = sum(s["demand_share"] for s in result.output["segments"])
    assert abs(total_share - 1.0) < 1e-6


async def test_segment_empty_demand_returns_empty_segments():
    mock_pool = make_pool([])
    with patch("packages.tools.demand_segment_tool.get_pool", return_value=mock_pool):
        tool = DemandSegmentTool()
        result = await tool.handle(
            {"dimension": "sku", "lookback_days": 90, "top_n": 10}, make_ctx()
        )

    assert result.output["segments"] == []


# ============================================================
# DemandCompareTool
# ============================================================

def _make_compare_pool(total_a: float, total_b: float) -> MagicMock:
    """DemandCompareTool calls get_pool() twice, each returns a fetchrow result."""
    mock_conn = AsyncMock()
    # fetchrow is called twice: once for period_a, once for period_b
    mock_conn.fetchrow.side_effect = [
        {"total_qty": total_a},
        {"total_qty": total_b},
    ]

    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_pool


async def test_compare_period_b_higher_returns_positive_change():
    mock_pool = _make_compare_pool(100.0, 120.0)

    with patch("packages.tools.demand_compare_tool.get_pool", return_value=mock_pool):
        tool = DemandCompareTool()
        result = await tool.handle(
            {
                "sku_id": "SKU-A",
                "period_a": {"start": "2025-01-01", "end": "2025-01-31"},
                "period_b": {"start": "2025-02-01", "end": "2025-02-28"},
            },
            make_ctx(),
        )

    assert result.output["change_units"] == 20.0
    assert result.output["change_pct"] is not None
    assert result.output["change_pct"] > 0


async def test_compare_period_a_zero_change_pct_is_none():
    mock_pool = _make_compare_pool(0.0, 50.0)

    with patch("packages.tools.demand_compare_tool.get_pool", return_value=mock_pool):
        tool = DemandCompareTool()
        result = await tool.handle(
            {
                "sku_id": "SKU-A",
                "period_a": {"start": "2025-01-01", "end": "2025-01-31"},
                "period_b": {"start": "2025-02-01", "end": "2025-02-28"},
            },
            make_ctx(),
        )

    assert result.output["change_pct"] is None
