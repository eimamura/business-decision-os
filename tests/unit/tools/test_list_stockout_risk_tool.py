from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from packages.tools.base import ToolContext
from packages.tools.list_stockout_risk_tool import ListStockoutRiskTool


def make_ctx() -> ToolContext:
    return ToolContext(
        session_id=uuid4(),
        agent_step_id=uuid4(),
        specialist_role="control",
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


def _row(
    sku_id: str = "SKU-A",
    on_hand_qty: float = 100.0,
    avg_daily: float = 5.0,
    incoming_supply: float = 0.0,
) -> dict:
    return {
        "sku_id": sku_id,
        "on_hand_qty": on_hand_qty,
        "avg_daily": avg_daily,
        "incoming_supply": incoming_supply,
    }


# ---------------------------------------------------------------------------
# (a) Returns SKUs filtered by min_risk_level
# ---------------------------------------------------------------------------


async def test_list_stockout_risk_filters_by_min_risk_level_medium():
    # SKU-A: on_hand=1000, avg_daily=5 → forecast=35 → ending=965 → ratio~27.6 → "low"
    # SKU-B: on_hand=5,    avg_daily=5 → forecast=35 → ending=-30   → "critical"
    # SKU-C: on_hand=4,    avg_daily=5 → forecast=35 → ending=-31   → "critical"
    # min_risk_level="medium" should exclude "low" rows
    rows = [
        _row("SKU-A", on_hand_qty=1000.0, avg_daily=5.0),
        _row("SKU-B", on_hand_qty=5.0, avg_daily=5.0),
        _row("SKU-C", on_hand_qty=4.0, avg_daily=5.0),
    ]
    mock_pool = make_pool(rows)

    with patch("packages.tools.list_stockout_risk_tool.get_pool", return_value=mock_pool):
        tool = ListStockoutRiskTool()
        result = await tool.handle({"horizon_days": 7, "min_risk_level": "medium"}, make_ctx())

    items = result.output["items"]
    sku_ids = [i["sku_id"] for i in items]
    assert "SKU-A" not in sku_ids  # low risk is excluded
    assert "SKU-B" in sku_ids
    assert "SKU-C" in sku_ids


# ---------------------------------------------------------------------------
# (b) count matches len(items)
# ---------------------------------------------------------------------------


async def test_list_stockout_risk_count_matches_items_length():
    rows = [
        _row("SKU-A", on_hand_qty=10.0, avg_daily=5.0),
        _row("SKU-B", on_hand_qty=3.0, avg_daily=5.0),
    ]
    mock_pool = make_pool(rows)

    with patch("packages.tools.list_stockout_risk_tool.get_pool", return_value=mock_pool):
        tool = ListStockoutRiskTool()
        result = await tool.handle({"horizon_days": 7, "min_risk_level": "low"}, make_ctx())

    assert result.output["count"] == len(result.output["items"])


# ---------------------------------------------------------------------------
# (c) stockout_date_estimate computed correctly for critical SKU
# ---------------------------------------------------------------------------


async def test_list_stockout_risk_critical_sku_has_stockout_date_estimate():
    # on_hand=5, avg_daily=5, incoming=0 → days_until_stockout = 5/5 = 1
    rows = [_row("SKU-CRIT", on_hand_qty=5.0, avg_daily=5.0, incoming_supply=0.0)]
    mock_pool = make_pool(rows)

    with patch("packages.tools.list_stockout_risk_tool.get_pool", return_value=mock_pool):
        tool = ListStockoutRiskTool()
        result = await tool.handle({"horizon_days": 7, "min_risk_level": "critical"}, make_ctx())

    items = result.output["items"]
    assert len(items) == 1
    item = items[0]
    assert item["risk_level"] == "critical"
    assert item["stockout_date_estimate"] is not None

    expected_date = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
    assert item["stockout_date_estimate"] == expected_date


# ---------------------------------------------------------------------------
# (d) empty result when no SKUs meet threshold
# ---------------------------------------------------------------------------


async def test_list_stockout_risk_empty_when_all_below_threshold():
    # All SKUs have ample stock (risk_level="low"); min_risk_level="critical"
    rows = [
        _row("SKU-A", on_hand_qty=1000.0, avg_daily=5.0),
        _row("SKU-B", on_hand_qty=900.0, avg_daily=5.0),
    ]
    mock_pool = make_pool(rows)

    with patch("packages.tools.list_stockout_risk_tool.get_pool", return_value=mock_pool):
        tool = ListStockoutRiskTool()
        result = await tool.handle({"horizon_days": 7, "min_risk_level": "critical"}, make_ctx())

    assert result.output["items"] == []
    assert result.output["count"] == 0


# ---------------------------------------------------------------------------
# (e) DB error returns {"error": ...} dict
# ---------------------------------------------------------------------------


async def test_list_stockout_risk_db_error_returns_error_key():
    with patch(
        "packages.tools.list_stockout_risk_tool.get_pool",
        side_effect=RuntimeError("database_url not set"),
    ):
        tool = ListStockoutRiskTool()
        result = await tool.handle({}, make_ctx())

    assert "error" in result.output
    assert "database" in result.output["error"].lower()


# ---------------------------------------------------------------------------
# (f) min_risk_level="low" returns all non-none risk items (includes low/medium/high/critical)
# ---------------------------------------------------------------------------


async def test_list_stockout_risk_min_low_includes_all_at_risk():
    # SKU-A: low, SKU-B: medium, SKU-C: high, SKU-D: critical
    # horizon=7, demand = avg_daily * 7
    # low:       on_hand=600, avg_daily=5 → demand=35 → ending=565 → ratio=16.1 ≥ 0.5 → "low"
    # medium:    on_hand=5,   avg_daily=5 → demand=35 → ending=-30 → "critical"  ← adjust below
    # high:      on_hand=4,   avg_daily=5 → demand=35 → ending=-31 → "critical"
    # Use simpler numbers to hit each bucket precisely:
    # low:      ratio ≥ 0.5  → ending ≥ 0.5 * demand=35 → ending ≥ 17.5 → on_hand=18, avg_daily=5→ ending=18-35=-17 → critical (nope)
    # Reuse verified thresholds from _classify_stockout_risk:
    #   critical: projected < 0
    #   high:     0 ≤ ratio < 0.1 → projected ≥ 0 AND projected/demand < 0.1
    #   medium:   0.1 ≤ ratio < 0.5
    #   low:      ratio ≥ 0.5
    # horizon=7 days:
    #   low:     on_hand=200, avg_daily=5 → demand=35, ending=165, ratio=4.7 → "low"
    #   medium:  on_hand=16,  avg_daily=5 → demand=35, ending=-19 → "critical" ← adjust
    # Easiest approach: pick values where ending is large/medium/small fraction of demand
    #   demand=100 (avg_daily=100/7≈14.28 with horizon=7, but we want whole numbers)
    # Use horizon=10 for convenience:
    #   demand = avg_daily * 10
    #   low:      on_hand=600, avg_daily=10 → demand=100, ending=500, ratio=5   → "low"
    #   medium:   on_hand=20,  avg_daily=10 → demand=100, ending=-80 → "critical" ← still wrong
    # The thresholds apply to projected_ending_stock / demand_forecast:
    #   high is:   0 ≤ projected < 0.1*demand
    #   medium is: 0.1*demand ≤ projected < 0.5*demand
    #   low:       projected ≥ 0.5*demand (no stockout projected)
    # So to get exactly "high":  demand=100, projected=5   (ratio=0.05)
    #    → on_hand + incoming - demand = 5 → on_hand = 5 + demand = 105, avg_daily=10, horizon=10
    # To get "medium": demand=100, projected=20 (ratio=0.20)
    #    → on_hand = 120, avg_daily=10, horizon=10
    rows = [
        # low:      on_hand=600, avg_daily=10, demand=100, ending=500, ratio=5
        _row("SKU-LOW", on_hand_qty=600.0, avg_daily=10.0, incoming_supply=0.0),
        # medium:   on_hand=120, avg_daily=10, demand=100, ending=20, ratio=0.20
        _row("SKU-MED", on_hand_qty=120.0, avg_daily=10.0, incoming_supply=0.0),
        # high:     on_hand=105, avg_daily=10, demand=100, ending=5, ratio=0.05
        _row("SKU-HIGH", on_hand_qty=105.0, avg_daily=10.0, incoming_supply=0.0),
        # critical: on_hand=50, avg_daily=10, demand=100, ending=-50
        _row("SKU-CRIT", on_hand_qty=50.0, avg_daily=10.0, incoming_supply=0.0),
    ]
    mock_pool = make_pool(rows)

    with patch("packages.tools.list_stockout_risk_tool.get_pool", return_value=mock_pool):
        tool = ListStockoutRiskTool()
        result = await tool.handle({"horizon_days": 10, "min_risk_level": "low"}, make_ctx())

    items = result.output["items"]
    sku_ids = {i["sku_id"] for i in items}
    assert {"SKU-LOW", "SKU-MED", "SKU-HIGH", "SKU-CRIT"} == sku_ids
    assert result.output["count"] == 4


# ---------------------------------------------------------------------------
# Output schema shape validation
# ---------------------------------------------------------------------------


async def test_list_stockout_risk_items_have_required_keys():
    rows = [_row("SKU-A", on_hand_qty=5.0, avg_daily=5.0)]
    mock_pool = make_pool(rows)

    with patch("packages.tools.list_stockout_risk_tool.get_pool", return_value=mock_pool):
        tool = ListStockoutRiskTool()
        result = await tool.handle({"horizon_days": 7, "min_risk_level": "critical"}, make_ctx())

    required_keys = {
        "sku_id",
        "on_hand_qty",
        "demand_forecast",
        "incoming_supply",
        "projected_ending_stock",
        "risk_level",
        "stockout_date_estimate",
    }
    for item in result.output["items"]:
        assert required_keys <= item.keys()


# ---------------------------------------------------------------------------
# Default parameter values
# ---------------------------------------------------------------------------


async def test_list_stockout_risk_defaults_horizon_7_and_min_level_medium():
    rows = [_row("SKU-A", on_hand_qty=1000.0, avg_daily=5.0)]
    mock_pool = make_pool(rows)

    with patch("packages.tools.list_stockout_risk_tool.get_pool", return_value=mock_pool):
        tool = ListStockoutRiskTool()
        # Call with no arguments — should use horizon_days=7 and min_risk_level="medium"
        result = await tool.handle({}, make_ctx())

    # SKU-A has ample stock (low risk), so with min_risk_level="medium" it should be excluded
    assert result.output["items"] == []
    assert result.output["count"] == 0


# ---------------------------------------------------------------------------
# Sorting: critical items appear before high, which appear before medium, then low
# ---------------------------------------------------------------------------


async def test_list_stockout_risk_sorted_critical_first():
    rows = [
        _row("SKU-LOW", on_hand_qty=600.0, avg_daily=10.0),   # low
        _row("SKU-CRIT", on_hand_qty=50.0, avg_daily=10.0),   # critical (horizon=10)
        _row("SKU-HIGH", on_hand_qty=105.0, avg_daily=10.0),  # high
    ]
    mock_pool = make_pool(rows)

    with patch("packages.tools.list_stockout_risk_tool.get_pool", return_value=mock_pool):
        tool = ListStockoutRiskTool()
        result = await tool.handle({"horizon_days": 10, "min_risk_level": "low"}, make_ctx())

    items = result.output["items"]
    assert len(items) == 3
    assert items[0]["sku_id"] == "SKU-CRIT"
    assert items[1]["sku_id"] == "SKU-HIGH"
    assert items[2]["sku_id"] == "SKU-LOW"


# ---------------------------------------------------------------------------
# missing_data: all SKUs have avg_daily=0 (no demand history in last 30 days)
# ---------------------------------------------------------------------------


async def test_list_stockout_risk_all_zero_demand_populates_missing_data():
    """When every SKU has avg_daily=0 the tool reports missing_data for each SKU.

    This distinguishes "no stockout risk" from "evaluation impossible due to
    missing demand data" — the root cause of the Judge-FAIL (bdos-judge 2026-06-10).
    """
    rows = [
        _row("SKU-001", on_hand_qty=100.0, avg_daily=0.0),
        _row("SKU-002", on_hand_qty=200.0, avg_daily=0.0),
        _row("SKU-003", on_hand_qty=50.0, avg_daily=0.0),
    ]
    mock_pool = make_pool(rows)

    with patch("packages.tools.list_stockout_risk_tool.get_pool", return_value=mock_pool):
        tool = ListStockoutRiskTool()
        result = await tool.handle({"horizon_days": 7, "min_risk_level": "medium"}, make_ctx())

    assert result.output["items"] == []
    assert result.output["count"] == 0

    missing = result.output["missing_data"]
    assert len(missing) == 3
    # Each entry names the SKU with no demand history
    sku_ids_in_missing = {entry.split(": ")[-1] for entry in missing}
    assert sku_ids_in_missing == {"SKU-001", "SKU-002", "SKU-003"}
    # Entry format matches calculate_stockout_risk convention
    for entry in missing:
        assert entry.startswith("no demand history in last 30 days: ")


# ---------------------------------------------------------------------------
# missing_data: mixed — some SKUs have demand, others do not
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "rows,expected_missing_skus,expected_item_skus",
    [
        # Case 1: one SKU has demand, one does not; only the zero-demand SKU missing
        (
            [
                _row("SKU-A", on_hand_qty=10.0, avg_daily=5.0),   # has demand → critical (horizon=7)
                _row("SKU-B", on_hand_qty=500.0, avg_daily=0.0),  # no demand → missing
            ],
            {"SKU-B"},
            {"SKU-A"},
        ),
        # Case 2: all SKUs have demand; missing_data must be empty
        (
            [
                _row("SKU-X", on_hand_qty=5.0, avg_daily=5.0),    # critical
                _row("SKU-Y", on_hand_qty=1000.0, avg_daily=5.0), # low/none
            ],
            set(),
            {"SKU-X"},
        ),
    ],
)
async def test_list_stockout_risk_mixed_demand_missing_data(
    rows: list[dict],
    expected_missing_skus: set[str],
    expected_item_skus: set[str],
) -> None:
    """Only zero-demand SKUs appear in missing_data; positive-demand SKUs are evaluated normally."""
    mock_pool = make_pool(rows)

    with patch("packages.tools.list_stockout_risk_tool.get_pool", return_value=mock_pool):
        tool = ListStockoutRiskTool()
        result = await tool.handle({"horizon_days": 7, "min_risk_level": "medium"}, make_ctx())

    actual_missing_skus = {entry.split(": ")[-1] for entry in result.output["missing_data"]}
    actual_item_skus = {item["sku_id"] for item in result.output["items"]}

    assert actual_missing_skus == expected_missing_skus
    assert actual_item_skus == expected_item_skus
