from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from packages.tools.base import ToolContext
from packages.tools.supply_delayed_orders_tool import GetDelayedSupplyOrdersTool


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


def _delayed_order_row(
    sku_id: str = "SKU-A",
    supplier_id: str = "SUP-1",
    quantity: float = 50.0,
    status: str = "pending",
    expected_arrival: datetime.date | None = None,
    row_id: str | None = None,
) -> dict:
    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    return {
        "id": row_id or str(uuid4()),
        "sku_id": sku_id,
        "supplier_id": supplier_id,
        "expected_arrival": expected_arrival or yesterday,
        "quantity": quantity,
        "status": status,
    }


async def test_delayed_orders_returns_overdue_orders_with_days_overdue_computed():
    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    rows = [_delayed_order_row(expected_arrival=yesterday)]
    mock_pool = make_pool(rows)

    with patch("packages.tools.supply_delayed_orders_tool.get_pool", return_value=mock_pool):
        tool = GetDelayedSupplyOrdersTool()
        result = await tool.handle({}, make_ctx())

    assert result.output["order_count"] == 1
    orders = result.output["orders"]
    assert len(orders) == 1
    assert orders[0]["days_overdue"] >= 1


async def test_delayed_orders_days_overdue_matches_calendar_distance():
    five_days_ago = datetime.date.today() - datetime.timedelta(days=5)
    rows = [_delayed_order_row(expected_arrival=five_days_ago, status="pending")]
    mock_pool = make_pool(rows)

    with patch("packages.tools.supply_delayed_orders_tool.get_pool", return_value=mock_pool):
        tool = GetDelayedSupplyOrdersTool()
        result = await tool.handle({}, make_ctx())

    assert result.output["orders"][0]["days_overdue"] == 5


async def test_delayed_orders_empty_result_returns_empty_list():
    mock_pool = make_pool([])

    with patch("packages.tools.supply_delayed_orders_tool.get_pool", return_value=mock_pool):
        tool = GetDelayedSupplyOrdersTool()
        result = await tool.handle({}, make_ctx())

    assert result.output["order_count"] == 0
    assert result.output["orders"] == []


async def test_delayed_orders_db_error_returns_error_key():
    with patch(
        "packages.tools.supply_delayed_orders_tool.get_pool",
        side_effect=RuntimeError("database_url not set"),
    ):
        tool = GetDelayedSupplyOrdersTool()
        result = await tool.handle({}, make_ctx())

    assert result.output.get("error") is not None


async def test_delayed_orders_sku_id_filter_passed_through():
    """sku_id filter is forwarded to the DB query (verified via mock_conn.fetch args)."""
    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    rows = [_delayed_order_row(sku_id="SKU-B", expected_arrival=yesterday)]
    mock_conn = AsyncMock()
    mock_conn.fetch.return_value = rows
    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    with patch("packages.tools.supply_delayed_orders_tool.get_pool", return_value=mock_pool):
        tool = GetDelayedSupplyOrdersTool()
        result = await tool.handle({"sku_id": "SKU-B"}, make_ctx())

    assert result.output["sku_id"] == "SKU-B"
    assert result.output["order_count"] == 1
    # Verify fetch was called with the sku_id argument
    call_args = mock_conn.fetch.call_args
    assert "SKU-B" in call_args.args or "SKU-B" in (call_args.kwargs or {}).values()
