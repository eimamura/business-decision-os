from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from packages.tools.base import ToolContext
from packages.tools.supply_lead_time_tool import AnalyzeSupplyLeadTimeTool
from packages.tools.inventory_doi_tool import CalculateDaysOfInventoryTool
from packages.tools.supply_risk_tool import AnalyzeSupplyRiskTool


def make_ctx() -> ToolContext:
    return ToolContext(
        session_id=uuid4(),
        agent_step_id=uuid4(),
        specialist_role="data_engineer",
        actor="test",
        correlation_id=uuid4(),
    )


# ============================================================
# AnalyzeSupplyLeadTimeTool
# AnalyzeSupplyLeadTimeTool calls conn.fetch once and computes
# lead times from (order_date, expected_arrival) pairs in Python.
# ============================================================

def _make_fetch_pool(fetch_return: list) -> MagicMock:
    mock_conn = AsyncMock()
    mock_conn.fetch.return_value = fetch_return
    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_pool


def _lead_time_row(
    order_date: datetime.date,
    expected_arrival: datetime.date,
    supplier_id: str = "SUP-1",
) -> dict:
    return {
        "order_date": order_date,
        "expected_arrival": expected_arrival,
        "supplier_id": supplier_id,
    }


async def test_lead_time_computes_avg_correctly():
    # Order 1: lead time 10d; Order 2: lead time 20d → avg = 15.0
    rows = [
        _lead_time_row(datetime.date(2026, 1, 1), datetime.date(2026, 1, 11)),
        _lead_time_row(datetime.date(2026, 1, 1), datetime.date(2026, 1, 21), supplier_id="SUP-2"),
    ]
    mock_pool = _make_fetch_pool(rows)

    with patch("packages.tools.supply_lead_time_tool.get_pool", return_value=mock_pool):
        tool = AnalyzeSupplyLeadTimeTool()
        result = await tool.handle({"sku_id": "SKU-A"}, make_ctx())

    assert result.output["avg_lead_time_days"] == 15.0


async def test_lead_time_no_orders_returns_none():
    mock_pool = _make_fetch_pool([])

    with patch("packages.tools.supply_lead_time_tool.get_pool", return_value=mock_pool):
        tool = AnalyzeSupplyLeadTimeTool()
        result = await tool.handle({"sku_id": "SKU-Z"}, make_ctx())

    assert result.output["avg_lead_time_days"] is None
    assert result.output["order_count"] == 0


# ============================================================
# CalculateDaysOfInventoryTool (migrated from CalculateDaysOfSupplyTool — T-483 DOS→DOI merge)
# Three sequential conn.fetchrow calls:
#   1. inventory_snapshot  → on_hand_qty
#   2. demand_history      → avg_daily
#   3. sku_master          → lead_time_days_mean
# ============================================================

def _make_fetchrow_pool(side_effects: list) -> MagicMock:
    mock_conn = AsyncMock()
    mock_conn.fetchrow.side_effect = side_effects
    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_pool


async def test_days_of_supply_computes_correctly():
    """Migrated from DOS: on_hand=300, avg_daily=10 → days_of_inventory = 30.0.

    DOI uses the same formula (on_hand / avg_daily) as the deleted DOS tool.
    """
    on_hand_row = {"on_hand_qty": 300}
    demand_row = {"avg_daily": 10.0}
    sku_row = {"lead_time_days_mean": None}

    mock_pool = _make_fetchrow_pool([on_hand_row, demand_row, sku_row])

    with patch("packages.tools.inventory_doi_tool.get_pool", return_value=mock_pool):
        tool = CalculateDaysOfInventoryTool()
        result = await tool.handle({"sku_id": "SKU-A"}, make_ctx())

    assert result.output["days_of_inventory"] == 30.0


async def test_days_of_supply_reorder_signal_triggered():
    """Migrated from DOS: on_hand=100, avg_daily=10 → days=10 < 14 → reorder_signal=True."""
    on_hand_row = {"on_hand_qty": 100}
    demand_row = {"avg_daily": 10.0}
    sku_row = {"lead_time_days_mean": None}

    mock_pool = _make_fetchrow_pool([on_hand_row, demand_row, sku_row])

    with patch("packages.tools.inventory_doi_tool.get_pool", return_value=mock_pool):
        tool = CalculateDaysOfInventoryTool()
        result = await tool.handle({"sku_id": "SKU-A"}, make_ctx())

    assert result.output["reorder_signal"] is True


async def test_doi_stockout_date_estimate_computed_from_days():
    """DOI-new: stockout_date_estimate = today + int(days_of_inventory)."""
    # on_hand=300, avg_daily=10 → days=30 → stockout = today + 30
    on_hand_row = {"on_hand_qty": 300}
    demand_row = {"avg_daily": 10.0}
    sku_row = {"lead_time_days_mean": None}

    mock_pool = _make_fetchrow_pool([on_hand_row, demand_row, sku_row])

    with patch("packages.tools.inventory_doi_tool.get_pool", return_value=mock_pool):
        tool = CalculateDaysOfInventoryTool()
        result = await tool.handle({"sku_id": "SKU-A"}, make_ctx())

    expected_date = (datetime.date.today() + datetime.timedelta(days=30)).isoformat()
    assert result.output["stockout_date_estimate"] == expected_date


async def test_doi_stockout_date_estimate_null_when_demand_is_none():
    """DOI-new: stockout_date_estimate is null when avg_daily_demand is None."""
    on_hand_row = {"on_hand_qty": 100}
    demand_row = {"avg_daily": None}
    sku_row = {"lead_time_days_mean": None}

    mock_pool = _make_fetchrow_pool([on_hand_row, demand_row, sku_row])

    with patch("packages.tools.inventory_doi_tool.get_pool", return_value=mock_pool):
        tool = CalculateDaysOfInventoryTool()
        result = await tool.handle({"sku_id": "SKU-B"}, make_ctx())

    assert result.output["stockout_date_estimate"] is None
    assert result.output["days_of_inventory"] is None


# ============================================================
# AnalyzeSupplyRiskTool
# DB calls within one pool.acquire block (in order):
#   1. conn.fetchrow → on_hand_qty (inventory_snapshot)
#   2. conn.fetchrow → incoming_qty (supply_orders)
#   3. conn.fetchrow → avg_daily (demand_history)
#   4. conn.fetch    → lt_rows (supply_orders lead time)
#   5. conn.fetch    → supplier_rows (supply_orders HHI)
# ============================================================

def _make_risk_pool(
    on_hand_qty: float,
    incoming_qty: float,
    avg_daily: float,
    lt_rows: list,
    supplier_rows: list,
) -> MagicMock:
    mock_conn = AsyncMock()
    mock_conn.fetchrow.side_effect = [
        {"on_hand_qty": on_hand_qty},
        {"incoming_qty": incoming_qty},
        {"avg_daily": avg_daily},
    ]
    mock_conn.fetch.side_effect = [lt_rows, supplier_rows]

    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_pool


def _lt_row(order_date: datetime.date, expected_arrival: datetime.date) -> dict:
    return {"order_date": order_date, "expected_arrival": expected_arrival}


async def test_supply_risk_high_gap_returns_high_risk():
    # on_hand=10, incoming=0, avg_daily=10, horizon=30
    # forecast_demand = 300, total_available = 10
    # gap_units = 290, gap_pct = 96.7% → gap_risk ≈ 0.967
    # With only 1 lt_row (no std), lead_time_risk = 0.5
    # Single supplier: HHI = 1.0 → concentration_risk = 1.0
    # risk_score = 0.5*0.967 + 0.3*0.5 + 0.2*1.0 = 0.483 + 0.15 + 0.2 = 0.833 → "critical"
    lt_rows = [_lt_row(datetime.date(2026, 1, 1), datetime.date(2026, 1, 15))]
    supplier_rows = [{"supplier_id": "SUP-1", "total_qty": 10.0}]

    mock_pool = _make_risk_pool(
        on_hand_qty=10.0,
        incoming_qty=0.0,
        avg_daily=10.0,
        lt_rows=lt_rows,
        supplier_rows=supplier_rows,
    )

    with patch("packages.tools.supply_risk_tool.get_pool", return_value=mock_pool):
        tool = AnalyzeSupplyRiskTool()
        result = await tool.handle({"sku_id": "SKU-A", "horizon_days": 30}, make_ctx())

    assert result.output["risk_level"] in ("high", "critical")


async def test_supply_risk_no_gap_returns_low_risk():
    # on_hand=10000, incoming=0, avg_daily=1, horizon=30
    # forecast_demand = 30, total_available = 10000
    # gap_units = -9970 (surplus) → gap_pct < 0 → gap_risk = 0 (clamped by max(0, ...))
    # 2 lead time rows with equal times → stdev=0 → CV=0 → lead_time_risk=0
    # 2 equal suppliers: HHI = 0.5^2 + 0.5^2 = 0.5 → concentration_risk=0.5
    # risk_score = 0.5*0 + 0.3*0 + 0.2*0.5 = 0.1 → "low"
    lt_rows = [
        _lt_row(datetime.date(2026, 1, 1), datetime.date(2026, 1, 11)),
        _lt_row(datetime.date(2026, 1, 1), datetime.date(2026, 1, 11)),
    ]
    supplier_rows = [
        {"supplier_id": "SUP-1", "total_qty": 50.0},
        {"supplier_id": "SUP-2", "total_qty": 50.0},
    ]

    mock_pool = _make_risk_pool(
        on_hand_qty=10000.0,
        incoming_qty=0.0,
        avg_daily=1.0,
        lt_rows=lt_rows,
        supplier_rows=supplier_rows,
    )

    with patch("packages.tools.supply_risk_tool.get_pool", return_value=mock_pool):
        tool = AnalyzeSupplyRiskTool()
        result = await tool.handle({"sku_id": "SKU-B", "horizon_days": 30}, make_ctx())

    assert result.output["risk_level"] == "low"
