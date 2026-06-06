from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from packages.tools.base import ToolContext
from packages.tools.supply_open_orders_tool import GetOpenSupplyOrdersTool


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


def _order_row(
    sku_id: str,
    supplier_id: str,
    quantity: float,
    status: str,
    order_date: datetime.date | None = None,
    expected_arrival: datetime.date | None = None,
) -> dict:
    return {
        "sku_id": sku_id,
        "supplier_id": supplier_id,
        "order_date": order_date or datetime.date(2026, 5, 1),
        "expected_arrival": expected_arrival or datetime.date(2026, 6, 15),
        "quantity": quantity,
        "status": status,
    }


async def test_open_orders_returns_pending_orders():
    rows = [
        _order_row("SKU-A", "SUP-1", 100.0, "pending"),
        _order_row("SKU-A", "SUP-2", 200.0, "in_transit"),
    ]
    mock_pool = make_pool(rows)

    with patch("packages.tools.supply_open_orders_tool.get_pool", return_value=mock_pool):
        tool = GetOpenSupplyOrdersTool()
        result = await tool.handle({"sku_id": "SKU-A"}, make_ctx())

    assert result.output["order_count"] == 2
    assert result.output["total_incoming_qty"] == 300.0


async def test_open_orders_no_results_returns_empty():
    mock_pool = make_pool([])

    with patch("packages.tools.supply_open_orders_tool.get_pool", return_value=mock_pool):
        tool = GetOpenSupplyOrdersTool()
        result = await tool.handle({}, make_ctx())

    assert result.output["order_count"] == 0
    assert result.output["orders"] == []


async def test_open_orders_db_error_returns_error_key():
    mock_pool = MagicMock()
    mock_pool.acquire.side_effect = RuntimeError("DATABASE_URL not set")

    with patch("packages.tools.supply_open_orders_tool.get_pool", side_effect=RuntimeError("DATABASE_URL not set")):
        tool = GetOpenSupplyOrdersTool()
        result = await tool.handle({}, make_ctx())

    assert "error" in result.output
