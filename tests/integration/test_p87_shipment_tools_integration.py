"""T-547: Integration tests for P87 shipment tools against a real PostgreSQL database.

Requires a running PostgreSQL instance reachable via DATABASE_URL with migration 0019
applied and the P87 seed data loaded (scripts/seed_db.py).

Deterministic seed scenarios (scripts/generate_sample_data.py constants):
    CO-0001, CO-0002 → inventory_shortage    (open, on_hand << qty, no open supply)
    CO-0003, CO-0004 → upstream_supply_delay (open, on_hand << qty, supply at today+10)
    CO-0005, CO-0006 → warehouse_processing_delay (shipped late: actual_ship > planned_ship)
    CO-0007, CO-0008 → carrier_delay         (shipped on time, delivered late)

Run with:
    docker compose up -d db && uv run pytest tests/integration/test_p87_shipment_tools_integration.py -v
"""
from __future__ import annotations

import os
from uuid import uuid4

import pytest

from packages.tools.base import ToolContext

_HAS_DB = bool(os.environ.get("DATABASE_URL"))
_SKIP_NO_DB = pytest.mark.skipif(not _HAS_DB, reason="DATABASE_URL not set")


def _ctx() -> ToolContext:
    return ToolContext(
        session_id=uuid4(),
        agent_step_id=uuid4(),
        specialist_role="control",
        actor="integration_test",
        correlation_id=uuid4(),
    )


@pytest.fixture(autouse=True)
async def reset_db_pool() -> None:  # type: ignore[misc]
    """Reset the global asyncpg pool before and after each test.

    pytest-asyncio creates a new event loop per test function. The global pool
    singleton in packages/persistence/db.py is bound to the event loop in which
    it was created, so reusing it across tests causes 'loop is closed' errors.
    Resetting the module-level variable forces pool recreation in the current loop.
    """
    import packages.persistence.db as db_module

    db_module._pool = None
    yield  # type: ignore[misc]
    if db_module._pool is not None:
        await db_module._pool.close()
        db_module._pool = None


# ===========================================================================
# AnalyzeShipmentDelayCausesTool integration tests
# ===========================================================================


@_SKIP_NO_DB
async def test_analyze_delay_causes_returns_no_error() -> None:
    """Tool executes against the real DB without error."""
    from packages.tools.analyze_shipment_delay_causes_tool import AnalyzeShipmentDelayCausesTool

    tool = AnalyzeShipmentDelayCausesTool()
    result = await tool.handle({}, _ctx())

    assert "error" not in result.output, f"Unexpected error: {result.output.get('error')}"


@_SKIP_NO_DB
async def test_analyze_delay_causes_output_has_required_fields() -> None:
    """Tool output includes all required schema fields with correct types."""
    from packages.tools.analyze_shipment_delay_causes_tool import AnalyzeShipmentDelayCausesTool

    tool = AnalyzeShipmentDelayCausesTool()
    result = await tool.handle({}, _ctx())

    assert "cause_counts" in result.output
    assert "total_delayed" in result.output
    assert "truncated" in result.output
    assert "missing_data" in result.output
    assert "orders" in result.output
    assert isinstance(result.output["total_delayed"], int)
    assert isinstance(result.output["truncated"], bool)
    assert isinstance(result.output["missing_data"], list)
    assert isinstance(result.output["orders"], list)


@_SKIP_NO_DB
async def test_analyze_delay_causes_inventory_shortage_nonzero_count() -> None:
    """CO-0001 and CO-0002 seed inventory_shortage orders; count must be >= 2."""
    from packages.tools.analyze_shipment_delay_causes_tool import AnalyzeShipmentDelayCausesTool

    tool = AnalyzeShipmentDelayCausesTool()
    result = await tool.handle({}, _ctx())

    shortage_count = result.output["cause_counts"]["inventory_shortage"]
    assert shortage_count >= 2, (
        f"Expected at least 2 inventory_shortage orders (CO-0001, CO-0002), "
        f"got {shortage_count}"
    )


@_SKIP_NO_DB
async def test_analyze_delay_causes_upstream_supply_delay_nonzero_count() -> None:
    """CO-0003 and CO-0004 seed upstream_supply_delay orders; count must be >= 2."""
    from packages.tools.analyze_shipment_delay_causes_tool import AnalyzeShipmentDelayCausesTool

    tool = AnalyzeShipmentDelayCausesTool()
    result = await tool.handle({}, _ctx())

    delay_count = result.output["cause_counts"]["upstream_supply_delay"]
    assert delay_count >= 2, (
        f"Expected at least 2 upstream_supply_delay orders (CO-0003, CO-0004), "
        f"got {delay_count}"
    )


@_SKIP_NO_DB
async def test_analyze_delay_causes_warehouse_processing_delay_nonzero_count() -> None:
    """CO-0005 and CO-0006 seed warehouse_processing_delay orders; count must be >= 2."""
    from packages.tools.analyze_shipment_delay_causes_tool import AnalyzeShipmentDelayCausesTool

    tool = AnalyzeShipmentDelayCausesTool()
    result = await tool.handle({}, _ctx())

    wh_count = result.output["cause_counts"]["warehouse_processing_delay"]
    assert wh_count >= 2, (
        f"Expected at least 2 warehouse_processing_delay orders (CO-0005, CO-0006), "
        f"got {wh_count}"
    )


@_SKIP_NO_DB
async def test_analyze_delay_causes_carrier_delay_nonzero_count() -> None:
    """CO-0007 and CO-0008 seed carrier_delay orders; count must be >= 2."""
    from packages.tools.analyze_shipment_delay_causes_tool import AnalyzeShipmentDelayCausesTool

    tool = AnalyzeShipmentDelayCausesTool()
    result = await tool.handle({}, _ctx())

    carrier_count = result.output["cause_counts"]["carrier_delay"]
    assert carrier_count >= 2, (
        f"Expected at least 2 carrier_delay orders (CO-0007, CO-0008), "
        f"got {carrier_count}"
    )


@_SKIP_NO_DB
async def test_analyze_delay_causes_all_four_cause_classes_have_nonzero_count() -> None:
    """All four seeded delay classes must each have a non-zero count in one call.

    This is the definitive end-to-end assertion for T-547: the seeded data covers
    all four root-cause classes, and the tool must report each with count >= 1.
    """
    from packages.tools.analyze_shipment_delay_causes_tool import AnalyzeShipmentDelayCausesTool

    tool = AnalyzeShipmentDelayCausesTool()
    result = await tool.handle({}, _ctx())

    counts = result.output["cause_counts"]
    failures = [
        cause for cause in (
            "inventory_shortage",
            "upstream_supply_delay",
            "warehouse_processing_delay",
            "carrier_delay",
        )
        if counts.get(cause, 0) == 0
    ]
    assert not failures, (
        f"Expected non-zero count for all four seeded delay classes, "
        f"but these had zero: {failures}. Full counts: {counts}"
    )


@_SKIP_NO_DB
async def test_analyze_delay_causes_demand_shift_orders_excluded() -> None:
    """CO-DS01..CO-DS08 (status=shipped, no shipments row) must not appear in results.

    These demand-shift seed orders have status='shipped' but no shipments row,
    so the INNER JOIN on shipments excludes them. They must not inflate any count.
    """
    from packages.tools.analyze_shipment_delay_causes_tool import AnalyzeShipmentDelayCausesTool

    tool = AnalyzeShipmentDelayCausesTool()
    result = await tool.handle({}, _ctx())

    demand_shift_ids = {f"CO-DS0{i}" for i in range(1, 9)}
    returned_ids = {o["order_id"] for o in result.output["orders"]}
    overlap = demand_shift_ids & returned_ids
    assert not overlap, (
        f"Demand-shift orders should be excluded but these appeared: {overlap}"
    )


@_SKIP_NO_DB
async def test_analyze_delay_causes_order_records_have_required_fields() -> None:
    """Each order record in the output contains all expected fields."""
    from packages.tools.analyze_shipment_delay_causes_tool import AnalyzeShipmentDelayCausesTool

    tool = AnalyzeShipmentDelayCausesTool()
    result = await tool.handle({}, _ctx())

    required_keys = {"order_id", "customer_id", "sku_id", "region", "status", "cause", "evidence"}
    for order in result.output["orders"]:
        missing = required_keys - order.keys()
        assert not missing, f"Order record missing keys {missing}: {order}"


@_SKIP_NO_DB
async def test_analyze_delay_causes_cause_counts_has_all_five_keys() -> None:
    """cause_counts must contain all five canonical keys."""
    from packages.tools.analyze_shipment_delay_causes_tool import AnalyzeShipmentDelayCausesTool

    tool = AnalyzeShipmentDelayCausesTool()
    result = await tool.handle({}, _ctx())

    expected_keys = {
        "inventory_shortage",
        "upstream_supply_delay",
        "warehouse_processing_delay",
        "carrier_delay",
        "unknown",
    }
    assert set(result.output["cause_counts"].keys()) == expected_keys


# ===========================================================================
# ListUnshippedOrdersTool integration tests
# ===========================================================================


@_SKIP_NO_DB
async def test_list_unshipped_orders_returns_no_error() -> None:
    """Tool executes against the real DB without error."""
    from packages.tools.list_unshipped_orders_tool import ListUnshippedOrdersTool

    tool = ListUnshippedOrdersTool()
    result = await tool.handle({}, _ctx())

    assert "error" not in result.output, f"Unexpected error: {result.output.get('error')}"


@_SKIP_NO_DB
async def test_list_unshipped_orders_output_has_required_fields() -> None:
    """Tool output includes all required schema fields with correct types."""
    from packages.tools.list_unshipped_orders_tool import ListUnshippedOrdersTool

    tool = ListUnshippedOrdersTool()
    result = await tool.handle({}, _ctx())

    assert "order_count" in result.output
    assert "truncated" in result.output
    assert "missing_data" in result.output
    assert "orders" in result.output
    assert isinstance(result.output["order_count"], int)
    assert isinstance(result.output["truncated"], bool)
    assert isinstance(result.output["missing_data"], list)
    assert isinstance(result.output["orders"], list)


@_SKIP_NO_DB
async def test_list_unshipped_orders_returns_seeded_open_orders() -> None:
    """CO-0001 through CO-0004 are seeded as open/overdue; the tool must return >= 4."""
    from packages.tools.list_unshipped_orders_tool import ListUnshippedOrdersTool

    tool = ListUnshippedOrdersTool()
    result = await tool.handle({}, _ctx())

    count = result.output["order_count"]
    assert count >= 4, (
        f"Expected at least 4 open unshipped orders (CO-0001..CO-0004), got {count}"
    )


@_SKIP_NO_DB
async def test_list_unshipped_orders_seeded_order_ids_present() -> None:
    """CO-0001, CO-0002, CO-0003, CO-0004 must all appear in the output."""
    from packages.tools.list_unshipped_orders_tool import ListUnshippedOrdersTool

    tool = ListUnshippedOrdersTool()
    result = await tool.handle({}, _ctx())

    returned_ids = {o["order_id"] for o in result.output["orders"]}
    expected_ids = {"CO-0001", "CO-0002", "CO-0003", "CO-0004"}
    missing = expected_ids - returned_ids
    assert not missing, (
        f"Expected seeded unshipped orders {expected_ids} in output, "
        f"but these were missing: {missing}"
    )


@_SKIP_NO_DB
async def test_list_unshipped_orders_order_count_matches_orders_length() -> None:
    """order_count field must equal len(orders)."""
    from packages.tools.list_unshipped_orders_tool import ListUnshippedOrdersTool

    tool = ListUnshippedOrdersTool()
    result = await tool.handle({}, _ctx())

    assert result.output["order_count"] == len(result.output["orders"])


@_SKIP_NO_DB
async def test_list_unshipped_orders_each_order_has_required_fields() -> None:
    """Each returned order record contains all expected output schema fields."""
    from packages.tools.list_unshipped_orders_tool import ListUnshippedOrdersTool

    tool = ListUnshippedOrdersTool()
    result = await tool.handle({}, _ctx())

    required_keys = {
        "order_id",
        "customer_id",
        "sku_id",
        "ship_from_location_id",
        "region",
        "quantity",
        "order_date",
        "requested_ship_date",
        "status",
        "days_overdue",
        "on_hand_at_ship_from",
        "open_inbound_supply",
    }
    for order in result.output["orders"]:
        missing = required_keys - order.keys()
        assert not missing, f"Order record missing keys {missing}: {order}"


@_SKIP_NO_DB
async def test_list_unshipped_orders_open_inbound_supply_has_required_fields() -> None:
    """Each open_inbound_supply dict contains the required three fields."""
    from packages.tools.list_unshipped_orders_tool import ListUnshippedOrdersTool

    tool = ListUnshippedOrdersTool()
    result = await tool.handle({}, _ctx())

    supply_required = {"total_qty", "nearest_expected_arrival", "any_supply_delayed_past_ship_date"}
    for order in result.output["orders"]:
        supply = order["open_inbound_supply"]
        missing = supply_required - supply.keys()
        assert not missing, (
            f"open_inbound_supply for {order['order_id']} missing keys {missing}: {supply}"
        )


@_SKIP_NO_DB
async def test_list_unshipped_orders_overdue_orders_have_positive_days_overdue() -> None:
    """CO-0001..CO-0004 are seeded with requested_ship_date=today-2 → days_overdue >= 1."""
    from packages.tools.list_unshipped_orders_tool import ListUnshippedOrdersTool

    tool = ListUnshippedOrdersTool()
    result = await tool.handle({}, _ctx())

    overdue_ids = {"CO-0001", "CO-0002", "CO-0003", "CO-0004"}
    for order in result.output["orders"]:
        if order["order_id"] in overdue_ids:
            assert order["days_overdue"] >= 1, (
                f"Expected days_overdue >= 1 for overdue order {order['order_id']}, "
                f"got {order['days_overdue']}"
            )


@_SKIP_NO_DB
async def test_list_unshipped_orders_upstream_supply_orders_have_inbound_supply() -> None:
    """CO-0003 and CO-0004 (upstream_supply_delay SKUs) must have total_qty > 0.

    SKU-001 and SKU-003 have pending supply at today+10; the tool should report
    open inbound supply context for these orders.
    """
    from packages.tools.list_unshipped_orders_tool import ListUnshippedOrdersTool

    tool = ListUnshippedOrdersTool()
    result = await tool.handle({}, _ctx())

    supply_delay_ids = {"CO-0003", "CO-0004"}
    for order in result.output["orders"]:
        if order["order_id"] in supply_delay_ids:
            supply = order["open_inbound_supply"]
            assert supply["total_qty"] > 0, (
                f"Expected open inbound supply for {order['order_id']} "
                f"(upstream_supply_delay SKU), got total_qty={supply['total_qty']}"
            )
            assert supply["any_supply_delayed_past_ship_date"] is True, (
                f"Expected any_supply_delayed_past_ship_date=True for {order['order_id']}"
            )
