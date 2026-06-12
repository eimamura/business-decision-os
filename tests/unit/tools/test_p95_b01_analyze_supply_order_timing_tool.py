"""T-583 / T-584: Unit tests for analyze_supply_order_timing_tool.

Covers:
- Schema contract: required top-level keys present.
- Classification boundaries:
    pull_forward_candidate: expected_arrival > projected_stockout_date.
    push_out_candidate: days_of_cover_at_arrival >= PUSH_OUT_COVER_DAYS.
    on_track: otherwise.
- days_misaligned math:
    pull_forward: positive = (arrival - stockout).days.
    push_out: negative = -floor(days_of_cover_at_arrival - PUSH_OUT_COVER_DAYS).
    on_track: 0.
- Summary counts computed pre-cap.
- Cap + truncated: >100 orders → truncated=True; count reflects full pre-cap set.
- missing_data variants:
    zero-demand SKU → missing_data entry, order classified on_track with null dates.
    null expected_arrival → missing_data entry, order excluded from classified list.
    no inventory_snapshot row → missing_data entry, on_hand assumed 0.
- Empty DB shape: empty lists, count=0, truncated=False, summary zeros.
- DB error → output contains error key.
- Deterministic sort: pull_forward before push_out before on_track;
  within class |days_misaligned| desc; then order_id asc.
- Registration: analyze_supply_order_timing in create_tool_registry().
- Pure-Python date helpers: _to_date, _date_to_iso.
"""
from __future__ import annotations

import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from packages.tools.base import ToolContext


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_ctx() -> ToolContext:
    return ToolContext(
        session_id=uuid4(),
        agent_step_id=uuid4(),
        specialist_role="control",
        actor="test",
        correlation_id=uuid4(),
    )


def _make_pool(order_rows: list[Any], inv_rows: list[Any], demand_rows: list[Any]) -> MagicMock:
    """Mock pool whose three fetch() calls return order, inventory, demand sequences."""
    mock_conn = AsyncMock()
    mock_conn.fetch.side_effect = [order_rows, inv_rows, demand_rows]
    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_pool


def _order(
    sku_id: str,
    supplier_id: str = "SUP-001",
    order_date: str = "2026-06-01",
    expected_arrival: Any = None,
    quantity: float = 100.0,
    status: str = "pending",
) -> dict[str, Any]:
    """Build an order row dict."""
    today = datetime.date.today()
    arrival = expected_arrival if expected_arrival is not None else (
        today + datetime.timedelta(days=10)
    )
    if isinstance(arrival, int):
        arrival = today + datetime.timedelta(days=arrival)
    return {
        "sku_id": sku_id,
        "supplier_id": supplier_id,
        "order_date": datetime.date.fromisoformat(order_date) if isinstance(order_date, str) else order_date,
        "expected_arrival": arrival,
        "quantity": quantity,
        "status": status,
    }


def _inv(sku_id: str, on_hand: float) -> dict[str, Any]:
    return {"sku_id": sku_id, "on_hand_qty": on_hand}


def _demand(sku_id: str, avg_daily: float) -> dict[str, Any]:
    return {"sku_id": sku_id, "avg_daily": avg_daily}


# Patch target
_PATCH = "packages.tools.analyze_supply_order_timing_tool.get_pool"


# ---------------------------------------------------------------------------
# Schema contract
# ---------------------------------------------------------------------------


async def test_schema_required_top_level_keys_present() -> None:
    """Output must include orders, count, truncated, summary, missing_data."""
    from packages.tools.analyze_supply_order_timing_tool import AnalyzeSupplyOrderTimingTool

    with patch(_PATCH, return_value=_make_pool([], [], [])):
        result = await AnalyzeSupplyOrderTimingTool().handle({}, make_ctx())

    for key in ("orders", "count", "truncated", "summary", "missing_data"):
        assert key in result.output, f"missing key: {key}"

    assert isinstance(result.output["orders"], list)
    assert isinstance(result.output["missing_data"], list)
    assert isinstance(result.output["truncated"], bool)
    assert isinstance(result.output["summary"], dict)


async def test_schema_summary_has_required_keys() -> None:
    """summary must include pull_forward_count, push_out_count, on_track_count."""
    from packages.tools.analyze_supply_order_timing_tool import AnalyzeSupplyOrderTimingTool

    with patch(_PATCH, return_value=_make_pool([], [], [])):
        result = await AnalyzeSupplyOrderTimingTool().handle({}, make_ctx())

    summary = result.output["summary"]
    for key in ("pull_forward_count", "push_out_count", "on_track_count"):
        assert key in summary, f"summary missing key: {key}"


async def test_schema_order_row_has_required_keys() -> None:
    """Each order row must include all required keys."""
    from packages.tools.analyze_supply_order_timing_tool import AnalyzeSupplyOrderTimingTool

    today = datetime.date.today()
    orders = [_order("SKU-A", expected_arrival=today + datetime.timedelta(days=20))]
    inv = [_inv("SKU-A", 50.0)]
    demand = [_demand("SKU-A", 1.0)]

    with patch(_PATCH, return_value=_make_pool(orders, inv, demand)):
        result = await AnalyzeSupplyOrderTimingTool().handle({}, make_ctx())

    assert len(result.output["orders"]) == 1
    row = result.output["orders"][0]
    required = (
        "order_id", "sku_id", "supplier_id", "order_date", "expected_arrival",
        "quantity", "status", "on_hand", "avg_daily_demand",
        "projected_stockout_date", "days_of_cover_at_arrival",
        "days_misaligned", "classification",
    )
    for key in required:
        assert key in row, f"order row missing key: {key}"


# ---------------------------------------------------------------------------
# Classification boundaries
# ---------------------------------------------------------------------------


async def test_pull_forward_when_arrival_after_stockout() -> None:
    """arrival > projected_stockout → pull_forward_candidate."""
    from packages.tools.analyze_supply_order_timing_tool import AnalyzeSupplyOrderTimingTool

    today = datetime.date.today()
    # on_hand=10, avg_daily=1 → stockout in 10 days
    # arrival = today+20 → arrives 10 days after stockout
    orders = [_order("SKU-A", expected_arrival=today + datetime.timedelta(days=20))]
    inv = [_inv("SKU-A", 10.0)]
    demand = [_demand("SKU-A", 1.0)]

    with patch(_PATCH, return_value=_make_pool(orders, inv, demand)):
        result = await AnalyzeSupplyOrderTimingTool().handle({}, make_ctx())

    assert len(result.output["orders"]) == 1
    row = result.output["orders"][0]
    assert row["classification"] == "pull_forward_candidate"
    assert row["days_misaligned"] > 0


async def test_push_out_when_cover_exceeds_threshold() -> None:
    """days_of_cover_at_arrival >= 30 → push_out_candidate (and not pull_forward)."""
    from packages.tools.analyze_supply_order_timing_tool import AnalyzeSupplyOrderTimingTool
    from packages.tools.analyze_supply_order_timing_tool import PUSH_OUT_COVER_DAYS

    today = datetime.date.today()
    # on_hand=100, avg_daily=1 → stockout in 100 days, arrival=today+5
    # days_of_cover_at_arrival = 100-5 = 95 >= 30 → push_out
    orders = [_order("SKU-B", expected_arrival=today + datetime.timedelta(days=5))]
    inv = [_inv("SKU-B", 100.0)]
    demand = [_demand("SKU-B", 1.0)]

    with patch(_PATCH, return_value=_make_pool(orders, inv, demand)):
        result = await AnalyzeSupplyOrderTimingTool().handle({}, make_ctx())

    assert len(result.output["orders"]) == 1
    row = result.output["orders"][0]
    assert row["classification"] == "push_out_candidate"
    assert row["days_misaligned"] < 0
    # days_misaligned = -floor(95 - 30) = -65
    assert row["days_misaligned"] == -(95 - PUSH_OUT_COVER_DAYS)


async def test_on_track_when_between_bands() -> None:
    """Order arriving before stockout with cover < 30 days at arrival → on_track."""
    from packages.tools.analyze_supply_order_timing_tool import AnalyzeSupplyOrderTimingTool

    today = datetime.date.today()
    # on_hand=50, avg_daily=1 → stockout in 50 days, arrival=today+30
    # days_of_cover_at_arrival = 50-30 = 20 < 30 and arrival < stockout → on_track
    orders = [_order("SKU-C", expected_arrival=today + datetime.timedelta(days=30))]
    inv = [_inv("SKU-C", 50.0)]
    demand = [_demand("SKU-C", 1.0)]

    with patch(_PATCH, return_value=_make_pool(orders, inv, demand)):
        result = await AnalyzeSupplyOrderTimingTool().handle({}, make_ctx())

    assert len(result.output["orders"]) == 1
    row = result.output["orders"][0]
    assert row["classification"] == "on_track"
    assert row["days_misaligned"] == 0


async def test_pull_forward_takes_precedence_over_push_out() -> None:
    """An order after stockout is pull_forward regardless of days_of_cover_at_arrival."""
    from packages.tools.analyze_supply_order_timing_tool import AnalyzeSupplyOrderTimingTool

    today = datetime.date.today()
    # on_hand=5, avg_daily=1 → stockout in 5 days, arrival=today+60
    # days_of_cover_at_arrival = 5-60 = -55 (negative — already stocked out at arrival)
    # arrival > projected_stockout → pull_forward wins
    orders = [_order("SKU-D", expected_arrival=today + datetime.timedelta(days=60))]
    inv = [_inv("SKU-D", 5.0)]
    demand = [_demand("SKU-D", 1.0)]

    with patch(_PATCH, return_value=_make_pool(orders, inv, demand)):
        result = await AnalyzeSupplyOrderTimingTool().handle({}, make_ctx())

    row = result.output["orders"][0]
    assert row["classification"] == "pull_forward_candidate"


# ---------------------------------------------------------------------------
# days_misaligned math
# ---------------------------------------------------------------------------


async def test_days_misaligned_pull_forward_is_arrival_minus_stockout() -> None:
    """days_misaligned for pull_forward = (expected_arrival - projected_stockout_date).days."""
    from packages.tools.analyze_supply_order_timing_tool import AnalyzeSupplyOrderTimingTool

    today = datetime.date.today()
    # on_hand=10, avg_daily=1 → projected_stockout = today+10, arrival = today+20
    # days_misaligned = 10
    orders = [_order("SKU-E", expected_arrival=today + datetime.timedelta(days=20))]
    inv = [_inv("SKU-E", 10.0)]
    demand = [_demand("SKU-E", 1.0)]

    with patch(_PATCH, return_value=_make_pool(orders, inv, demand)):
        result = await AnalyzeSupplyOrderTimingTool().handle({}, make_ctx())

    row = result.output["orders"][0]
    assert row["classification"] == "pull_forward_candidate"
    assert row["days_misaligned"] == 10


async def test_days_misaligned_push_out_is_negative_excess_cover() -> None:
    """days_misaligned for push_out = -floor(days_of_cover_at_arrival - PUSH_OUT_COVER_DAYS)."""
    from packages.tools.analyze_supply_order_timing_tool import AnalyzeSupplyOrderTimingTool
    from packages.tools.analyze_supply_order_timing_tool import PUSH_OUT_COVER_DAYS

    today = datetime.date.today()
    # on_hand=80, avg_daily=1 → stockout=today+80, arrival=today+5
    # days_of_cover_at_arrival = 80-5 = 75 >= 30 → push_out
    # days_misaligned = -floor(75 - 30) = -45
    orders = [_order("SKU-F", expected_arrival=today + datetime.timedelta(days=5))]
    inv = [_inv("SKU-F", 80.0)]
    demand = [_demand("SKU-F", 1.0)]

    with patch(_PATCH, return_value=_make_pool(orders, inv, demand)):
        result = await AnalyzeSupplyOrderTimingTool().handle({}, make_ctx())

    row = result.output["orders"][0]
    assert row["classification"] == "push_out_candidate"
    assert row["days_misaligned"] == -(75 - PUSH_OUT_COVER_DAYS)


async def test_days_misaligned_on_track_is_zero() -> None:
    """days_misaligned for on_track == 0."""
    from packages.tools.analyze_supply_order_timing_tool import AnalyzeSupplyOrderTimingTool

    today = datetime.date.today()
    # on_hand=50, avg_daily=1 → stockout=today+50, arrival=today+30
    # cover_at_arrival=20 < 30 and arrival < stockout → on_track
    orders = [_order("SKU-G", expected_arrival=today + datetime.timedelta(days=30))]
    inv = [_inv("SKU-G", 50.0)]
    demand = [_demand("SKU-G", 1.0)]

    with patch(_PATCH, return_value=_make_pool(orders, inv, demand)):
        result = await AnalyzeSupplyOrderTimingTool().handle({}, make_ctx())

    row = result.output["orders"][0]
    assert row["days_misaligned"] == 0


# ---------------------------------------------------------------------------
# Summary counts pre-cap
# ---------------------------------------------------------------------------


async def test_summary_counts_match_pre_cap() -> None:
    """Summary counts must reflect the full pre-cap set, not the capped list."""
    from packages.tools.analyze_supply_order_timing_tool import AnalyzeSupplyOrderTimingTool

    today = datetime.date.today()
    # Build 3 orders: 1 pull_forward, 1 push_out, 1 on_track
    orders = [
        _order("SKU-P", expected_arrival=today + datetime.timedelta(days=20)),  # pull_forward
        _order("SKU-Q", expected_arrival=today + datetime.timedelta(days=5)),   # push_out
        _order("SKU-R", expected_arrival=today + datetime.timedelta(days=30)),  # on_track
    ]
    inv = [_inv("SKU-P", 10.0), _inv("SKU-Q", 100.0), _inv("SKU-R", 50.0)]
    demand = [_demand("SKU-P", 1.0), _demand("SKU-Q", 1.0), _demand("SKU-R", 1.0)]

    with patch(_PATCH, return_value=_make_pool(orders, inv, demand)):
        result = await AnalyzeSupplyOrderTimingTool().handle({}, make_ctx())

    summary = result.output["summary"]
    assert summary["pull_forward_count"] == 1
    assert summary["push_out_count"] == 1
    assert summary["on_track_count"] == 1
    assert result.output["count"] == 3


async def test_summary_counts_computed_pre_cap_with_many_orders() -> None:
    """Summary counts and count reflect the full pre-cap set even when truncated.

    Setup:
      SKU-000..SKU-109: on_hand=10, avg_daily=1, arrival=today+20
        → stockout=today+10, arrival>stockout → pull_forward (110 orders)
      SKU-110..SKU-114: on_hand=50, avg_daily=1, arrival=today+30
        → stockout=today+50, arrival<stockout, cover_at_arrival=20 < 30 → on_track (5 orders)
    Total = 115 > 100 → truncated=True, len(orders)=100, count=115.
    Summary pre-cap: pull_forward=110, on_track=5.
    """
    from packages.tools.analyze_supply_order_timing_tool import AnalyzeSupplyOrderTimingTool

    today = datetime.date.today()
    # 110 pull_forward orders
    pf_orders = [
        _order(f"SKU-{i:03d}", expected_arrival=today + datetime.timedelta(days=20))
        for i in range(110)
    ]
    # 5 on_track orders: on_hand=50, arrival=today+30, avg_daily=1
    # stockout=today+50, cover_at_arrival=50-30=20 < 30 → on_track
    ot_orders = [
        _order(f"SKU-{i:03d}", supplier_id="SUP-002",
               expected_arrival=today + datetime.timedelta(days=30))
        for i in range(110, 115)
    ]
    all_orders = pf_orders + ot_orders

    # on_hand: pull_forward SKUs get 10, on_track SKUs get 50
    inv = (
        [_inv(f"SKU-{i:03d}", 10.0) for i in range(110)]
        + [_inv(f"SKU-{i:03d}", 50.0) for i in range(110, 115)]
    )
    # All avg_daily=1; pull_forward: stockout=today+10 < arrival=today+20; on_track: stockout=today+50
    demand = [_demand(f"SKU-{i:03d}", 1.0) for i in range(115)]

    with patch(_PATCH, return_value=_make_pool(all_orders, inv, demand)):
        result = await AnalyzeSupplyOrderTimingTool().handle({}, make_ctx())

    assert result.output["truncated"] is True
    assert result.output["count"] == 115
    assert len(result.output["orders"]) == 100  # capped
    # summary reflects the full pre-cap set
    assert result.output["summary"]["pull_forward_count"] == 110
    assert result.output["summary"]["on_track_count"] == 5
    assert result.output["summary"]["push_out_count"] == 0


# ---------------------------------------------------------------------------
# missing_data variants
# ---------------------------------------------------------------------------


async def test_missing_data_zero_demand_sku_classified_on_track_null_dates() -> None:
    """Zero-demand SKU → missing_data entry, order classified on_track, projected_stockout=null."""
    from packages.tools.analyze_supply_order_timing_tool import AnalyzeSupplyOrderTimingTool

    today = datetime.date.today()
    orders = [_order("SKU-Z", expected_arrival=today + datetime.timedelta(days=5))]
    inv = [_inv("SKU-Z", 50.0)]
    demand: list[Any] = []  # no demand row → avg_daily=0

    with patch(_PATCH, return_value=_make_pool(orders, inv, demand)):
        result = await AnalyzeSupplyOrderTimingTool().handle({}, make_ctx())

    assert len(result.output["missing_data"]) >= 1
    assert any("zero-demand" in m or "SKU-Z" in m for m in result.output["missing_data"])

    assert len(result.output["orders"]) == 1
    row = result.output["orders"][0]
    assert row["classification"] == "on_track"
    assert row["projected_stockout_date"] is None
    assert row["days_of_cover_at_arrival"] is None
    assert row["days_misaligned"] == 0


async def test_missing_data_null_expected_arrival_excluded() -> None:
    """Order with null expected_arrival → missing_data entry, excluded from orders list."""
    from packages.tools.analyze_supply_order_timing_tool import AnalyzeSupplyOrderTimingTool

    orders = [_order("SKU-N", expected_arrival=None)]
    # Manually set expected_arrival to None
    orders[0] = dict(orders[0])
    orders[0]["expected_arrival"] = None
    inv = [_inv("SKU-N", 50.0)]
    demand = [_demand("SKU-N", 1.0)]

    with patch(_PATCH, return_value=_make_pool(orders, inv, demand)):
        result = await AnalyzeSupplyOrderTimingTool().handle({}, make_ctx())

    assert len(result.output["orders"]) == 0
    assert any("null expected_arrival" in m for m in result.output["missing_data"])


async def test_missing_data_no_inventory_snapshot_on_hand_assumed_zero() -> None:
    """SKU with no inventory row → missing_data entry, on_hand=0, pull_forward if arrival late."""
    from packages.tools.analyze_supply_order_timing_tool import AnalyzeSupplyOrderTimingTool

    today = datetime.date.today()
    # on_hand=0, avg_daily=5, stockout=today (floor(0/5)=0), arrival=today+1 → pull_forward
    orders = [_order("SKU-NI", expected_arrival=today + datetime.timedelta(days=1))]
    inv: list[Any] = []  # no inventory row for SKU-NI
    demand = [_demand("SKU-NI", 5.0)]

    with patch(_PATCH, return_value=_make_pool(orders, inv, demand)):
        result = await AnalyzeSupplyOrderTimingTool().handle({}, make_ctx())

    assert any("inventory_snapshot" in m and "SKU-NI" in m for m in result.output["missing_data"])
    # on_hand=0 → stockout=today → arrival=today+1 > today → pull_forward
    assert len(result.output["orders"]) == 1
    assert result.output["orders"][0]["on_hand"] == 0.0
    assert result.output["orders"][0]["classification"] == "pull_forward_candidate"


# ---------------------------------------------------------------------------
# Empty DB shape
# ---------------------------------------------------------------------------


async def test_empty_db_returns_empty_lists_and_zero_counts() -> None:
    """Empty DB: orders=[], count=0, truncated=False, summary all zeros, missing_data=[]."""
    from packages.tools.analyze_supply_order_timing_tool import AnalyzeSupplyOrderTimingTool

    with patch(_PATCH, return_value=_make_pool([], [], [])):
        result = await AnalyzeSupplyOrderTimingTool().handle({}, make_ctx())

    assert result.output["orders"] == []
    assert result.output["count"] == 0
    assert result.output["truncated"] is False
    assert result.output["summary"]["pull_forward_count"] == 0
    assert result.output["summary"]["push_out_count"] == 0
    assert result.output["summary"]["on_track_count"] == 0
    assert result.output["missing_data"] == []


# ---------------------------------------------------------------------------
# DB error path
# ---------------------------------------------------------------------------


async def test_db_error_returns_error_key() -> None:
    """DB failure during fetch → ToolResult.output contains 'error' key."""
    from packages.tools.analyze_supply_order_timing_tool import AnalyzeSupplyOrderTimingTool

    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(
        side_effect=RuntimeError("DATABASE_URL not configured")
    )
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    with patch(_PATCH, return_value=mock_pool):
        result = await AnalyzeSupplyOrderTimingTool().handle({}, make_ctx())

    assert "error" in result.output
    assert "database" in result.output["error"].lower()


# ---------------------------------------------------------------------------
# Deterministic sort order
# ---------------------------------------------------------------------------


async def test_sort_order_pull_forward_before_push_out_before_on_track() -> None:
    """pull_forward rows come before push_out which come before on_track."""
    from packages.tools.analyze_supply_order_timing_tool import AnalyzeSupplyOrderTimingTool

    today = datetime.date.today()
    orders = [
        _order("SKU-OT", expected_arrival=today + datetime.timedelta(days=30)),  # on_track
        _order("SKU-PO", expected_arrival=today + datetime.timedelta(days=5)),   # push_out
        _order("SKU-PF", expected_arrival=today + datetime.timedelta(days=20)),  # pull_forward
    ]
    inv = [_inv("SKU-OT", 50.0), _inv("SKU-PO", 100.0), _inv("SKU-PF", 10.0)]
    demand = [_demand("SKU-OT", 1.0), _demand("SKU-PO", 1.0), _demand("SKU-PF", 1.0)]

    with patch(_PATCH, return_value=_make_pool(orders, inv, demand)):
        result = await AnalyzeSupplyOrderTimingTool().handle({}, make_ctx())

    classes = [row["classification"] for row in result.output["orders"]]
    # pull_forward first, then push_out, then on_track
    assert classes.index("pull_forward_candidate") < classes.index("push_out_candidate")
    assert classes.index("push_out_candidate") < classes.index("on_track")


async def test_sort_order_within_class_by_abs_days_misaligned_desc() -> None:
    """Within a class, orders with higher |days_misaligned| come first."""
    from packages.tools.analyze_supply_order_timing_tool import AnalyzeSupplyOrderTimingTool

    today = datetime.date.today()
    # Two pull_forward orders: one with 30 days late, one with 5 days late
    orders = [
        _order("SKU-PF1", supplier_id="SUP-A",
               expected_arrival=today + datetime.timedelta(days=15)),  # stockout=today+5 → 10 days late
        _order("SKU-PF2", supplier_id="SUP-B",
               expected_arrival=today + datetime.timedelta(days=35)),  # stockout=today+5 → 30 days late
    ]
    inv = [_inv("SKU-PF1", 5.0), _inv("SKU-PF2", 5.0)]
    demand = [_demand("SKU-PF1", 1.0), _demand("SKU-PF2", 1.0)]

    with patch(_PATCH, return_value=_make_pool(orders, inv, demand)):
        result = await AnalyzeSupplyOrderTimingTool().handle({}, make_ctx())

    orders_out = result.output["orders"]
    assert len(orders_out) == 2
    # SKU-PF2 has days_misaligned=30, SKU-PF1 has days_misaligned=10 → PF2 first
    assert orders_out[0]["sku_id"] == "SKU-PF2"
    assert orders_out[1]["sku_id"] == "SKU-PF1"


async def test_sort_order_tie_break_by_order_id_asc() -> None:
    """Same days_misaligned within a class → order_id ascending as tie-break."""
    from packages.tools.analyze_supply_order_timing_tool import AnalyzeSupplyOrderTimingTool

    today = datetime.date.today()
    # Two on_track orders with identical parameters; order_id tiebreak by sku_id+supplier
    orders = [
        _order("SKU-ZZZ", supplier_id="SUP-002", order_date="2026-06-01",
               expected_arrival=today + datetime.timedelta(days=30)),
        _order("SKU-AAA", supplier_id="SUP-001", order_date="2026-06-01",
               expected_arrival=today + datetime.timedelta(days=30)),
    ]
    inv = [_inv("SKU-ZZZ", 50.0), _inv("SKU-AAA", 50.0)]
    demand = [_demand("SKU-ZZZ", 1.0), _demand("SKU-AAA", 1.0)]

    with patch(_PATCH, return_value=_make_pool(orders, inv, demand)):
        result = await AnalyzeSupplyOrderTimingTool().handle({}, make_ctx())

    ids = [r["order_id"] for r in result.output["orders"]]
    # order_id = sku_id:supplier_id:order_date → AAA:... < ZZZ:...
    assert ids[0] < ids[1]


# ---------------------------------------------------------------------------
# Registration check
# ---------------------------------------------------------------------------


def test_analyze_supply_order_timing_in_registry() -> None:
    """analyze_supply_order_timing must be registered in create_tool_registry()."""
    from packages.tools import create_tool_registry

    registry = create_tool_registry()
    assert "analyze_supply_order_timing" in registry._tools


# ---------------------------------------------------------------------------
# Pure-Python date helpers
# ---------------------------------------------------------------------------


def test_to_date_with_date_object() -> None:
    from packages.tools.analyze_supply_order_timing_tool import _to_date

    d = datetime.date(2026, 6, 12)
    assert _to_date(d) == d


def test_to_date_with_datetime_object() -> None:
    from packages.tools.analyze_supply_order_timing_tool import _to_date

    dt = datetime.datetime(2026, 6, 12, 10, 30)
    assert _to_date(dt) == datetime.date(2026, 6, 12)


def test_to_date_with_iso_string() -> None:
    from packages.tools.analyze_supply_order_timing_tool import _to_date

    assert _to_date("2026-06-12") == datetime.date(2026, 6, 12)


def test_to_date_with_none() -> None:
    from packages.tools.analyze_supply_order_timing_tool import _to_date

    assert _to_date(None) is None


def test_to_date_with_invalid_string() -> None:
    from packages.tools.analyze_supply_order_timing_tool import _to_date

    assert _to_date("not-a-date") is None


def test_date_to_iso_with_date() -> None:
    from packages.tools.analyze_supply_order_timing_tool import _date_to_iso

    assert _date_to_iso(datetime.date(2026, 6, 12)) == "2026-06-12"


def test_date_to_iso_with_none() -> None:
    from packages.tools.analyze_supply_order_timing_tool import _date_to_iso

    assert _date_to_iso(None) == ""


# ---------------------------------------------------------------------------
# PUSH_OUT_COVER_DAYS constant documentation
# ---------------------------------------------------------------------------


def test_push_out_cover_days_is_30() -> None:
    """PUSH_OUT_COVER_DAYS must be 30 (documented threshold)."""
    from packages.tools.analyze_supply_order_timing_tool import PUSH_OUT_COVER_DAYS

    assert PUSH_OUT_COVER_DAYS == 30, (
        f"PUSH_OUT_COVER_DAYS changed from 30 to {PUSH_OUT_COVER_DAYS}. "
        "Update the module docstring and this test if the threshold is intentionally changed."
    )
