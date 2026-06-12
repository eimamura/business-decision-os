"""T-546: Gap-filling unit tests for P87 B-02 shipment tools.

Covers gaps not addressed in test_p87_b02_shipment_tools.py:

ListUnshippedOrdersTool:
- supply arriving on or before requested_ship_date → any_supply_delayed_past_ship_date=False
- no open supply (qty=None from DB) → total_qty=0.0, any_supply_delayed_past_ship_date=False
- future-dated order (not yet overdue) → negative days_overdue
- within_days default parameter accepted (no error on empty input)
- empty DB → order_count=0, truncated=False, missing_data=[], orders=[]

AnalyzeShipmentDelayCausesTool:
- Precedence 1 guards Precedence 3: on_hand=None with open late supply → unknown (not upstream_supply_delay)
- Precedence 2 guards Precedence 3: on_hand >= qty with open late supply → unknown (not upstream_supply_delay)
- Precedence 3 vs 4: on_hand < qty, open supply but arrives ON requested_ship_date → inventory_shortage
  (supply not late → falls through to Precedence 4)
- in_transit past planned_delivery → carrier_delay (third carrier sub-case)
- cause_counts contains all five canonical keys even when all are zero
- shipped-order cause=unknown when no delay flags → handled gracefully
- total_delayed increments for multi-cause (warehouse+carrier) as 1 order, not 2
"""
from __future__ import annotations

import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from packages.tools.base import ToolContext


# ---------------------------------------------------------------------------
# Helpers (mirrors test_p87_b02_shipment_tools.py helpers)
# ---------------------------------------------------------------------------


def make_ctx() -> ToolContext:
    return ToolContext(
        session_id=uuid4(),
        agent_step_id=uuid4(),
        specialist_role="control",
        actor="test",
        correlation_id=uuid4(),
    )


def _make_fetch_pool(*fetch_sequences: list[Any]) -> MagicMock:
    """Pool that returns successive fetch() results from fetch_sequences in order."""
    mock_conn = AsyncMock()
    mock_conn.fetch.side_effect = list(fetch_sequences)
    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_pool


def _unshipped_row(
    order_id: str = "CO-TEST",
    sku_id: str = "SKU-001",
    location: str = "WH-001",
    quantity: int = 100,
    days_overdue: int = 2,
    on_hand: int | None = 10,
    supply_qty: float | None = 0.0,
    supply_arrival: datetime.date | None = None,
    status: str = "open",
) -> dict[str, Any]:
    today = datetime.date.today()
    return {
        "order_id": order_id,
        "customer_id": "CUST-001",
        "sku_id": sku_id,
        "ship_from_location_id": location,
        "region": "Kanto",
        "quantity": quantity,
        "order_date": today - datetime.timedelta(days=days_overdue + 5),
        "requested_ship_date": today - datetime.timedelta(days=days_overdue),
        "status": status,
        "on_hand_at_ship_from": on_hand,
        "open_supply_total_qty": supply_qty,
        "nearest_expected_arrival": supply_arrival,
    }


def _shipped_row(
    order_id: str = "CO-TEST",
    planned_ship_days_ago: int = 7,
    actual_ship_days_ago: int = 7,
    planned_delivery_days_ago: int = 4,
    actual_delivery_days_ago: int = 4,
    shipment_status: str = "delivered",
) -> dict[str, Any]:
    today = datetime.date.today()
    return {
        "order_id": order_id,
        "customer_id": "CUST-001",
        "sku_id": "SKU-001",
        "region": "Kanto",
        "status": "shipped",
        "planned_ship_date": today - datetime.timedelta(days=planned_ship_days_ago),
        "actual_ship_date": today - datetime.timedelta(days=actual_ship_days_ago),
        "planned_delivery_date": today - datetime.timedelta(days=planned_delivery_days_ago),
        "actual_delivery_date": today - datetime.timedelta(days=actual_delivery_days_ago),
        "shipment_status": shipment_status,
    }


# ===========================================================================
# ListUnshippedOrdersTool — gap cases
# ===========================================================================


async def test_list_unshipped_orders_empty_db_returns_zero_count() -> None:
    """Empty DB → order_count=0, truncated=False, missing_data=[], orders=[]."""
    from packages.tools.list_unshipped_orders_tool import ListUnshippedOrdersTool

    mock_pool = _make_fetch_pool([])

    with patch("packages.tools.list_unshipped_orders_tool.get_pool", return_value=mock_pool):
        tool = ListUnshippedOrdersTool()
        result = await tool.handle({}, make_ctx())

    assert result.output["order_count"] == 0
    assert result.output["truncated"] is False
    assert result.output["missing_data"] == []
    assert result.output["orders"] == []


async def test_list_unshipped_orders_supply_arriving_on_ship_date_not_delayed() -> None:
    """Supply arrives exactly on requested_ship_date → any_supply_delayed_past_ship_date=False.

    Supply arriving on or before the requested_ship_date is NOT late;
    the tool should not flag it as delayed.
    """
    from packages.tools.list_unshipped_orders_tool import ListUnshippedOrdersTool

    today = datetime.date.today()
    days_overdue = 2
    requested_ship_date = today - datetime.timedelta(days=days_overdue)
    # Arrival exactly on the requested_ship_date (not after) → not delayed
    supply_arrival = requested_ship_date

    rows = [_unshipped_row(days_overdue=days_overdue, supply_qty=100.0, supply_arrival=supply_arrival)]
    mock_pool = _make_fetch_pool(rows)

    with patch("packages.tools.list_unshipped_orders_tool.get_pool", return_value=mock_pool):
        tool = ListUnshippedOrdersTool()
        result = await tool.handle({}, make_ctx())

    supply_ctx = result.output["orders"][0]["open_inbound_supply"]
    assert supply_ctx["any_supply_delayed_past_ship_date"] is False
    assert supply_ctx["total_qty"] == 100.0


async def test_list_unshipped_orders_no_open_supply_gives_zero_qty() -> None:
    """When open_supply_total_qty is None (no supply row) → total_qty=0.0, not delayed."""
    from packages.tools.list_unshipped_orders_tool import ListUnshippedOrdersTool

    rows = [_unshipped_row(supply_qty=None, supply_arrival=None)]
    mock_pool = _make_fetch_pool(rows)

    with patch("packages.tools.list_unshipped_orders_tool.get_pool", return_value=mock_pool):
        tool = ListUnshippedOrdersTool()
        result = await tool.handle({}, make_ctx())

    supply_ctx = result.output["orders"][0]["open_inbound_supply"]
    assert supply_ctx["total_qty"] == 0.0
    assert supply_ctx["nearest_expected_arrival"] is None
    assert supply_ctx["any_supply_delayed_past_ship_date"] is False


async def test_list_unshipped_orders_future_order_has_negative_days_overdue() -> None:
    """Order not yet overdue (requested_ship_date in the future) → days_overdue < 0."""
    from packages.tools.list_unshipped_orders_tool import ListUnshippedOrdersTool

    today = datetime.date.today()
    future_date = today + datetime.timedelta(days=3)
    row = {
        "order_id": "CO-FUTURE",
        "customer_id": "CUST-001",
        "sku_id": "SKU-001",
        "ship_from_location_id": "WH-001",
        "region": "Kanto",
        "quantity": 50,
        "order_date": today - datetime.timedelta(days=2),
        "requested_ship_date": future_date,
        "status": "allocated",
        "on_hand_at_ship_from": 100,
        "open_supply_total_qty": 0.0,
        "nearest_expected_arrival": None,
    }
    mock_pool = _make_fetch_pool([row])

    with patch("packages.tools.list_unshipped_orders_tool.get_pool", return_value=mock_pool):
        tool = ListUnshippedOrdersTool()
        result = await tool.handle({}, make_ctx())

    assert result.output["orders"][0]["days_overdue"] == -3


async def test_list_unshipped_orders_within_days_parameter_accepted() -> None:
    """Passing within_days parameter does not raise an error."""
    from packages.tools.list_unshipped_orders_tool import ListUnshippedOrdersTool

    mock_pool = _make_fetch_pool([])

    with patch("packages.tools.list_unshipped_orders_tool.get_pool", return_value=mock_pool):
        tool = ListUnshippedOrdersTool()
        result = await tool.handle({"within_days": 14}, make_ctx())

    assert "error" not in result.output
    assert result.output["order_count"] == 0


async def test_list_unshipped_orders_status_filter_parameter_accepted() -> None:
    """Passing status_filter parameter does not raise an error."""
    from packages.tools.list_unshipped_orders_tool import ListUnshippedOrdersTool

    mock_pool = _make_fetch_pool([])

    with patch("packages.tools.list_unshipped_orders_tool.get_pool", return_value=mock_pool):
        tool = ListUnshippedOrdersTool()
        result = await tool.handle({"status_filter": ["allocated"]}, make_ctx())

    assert "error" not in result.output
    assert result.output["order_count"] == 0


# ===========================================================================
# AnalyzeShipmentDelayCausesTool — precedence gap cases
# ===========================================================================


async def test_analyze_delay_precedence1_overrides_supply_context() -> None:
    """Precedence 1 (no snapshot) beats Precedence 3 (open late supply).

    When on_hand=None AND there is open supply arriving after the requested_ship_date,
    the classification must be 'unknown' (not 'upstream_supply_delay').
    The order must appear in missing_data.
    """
    from packages.tools.analyze_shipment_delay_causes_tool import AnalyzeShipmentDelayCausesTool

    today = datetime.date.today()
    supply_arrival = today + datetime.timedelta(days=10)  # clearly late

    row = {
        "order_id": "CO-PREC1",
        "customer_id": "CUST-001",
        "sku_id": "SKU-099",
        "ship_from_location_id": "WH-001",
        "region": "Kanto",
        "quantity": 100,
        "requested_ship_date": today - datetime.timedelta(days=2),
        "status": "open",
        "on_hand_at_ship_from": None,       # no snapshot
        "open_supply_total_qty": 500.0,     # open supply exists
        "nearest_expected_arrival": supply_arrival,  # arrives late
    }

    mock_pool = _make_fetch_pool([row], [])

    with patch(
        "packages.tools.analyze_shipment_delay_causes_tool.get_pool",
        return_value=mock_pool,
    ):
        tool = AnalyzeShipmentDelayCausesTool()
        result = await tool.handle({}, make_ctx())

    order_rec = result.output["orders"][0]
    assert order_rec["cause"] == "unknown", (
        f"Expected 'unknown' (Precedence 1) but got '{order_rec['cause']}'"
    )
    assert result.output["cause_counts"]["unknown"] == 1
    assert result.output["cause_counts"]["upstream_supply_delay"] == 0
    assert any("CO-PREC1" in m for m in result.output["missing_data"])


async def test_analyze_delay_precedence2_overrides_supply_context() -> None:
    """Precedence 2 (sufficient stock) beats Precedence 3 (open late supply).

    When on_hand >= quantity AND there is open supply arriving after the
    requested_ship_date, the classification must be 'unknown' (not 'upstream_supply_delay').
    The order must appear in missing_data.
    """
    from packages.tools.analyze_shipment_delay_causes_tool import AnalyzeShipmentDelayCausesTool

    today = datetime.date.today()
    supply_arrival = today + datetime.timedelta(days=10)

    row = {
        "order_id": "CO-PREC2",
        "customer_id": "CUST-001",
        "sku_id": "SKU-098",
        "ship_from_location_id": "WH-001",
        "region": "Kanto",
        "quantity": 100,
        "requested_ship_date": today - datetime.timedelta(days=2),
        "status": "open",
        "on_hand_at_ship_from": 150,        # >= quantity → Precedence 2
        "open_supply_total_qty": 500.0,     # open supply exists
        "nearest_expected_arrival": supply_arrival,
    }

    mock_pool = _make_fetch_pool([row], [])

    with patch(
        "packages.tools.analyze_shipment_delay_causes_tool.get_pool",
        return_value=mock_pool,
    ):
        tool = AnalyzeShipmentDelayCausesTool()
        result = await tool.handle({}, make_ctx())

    order_rec = result.output["orders"][0]
    assert order_rec["cause"] == "unknown", (
        f"Expected 'unknown' (Precedence 2) but got '{order_rec['cause']}'"
    )
    assert result.output["cause_counts"]["unknown"] == 1
    assert result.output["cause_counts"]["upstream_supply_delay"] == 0
    assert any("CO-PREC2" in m for m in result.output["missing_data"])


async def test_analyze_delay_supply_arriving_on_ship_date_falls_to_inventory_shortage() -> None:
    """Supply arriving exactly on requested_ship_date → inventory_shortage (not upstream_supply_delay).

    Precedence 3 requires arrival AFTER requested_ship_date (strictly greater).
    If the nearest arrival equals the requested_ship_date, supply is not 'late'
    and the order falls through to Precedence 4 (inventory_shortage).
    """
    from packages.tools.analyze_shipment_delay_causes_tool import AnalyzeShipmentDelayCausesTool

    today = datetime.date.today()
    requested_ship = today - datetime.timedelta(days=2)
    supply_arrival = requested_ship  # arrives ON the ship date (not after)

    row = {
        "order_id": "CO-ONTIME-SUPPLY",
        "customer_id": "CUST-001",
        "sku_id": "SKU-097",
        "ship_from_location_id": "WH-001",
        "region": "Kanto",
        "quantity": 100,
        "requested_ship_date": requested_ship,
        "status": "open",
        "on_hand_at_ship_from": 10,          # < quantity
        "open_supply_total_qty": 200.0,      # supply exists
        "nearest_expected_arrival": supply_arrival,  # arrives exactly on ship date
    }

    mock_pool = _make_fetch_pool([row], [])

    with patch(
        "packages.tools.analyze_shipment_delay_causes_tool.get_pool",
        return_value=mock_pool,
    ):
        tool = AnalyzeShipmentDelayCausesTool()
        result = await tool.handle({}, make_ctx())

    order_rec = result.output["orders"][0]
    assert order_rec["cause"] == "inventory_shortage", (
        f"Expected 'inventory_shortage' when supply arrives exactly on ship date, "
        f"got '{order_rec['cause']}'"
    )
    assert result.output["cause_counts"]["inventory_shortage"] == 1
    assert result.output["cause_counts"]["upstream_supply_delay"] == 0


async def test_analyze_delay_carrier_delay_in_transit_past_planned_delivery() -> None:
    """in_transit shipment past planned_delivery_date → carrier_delay.

    This tests the third sub-case: status='in_transit' AND today > planned_delivery_date.
    actual_delivery_date is None (not yet delivered).
    """
    from packages.tools.analyze_shipment_delay_causes_tool import AnalyzeShipmentDelayCausesTool

    today = datetime.date.today()
    shipped_row = {
        "order_id": "CO-INTRANSIT",
        "customer_id": "CUST-001",
        "sku_id": "SKU-015",
        "region": "Kanto",
        "status": "shipped",
        "planned_ship_date": today - datetime.timedelta(days=6),
        "actual_ship_date": today - datetime.timedelta(days=6),   # on time
        "planned_delivery_date": today - datetime.timedelta(days=2),  # was due 2 days ago
        "actual_delivery_date": None,          # not yet delivered
        "shipment_status": "in_transit",       # still in transit
    }

    mock_pool = _make_fetch_pool([], [shipped_row])

    with patch(
        "packages.tools.analyze_shipment_delay_causes_tool.get_pool",
        return_value=mock_pool,
    ):
        tool = AnalyzeShipmentDelayCausesTool()
        result = await tool.handle({}, make_ctx())

    order_rec = result.output["orders"][0]
    assert order_rec["cause"] == "carrier_delay", (
        f"Expected 'carrier_delay' for in_transit past planned_delivery, "
        f"got '{order_rec['cause']}'"
    )
    assert result.output["cause_counts"]["carrier_delay"] == 1
    assert result.output["cause_counts"]["warehouse_processing_delay"] == 0


async def test_analyze_delay_cause_counts_has_all_five_keys_when_empty() -> None:
    """Empty DB → cause_counts contains all five canonical keys with value 0.

    Verifies that no key is silently omitted from the output when it has a zero count.
    """
    from packages.tools.analyze_shipment_delay_causes_tool import AnalyzeShipmentDelayCausesTool

    mock_pool = _make_fetch_pool([], [])

    with patch(
        "packages.tools.analyze_shipment_delay_causes_tool.get_pool",
        return_value=mock_pool,
    ):
        tool = AnalyzeShipmentDelayCausesTool()
        result = await tool.handle({}, make_ctx())

    expected_keys = {
        "inventory_shortage",
        "upstream_supply_delay",
        "warehouse_processing_delay",
        "carrier_delay",
        "unknown",
    }
    assert set(result.output["cause_counts"].keys()) == expected_keys


async def test_analyze_delay_multi_cause_counts_one_order_not_two() -> None:
    """An order with both warehouse and carrier delay → total_delayed=1, not 2.

    Both cause counts are incremented, but the order is a single entry
    in total_delayed and in the orders list.
    """
    from packages.tools.analyze_shipment_delay_causes_tool import AnalyzeShipmentDelayCausesTool

    today = datetime.date.today()
    shipped_row = {
        "order_id": "CO-DUAL",
        "customer_id": "CUST-001",
        "sku_id": "SKU-001",
        "region": "Kanto",
        "status": "shipped",
        "planned_ship_date": today - datetime.timedelta(days=7),
        "actual_ship_date": today - datetime.timedelta(days=4),  # 3 days late (warehouse)
        "planned_delivery_date": today - datetime.timedelta(days=4),
        "actual_delivery_date": today - datetime.timedelta(days=1),  # 3 days late (carrier)
        "shipment_status": "delivered",
    }

    mock_pool = _make_fetch_pool([], [shipped_row])

    with patch(
        "packages.tools.analyze_shipment_delay_causes_tool.get_pool",
        return_value=mock_pool,
    ):
        tool = AnalyzeShipmentDelayCausesTool()
        result = await tool.handle({}, make_ctx())

    assert result.output["total_delayed"] == 1, (
        f"Expected total_delayed=1 for one order, got {result.output['total_delayed']}"
    )
    assert len(result.output["orders"]) == 1
    assert result.output["cause_counts"]["warehouse_processing_delay"] == 1
    assert result.output["cause_counts"]["carrier_delay"] == 1


async def test_analyze_delay_mixed_unshipped_and_shipped_both_counted() -> None:
    """One unshipped (inventory_shortage) and one shipped (carrier_delay) → total_delayed=2."""
    from packages.tools.analyze_shipment_delay_causes_tool import AnalyzeShipmentDelayCausesTool

    today = datetime.date.today()

    unshipped_row = {
        "order_id": "CO-UNSHIP",
        "customer_id": "CUST-001",
        "sku_id": "SKU-002",
        "ship_from_location_id": "WH-001",
        "region": "Kanto",
        "quantity": 200,
        "requested_ship_date": today - datetime.timedelta(days=2),
        "status": "open",
        "on_hand_at_ship_from": 10,
        "open_supply_total_qty": 0,
        "nearest_expected_arrival": None,
    }
    shipped_row = {
        "order_id": "CO-SHIP",
        "customer_id": "CUST-002",
        "sku_id": "SKU-015",
        "region": "Kanto",
        "status": "shipped",
        "planned_ship_date": today - datetime.timedelta(days=6),
        "actual_ship_date": today - datetime.timedelta(days=6),
        "planned_delivery_date": today - datetime.timedelta(days=3),
        "actual_delivery_date": today - datetime.timedelta(days=1),
        "shipment_status": "delivered",
    }

    mock_pool = _make_fetch_pool([unshipped_row], [shipped_row])

    with patch(
        "packages.tools.analyze_shipment_delay_causes_tool.get_pool",
        return_value=mock_pool,
    ):
        tool = AnalyzeShipmentDelayCausesTool()
        result = await tool.handle({}, make_ctx())

    assert result.output["total_delayed"] == 2
    assert result.output["cause_counts"]["inventory_shortage"] == 1
    assert result.output["cause_counts"]["carrier_delay"] == 1
