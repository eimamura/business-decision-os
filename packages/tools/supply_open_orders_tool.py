from __future__ import annotations

import datetime
from typing import Any, Literal

from packages.persistence.db import get_pool
from packages.tools._shared import db_error_message
from packages.tools.base import ToolContext, ToolResult

_ROW_CAP = 100


class GetOpenSupplyOrdersTool:
    name = "get_open_supply_orders"
    description = (
        "Retrieve open (pending or in-transit) supply orders for a SKU or all SKUs"
    )
    safety_level: Literal["read_only", "write", "hitl"] = "read_only"
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "sku_id": {
                "type": "string",
                "description": "Filter by SKU; omit for all SKUs",
            },
            "status_filter": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Order statuses to include; "
                    "default ['pending','confirmed','in_transit']"
                ),
            },
        },
        "required": [],
    }
    output_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "sku_id": {"type": ["string", "null"]},
            "order_count": {"type": "integer"},
            "total_incoming_qty": {"type": "number"},
            "truncated": {"type": "boolean"},
            "missing_data": {"type": "array", "items": {"type": "string"}},
            "orders": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "sku_id": {"type": "string"},
                        "supplier_id": {"type": "string"},
                        "order_date": {"type": "string"},
                        "expected_arrival": {"type": "string"},
                        "quantity": {"type": "number"},
                        "status": {"type": "string"},
                        "days_until_arrival": {"type": ["integer", "null"]},
                    },
                },
            },
        },
    }

    def __init__(self, db_session: Any | None = None) -> None:
        pass

    async def handle(self, input: dict[str, Any], ctx: ToolContext) -> ToolResult:
        sku_id: str | None = input.get("sku_id") or None
        raw_status_filter = input.get("status_filter")
        status_filter: list[str] = (
            list(raw_status_filter)
            if raw_status_filter
            else ["pending", "confirmed", "in_transit"]
        )

        try:
            raw_rows = await _fetch_open_orders(sku_id, status_filter)
        except Exception as exc:
            return ToolResult(
                output={"error": db_error_message(exc)},
                audit_payload={
                    "sku_id": sku_id,
                    "status_filter": status_filter,
                    "order_count": 0,
                },
            )

        truncated = len(raw_rows) > _ROW_CAP
        rows = raw_rows[:_ROW_CAP]

        today = datetime.date.today()
        orders: list[dict[str, Any]] = []
        for row in rows:
            expected_arrival = row["expected_arrival"]
            if expected_arrival is not None:
                if isinstance(expected_arrival, datetime.datetime):
                    expected_arrival_date = expected_arrival.date()
                elif isinstance(expected_arrival, datetime.date):
                    expected_arrival_date = expected_arrival
                else:
                    expected_arrival_date = None
                days_until_arrival: int | None = (
                    (expected_arrival_date - today).days
                    if expected_arrival_date is not None
                    else None
                )
                expected_arrival_str: str | None = (
                    expected_arrival_date.isoformat()
                    if expected_arrival_date is not None
                    else None
                )
            else:
                days_until_arrival = None
                expected_arrival_str = None

            order_date = row["order_date"]
            if isinstance(order_date, datetime.datetime):
                order_date_str = order_date.date().isoformat()
            elif isinstance(order_date, datetime.date):
                order_date_str = order_date.isoformat()
            else:
                order_date_str = str(order_date) if order_date is not None else ""

            orders.append(
                {
                    "sku_id": row["sku_id"],
                    "supplier_id": row["supplier_id"],
                    "order_date": order_date_str,
                    "expected_arrival": expected_arrival_str,
                    "quantity": float(row["quantity"]),
                    "status": row["status"],
                    "days_until_arrival": days_until_arrival,
                }
            )

        order_count = len(orders)
        total_incoming_qty = sum(o["quantity"] for o in orders)

        return ToolResult(
            output={
                "sku_id": sku_id,
                "order_count": order_count,
                "total_incoming_qty": total_incoming_qty,
                "truncated": truncated,
                "missing_data": [],
                "orders": orders,
            },
            audit_payload={
                "sku_id": sku_id,
                "status_filter": status_filter,
                "order_count": order_count,
                "truncated": truncated,
            },
        )


async def _fetch_open_orders(
    sku_id: str | None, status_filter: list[str]
) -> list[dict[str, Any]]:
    """Fetch up to _ROW_CAP + 1 rows so the caller can detect truncation."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT sku_id, supplier_id, order_date, expected_arrival, quantity, status
            FROM supply_orders
            WHERE status = ANY($1)
              AND ($2::text IS NULL OR sku_id = $2)
            ORDER BY expected_arrival ASC NULLS LAST
            LIMIT 101
            """,
            status_filter,
            sku_id,
        )
        return [dict(r) for r in rows]
