"""T-543/T-544: Unit tests for P87 B-02 shipment tools.

Covers:
- ListUnshippedOrdersTool: schema contract, truncation, missing_data for no inventory snapshot,
  days_overdue calculation, open_inbound_supply context.
- AnalyzeShipmentDelayCausesTool: schema contract, classification precedence
  (inventory_shortage > upstream_supply_delay for unshipped; warehouse + carrier can co-exist),
  shipped-without-shipment-row orders excluded, missing_data for unknown.
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


def _make_fetch_pool(*fetch_sequences: list[Any]) -> MagicMock:
    """Pool that returns successive fetch() results from fetch_sequences in order."""
    mock_conn = AsyncMock()
    mock_conn.fetch.side_effect = list(fetch_sequences)
    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_pool


def _order_row(
    order_id: str = "CO-0001",
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


def _shipment_delayed_row(
    order_id: str = "CO-0005",
    sku_id: str = "SKU-010",
    planned_ship_days_ago: int = 7,
    actual_ship_days_ago: int = 4,
    planned_delivery_days_ago: int = 4,
    actual_delivery_days_ago: int = 1,
    shipment_status: str = "delivered",
) -> dict[str, Any]:
    today = datetime.date.today()
    return {
        "order_id": order_id,
        "customer_id": "CUST-005",
        "sku_id": sku_id,
        "region": "Kanto",
        "status": "shipped",
        "planned_ship_date": today - datetime.timedelta(days=planned_ship_days_ago),
        "actual_ship_date": today - datetime.timedelta(days=actual_ship_days_ago),
        "planned_delivery_date": today - datetime.timedelta(days=planned_delivery_days_ago),
        "actual_delivery_date": today - datetime.timedelta(days=actual_delivery_days_ago),
        "shipment_status": shipment_status,
    }


# ===========================================================================
# ListUnshippedOrdersTool
# ===========================================================================


async def test_list_unshipped_orders_returns_required_fields():
    """Output must include order_count, truncated, missing_data, orders."""
    from packages.tools.list_unshipped_orders_tool import ListUnshippedOrdersTool

    rows = [_order_row()]
    mock_pool = _make_fetch_pool(rows)

    with patch("packages.tools.list_unshipped_orders_tool.get_pool", return_value=mock_pool):
        tool = ListUnshippedOrdersTool()
        result = await tool.handle({}, make_ctx())

    assert "order_count" in result.output
    assert "truncated" in result.output
    assert "missing_data" in result.output
    assert "orders" in result.output


async def test_list_unshipped_orders_days_overdue_calculated_correctly():
    """days_overdue must equal today - requested_ship_date in days."""
    from packages.tools.list_unshipped_orders_tool import ListUnshippedOrdersTool

    days_overdue = 3
    rows = [_order_row(days_overdue=days_overdue)]
    mock_pool = _make_fetch_pool(rows)

    with patch("packages.tools.list_unshipped_orders_tool.get_pool", return_value=mock_pool):
        tool = ListUnshippedOrdersTool()
        result = await tool.handle({}, make_ctx())

    assert result.output["orders"][0]["days_overdue"] == days_overdue


async def test_list_unshipped_orders_no_inventory_snapshot_sets_missing_data():
    """When on_hand_at_ship_from is None, missing_data must have an entry."""
    from packages.tools.list_unshipped_orders_tool import ListUnshippedOrdersTool

    rows = [_order_row(on_hand=None)]
    mock_pool = _make_fetch_pool(rows)

    with patch("packages.tools.list_unshipped_orders_tool.get_pool", return_value=mock_pool):
        tool = ListUnshippedOrdersTool()
        result = await tool.handle({}, make_ctx())

    assert len(result.output["missing_data"]) > 0
    assert result.output["orders"][0]["on_hand_at_ship_from"] is None


async def test_list_unshipped_orders_truncated_at_50():
    """DB returns 51 rows → order_count=50, truncated=True."""
    from packages.tools.list_unshipped_orders_tool import ListUnshippedOrdersTool

    rows = [_order_row(order_id=f"CO-{i:04d}") for i in range(51)]
    mock_pool = _make_fetch_pool(rows)

    with patch("packages.tools.list_unshipped_orders_tool.get_pool", return_value=mock_pool):
        tool = ListUnshippedOrdersTool()
        result = await tool.handle({}, make_ctx())

    assert result.output["order_count"] == 50
    assert result.output["truncated"] is True


async def test_list_unshipped_orders_not_truncated_at_50():
    """DB returns exactly 50 rows → truncated=False."""
    from packages.tools.list_unshipped_orders_tool import ListUnshippedOrdersTool

    rows = [_order_row(order_id=f"CO-{i:04d}") for i in range(50)]
    mock_pool = _make_fetch_pool(rows)

    with patch("packages.tools.list_unshipped_orders_tool.get_pool", return_value=mock_pool):
        tool = ListUnshippedOrdersTool()
        result = await tool.handle({}, make_ctx())

    assert result.output["order_count"] == 50
    assert result.output["truncated"] is False


async def test_list_unshipped_orders_supply_delayed_past_ship_date():
    """When open supply arrives after requested_ship_date → any_supply_delayed_past_ship_date=True."""
    from packages.tools.list_unshipped_orders_tool import ListUnshippedOrdersTool

    today = datetime.date.today()
    supply_arrival = today + datetime.timedelta(days=10)  # after ship date (2 days ago)
    rows = [_order_row(days_overdue=2, supply_qty=100.0, supply_arrival=supply_arrival)]
    mock_pool = _make_fetch_pool(rows)

    with patch("packages.tools.list_unshipped_orders_tool.get_pool", return_value=mock_pool):
        tool = ListUnshippedOrdersTool()
        result = await tool.handle({}, make_ctx())

    supply_ctx = result.output["orders"][0]["open_inbound_supply"]
    assert supply_ctx["any_supply_delayed_past_ship_date"] is True
    assert supply_ctx["total_qty"] == 100.0


async def test_list_unshipped_orders_db_error_returns_error_key():
    """DB exception → output has 'error' key."""
    from packages.tools.list_unshipped_orders_tool import ListUnshippedOrdersTool

    with patch(
        "packages.tools.list_unshipped_orders_tool.get_pool",
        side_effect=RuntimeError("DATABASE_URL not configured"),
    ):
        tool = ListUnshippedOrdersTool()
        result = await tool.handle({}, make_ctx())

    assert "error" in result.output
    assert "database" in result.output["error"].lower()


# ===========================================================================
# AnalyzeShipmentDelayCausesTool
# ===========================================================================


async def test_analyze_delay_causes_returns_required_fields():
    """Output must include cause_counts, total_delayed, truncated, missing_data, orders."""
    from packages.tools.analyze_shipment_delay_causes_tool import AnalyzeShipmentDelayCausesTool

    mock_pool = _make_fetch_pool([], [])  # no rows

    with patch(
        "packages.tools.analyze_shipment_delay_causes_tool.get_pool",
        return_value=mock_pool,
    ):
        tool = AnalyzeShipmentDelayCausesTool()
        result = await tool.handle({}, make_ctx())

    assert "cause_counts" in result.output
    assert "total_delayed" in result.output
    assert "truncated" in result.output
    assert "missing_data" in result.output
    assert "orders" in result.output


async def test_analyze_delay_causes_upstream_supply_delay_when_open_supply_exists():
    """upstream_supply_delay when on_hand < quantity AND open supply exists but arrives late.

    Spec: the SKU's risk is an inbound delay — supply is coming but too late.
    Classification: on_hand < quantity AND open supply has expected_arrival > requested_ship_date.
    """
    from packages.tools.analyze_shipment_delay_causes_tool import AnalyzeShipmentDelayCausesTool

    today = datetime.date.today()
    supply_arrival = today + datetime.timedelta(days=10)
    requested_ship = today - datetime.timedelta(days=2)  # overdue

    unshipped_row = {
        "order_id": "CO-0003",
        "customer_id": "CUST-002",
        "sku_id": "SKU-001",
        "ship_from_location_id": "WH-001",
        "region": "Tohoku",
        "quantity": 150,
        "requested_ship_date": requested_ship,
        "status": "open",
        "on_hand_at_ship_from": 10,   # << 150 → stock insufficient
        "open_supply_total_qty": 500,  # open supply exists
        "nearest_expected_arrival": supply_arrival,  # arrives after requested_ship_date
    }

    mock_pool = _make_fetch_pool([unshipped_row], [])

    with patch(
        "packages.tools.analyze_shipment_delay_causes_tool.get_pool",
        return_value=mock_pool,
    ):
        tool = AnalyzeShipmentDelayCausesTool()
        result = await tool.handle({}, make_ctx())

    assert result.output["total_delayed"] == 1
    order_rec = result.output["orders"][0]
    assert order_rec["cause"] == "upstream_supply_delay"
    assert result.output["cause_counts"]["upstream_supply_delay"] == 1
    assert result.output["cause_counts"]["inventory_shortage"] == 0


async def test_analyze_delay_causes_inventory_shortage_when_no_open_supply():
    """inventory_shortage when on_hand < quantity AND no open supply order at all.

    Spec: nothing is inbound — the root cause is an absence of supply.
    """
    from packages.tools.analyze_shipment_delay_causes_tool import AnalyzeShipmentDelayCausesTool

    today = datetime.date.today()
    requested_ship = today - datetime.timedelta(days=2)  # overdue

    unshipped_row = {
        "order_id": "CO-0001",
        "customer_id": "CUST-001",
        "sku_id": "SKU-002",
        "ship_from_location_id": "WH-001",
        "region": "Kanto",
        "quantity": 200,
        "requested_ship_date": requested_ship,
        "status": "open",
        "on_hand_at_ship_from": 10,       # << 200 → shortage
        "open_supply_total_qty": 0,        # no open supply at all
        "nearest_expected_arrival": None,  # nothing inbound
    }

    mock_pool = _make_fetch_pool([unshipped_row], [])

    with patch(
        "packages.tools.analyze_shipment_delay_causes_tool.get_pool",
        return_value=mock_pool,
    ):
        tool = AnalyzeShipmentDelayCausesTool()
        result = await tool.handle({}, make_ctx())

    assert result.output["total_delayed"] == 1
    order_rec = result.output["orders"][0]
    assert order_rec["cause"] == "inventory_shortage"
    assert result.output["cause_counts"]["inventory_shortage"] == 1
    assert result.output["cause_counts"]["upstream_supply_delay"] == 0


async def test_analyze_delay_causes_unknown_when_sufficient_stock_but_unshipped():
    """unknown when on_hand >= quantity but order is overdue and unshipped.

    Spec: stock is present but order has not shipped — not a supply problem.
    The order appears in missing_data for human investigation.
    """
    from packages.tools.analyze_shipment_delay_causes_tool import AnalyzeShipmentDelayCausesTool

    today = datetime.date.today()
    requested_ship = today - datetime.timedelta(days=2)  # overdue

    unshipped_row = {
        "order_id": "CO-0099",
        "customer_id": "CUST-001",
        "sku_id": "SKU-010",
        "ship_from_location_id": "WH-001",
        "region": "Kanto",
        "quantity": 100,
        "requested_ship_date": requested_ship,
        "status": "open",
        "on_hand_at_ship_from": 200,  # >= quantity → not a supply problem
        "open_supply_total_qty": 0,
        "nearest_expected_arrival": None,
    }

    mock_pool = _make_fetch_pool([unshipped_row], [])

    with patch(
        "packages.tools.analyze_shipment_delay_causes_tool.get_pool",
        return_value=mock_pool,
    ):
        tool = AnalyzeShipmentDelayCausesTool()
        result = await tool.handle({}, make_ctx())

    order_rec = result.output["orders"][0]
    assert order_rec["cause"] == "unknown"
    assert result.output["cause_counts"]["unknown"] == 1
    assert result.output["cause_counts"]["inventory_shortage"] == 0
    # missing_data must contain an entry for this order
    assert any("CO-0099" in m for m in result.output["missing_data"])


async def test_analyze_delay_causes_warehouse_delay_classified():
    """Shipped order with actual_ship_date > planned_ship_date → warehouse_processing_delay."""
    from packages.tools.analyze_shipment_delay_causes_tool import AnalyzeShipmentDelayCausesTool

    today = datetime.date.today()
    shipped_row = {
        "order_id": "CO-0005",
        "customer_id": "CUST-005",
        "sku_id": "SKU-010",
        "region": "Kanto",
        "status": "shipped",
        "planned_ship_date": today - datetime.timedelta(days=7),
        "actual_ship_date": today - datetime.timedelta(days=4),  # 3 days late
        "planned_delivery_date": today - datetime.timedelta(days=4),
        "actual_delivery_date": today - datetime.timedelta(days=1),
        "shipment_status": "delivered",
    }

    mock_pool = _make_fetch_pool([], [shipped_row])  # no unshipped rows

    with patch(
        "packages.tools.analyze_shipment_delay_causes_tool.get_pool",
        return_value=mock_pool,
    ):
        tool = AnalyzeShipmentDelayCausesTool()
        result = await tool.handle({}, make_ctx())

    order_rec = result.output["orders"][0]
    assert "warehouse_processing_delay" in order_rec["cause"]
    assert result.output["cause_counts"]["warehouse_processing_delay"] >= 1


async def test_analyze_delay_causes_carrier_delay_classified():
    """Shipped on time but actual_delivery > planned_delivery → carrier_delay."""
    from packages.tools.analyze_shipment_delay_causes_tool import AnalyzeShipmentDelayCausesTool

    today = datetime.date.today()
    shipped_row = {
        "order_id": "CO-0007",
        "customer_id": "CUST-007",
        "sku_id": "SKU-015",
        "region": "Kanto",
        "status": "shipped",
        "planned_ship_date": today - datetime.timedelta(days=6),
        "actual_ship_date": today - datetime.timedelta(days=6),  # on time
        "planned_delivery_date": today - datetime.timedelta(days=3),
        "actual_delivery_date": today - datetime.timedelta(days=1),  # 2 days late
        "shipment_status": "delivered",
    }

    mock_pool = _make_fetch_pool([], [shipped_row])

    with patch(
        "packages.tools.analyze_shipment_delay_causes_tool.get_pool",
        return_value=mock_pool,
    ):
        tool = AnalyzeShipmentDelayCausesTool()
        result = await tool.handle({}, make_ctx())

    order_rec = result.output["orders"][0]
    assert order_rec["cause"] == "carrier_delay"
    assert result.output["cause_counts"]["carrier_delay"] == 1
    assert result.output["cause_counts"]["warehouse_processing_delay"] == 0


async def test_analyze_delay_causes_both_warehouse_and_carrier():
    """Order shipped late AND delivered late → both warehouse_processing_delay AND carrier_delay."""
    from packages.tools.analyze_shipment_delay_causes_tool import AnalyzeShipmentDelayCausesTool

    today = datetime.date.today()
    shipped_row = {
        "order_id": "CO-TEST",
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

    order_rec = result.output["orders"][0]
    # Both causes must appear in the comma-separated cause string
    assert "warehouse_processing_delay" in order_rec["cause"]
    assert "carrier_delay" in order_rec["cause"]
    # Both counters incremented
    assert result.output["cause_counts"]["warehouse_processing_delay"] == 1
    assert result.output["cause_counts"]["carrier_delay"] == 1


async def test_analyze_delay_causes_unknown_when_no_inventory_no_supply():
    """Unshipped order with no inventory snapshot and no open supply → unknown + missing_data."""
    from packages.tools.analyze_shipment_delay_causes_tool import AnalyzeShipmentDelayCausesTool

    today = datetime.date.today()
    unshipped_row = {
        "order_id": "CO-UNKNOWN",
        "customer_id": "CUST-001",
        "sku_id": "SKU-999",
        "ship_from_location_id": "WH-001",
        "region": "Other",
        "quantity": 100,
        "requested_ship_date": today - datetime.timedelta(days=1),
        "status": "open",
        "on_hand_at_ship_from": None,
        "open_supply_total_qty": 0,
        "nearest_expected_arrival": None,
    }

    mock_pool = _make_fetch_pool([unshipped_row], [])

    with patch(
        "packages.tools.analyze_shipment_delay_causes_tool.get_pool",
        return_value=mock_pool,
    ):
        tool = AnalyzeShipmentDelayCausesTool()
        result = await tool.handle({}, make_ctx())

    order_rec = result.output["orders"][0]
    assert order_rec["cause"] == "unknown"
    assert result.output["cause_counts"]["unknown"] == 1
    # missing_data contains at least one entry (inventory snapshot + unknown classification)
    assert len(result.output["missing_data"]) >= 1


async def test_analyze_delay_causes_db_error_returns_error_key():
    """DB exception → output has 'error' key."""
    from packages.tools.analyze_shipment_delay_causes_tool import AnalyzeShipmentDelayCausesTool

    with patch(
        "packages.tools.analyze_shipment_delay_causes_tool.get_pool",
        side_effect=RuntimeError("DATABASE_URL not configured"),
    ):
        tool = AnalyzeShipmentDelayCausesTool()
        result = await tool.handle({}, make_ctx())

    assert "error" in result.output
    assert "database" in result.output["error"].lower()


async def test_analyze_delay_causes_empty_db_returns_zero_counts():
    """Empty DB → zero totals, no missing_data, no truncation."""
    from packages.tools.analyze_shipment_delay_causes_tool import AnalyzeShipmentDelayCausesTool

    mock_pool = _make_fetch_pool([], [])

    with patch(
        "packages.tools.analyze_shipment_delay_causes_tool.get_pool",
        return_value=mock_pool,
    ):
        tool = AnalyzeShipmentDelayCausesTool()
        result = await tool.handle({}, make_ctx())

    assert result.output["total_delayed"] == 0
    assert result.output["truncated"] is False
    assert result.output["missing_data"] == []
    for cause, count in result.output["cause_counts"].items():
        assert count == 0, f"Expected 0 for {cause}, got {count}"


async def test_analyze_delay_causes_truncated_at_50():
    """More than 50 classified orders → truncated=True, orders list capped at 50."""
    from packages.tools.analyze_shipment_delay_causes_tool import AnalyzeShipmentDelayCausesTool

    today = datetime.date.today()
    # Generate 51 shipped-late rows (easier to construct than unshipped)
    shipped_rows = [
        {
            "order_id": f"CO-{i:04d}",
            "customer_id": "CUST-001",
            "sku_id": "SKU-001",
            "region": "Kanto",
            "status": "shipped",
            "planned_ship_date": today - datetime.timedelta(days=7),
            "actual_ship_date": today - datetime.timedelta(days=4),
            "planned_delivery_date": today - datetime.timedelta(days=4),
            "actual_delivery_date": today - datetime.timedelta(days=1),
            "shipment_status": "delivered",
        }
        for i in range(51)
    ]

    mock_pool = _make_fetch_pool([], shipped_rows)

    with patch(
        "packages.tools.analyze_shipment_delay_causes_tool.get_pool",
        return_value=mock_pool,
    ):
        tool = AnalyzeShipmentDelayCausesTool()
        result = await tool.handle({}, make_ctx())

    assert result.output["total_delayed"] == 51
    assert result.output["truncated"] is True
    assert len(result.output["orders"]) == 50
