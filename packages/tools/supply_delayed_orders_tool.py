from __future__ import annotations

import datetime
from typing import Any, Literal

from packages.persistence.db import get_pool
from packages.tools._shared import db_error_message
from packages.tools.base import ToolContext, ToolResult

_ROW_CAP = 100


class GetDelayedSupplyOrdersTool:
    name = "get_delayed_supply_orders"
    description = (
        "Retrieve supply orders that are overdue"
        " (expected_arrival < today and status != 'delivered'),"
        " with days overdue calculated"
    )
    safety_level: Literal["read_only", "write", "hitl"] = "read_only"
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "sku_id": {
                "type": "string",
                "description": "Filter by SKU; omit for all SKUs",
            },
        },
        "required": [],
    }
    output_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "sku_id": {"type": ["string", "null"]},
            "order_count": {"type": "integer"},
            "truncated": {"type": "boolean"},
            "missing_data": {"type": "array", "items": {"type": "string"}},
            "orders": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "sku_id": {"type": "string"},
                        "supplier_id": {"type": "string"},
                        "expected_arrival": {"type": "string"},
                        "days_overdue": {"type": "integer"},
                        "quantity": {"type": "number"},
                        "status": {"type": "string"},
                    },
                },
            },
        },
    }

    def __init__(self, db_session: Any | None = None) -> None:
        pass

    async def handle(self, input: dict[str, Any], ctx: ToolContext) -> ToolResult:
        sku_id: str | None = input.get("sku_id") or None

        try:
            raw_rows = await _fetch_delayed_orders(sku_id)
        except Exception as exc:
            return ToolResult(
                output={"error": db_error_message(exc)},
                audit_payload={
                    "sku_id": sku_id,
                    "order_count": 0,
                },
            )

        truncated = len(raw_rows) > _ROW_CAP
        rows = raw_rows[:_ROW_CAP]

        today = datetime.date.today()
        orders: list[dict[str, Any]] = []
        for row in rows:
            expected_arrival = row["expected_arrival"]
            if isinstance(expected_arrival, datetime.datetime):
                expected_arrival_date = expected_arrival.date()
            elif isinstance(expected_arrival, datetime.date):
                expected_arrival_date = expected_arrival
            else:
                expected_arrival_date = None

            days_overdue: int = (
                (today - expected_arrival_date).days
                if expected_arrival_date is not None
                else 0
            )
            expected_arrival_str: str = (
                expected_arrival_date.isoformat()
                if expected_arrival_date is not None
                else ""
            )

            orders.append(
                {
                    "id": str(row["id"]),
                    "sku_id": row["sku_id"],
                    "supplier_id": row["supplier_id"],
                    "expected_arrival": expected_arrival_str,
                    "days_overdue": days_overdue,
                    "quantity": float(row["quantity"]),
                    "status": row["status"],
                }
            )

        order_count = len(orders)

        return ToolResult(
            output={
                "sku_id": sku_id,
                "order_count": order_count,
                "truncated": truncated,
                "missing_data": [],
                "orders": orders,
            },
            audit_payload={
                "sku_id": sku_id,
                "order_count": order_count,
                "truncated": truncated,
            },
        )


async def _fetch_delayed_orders(
    sku_id: str | None,
) -> list[dict[str, Any]]:
    """Fetch up to _ROW_CAP + 1 rows so the caller can detect truncation."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, sku_id, supplier_id, expected_arrival, quantity, status
            FROM supply_orders
            WHERE expected_arrival < CURRENT_DATE
              AND status != 'delivered'
              AND ($1::text IS NULL OR sku_id = $1)
            ORDER BY expected_arrival ASC
            LIMIT 101
            """,
            sku_id,
        )
        return [dict(r) for r in rows]
