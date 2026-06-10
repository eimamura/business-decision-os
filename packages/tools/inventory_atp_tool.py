from __future__ import annotations

import datetime
from typing import Any, Literal

from packages.persistence.db import get_pool
from packages.tools._shared import db_error_message
from packages.tools.base import ToolContext, ToolResult

_OPEN_STATUSES = ["pending", "confirmed", "in_transit"]


class GetAvailableToPromiseTool:
    name = "get_available_to_promise"
    description = (
        "Calculate available-to-promise (ATP) quantity combining on-hand stock and "
        "confirmed incoming supply"
    )
    safety_level: Literal["read_only", "write", "hitl"] = "read_only"
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "sku_id": {"type": "string"},
            "warehouse_id": {"type": "string"},
        },
        "required": ["sku_id"],
    }
    output_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "sku_id": {"type": "string"},
            "warehouse_id": {"type": ["string", "null"]},
            "on_hand_qty": {"type": "number"},
            "on_order_incoming": {"type": "number"},
            "atp_units": {"type": "number"},
            "atp_date_horizon": {"type": "string"},
            "missing_data": {"type": "array", "items": {"type": "string"}},
        },
    }

    def __init__(self, db_session: Any | None = None) -> None:
        pass

    async def handle(self, input: dict[str, Any], ctx: ToolContext) -> ToolResult:
        sku_id: str = input["sku_id"]
        warehouse_id: str | None = input.get("warehouse_id")

        try:
            on_hand_qty, on_order_incoming = await _fetch_atp_data(sku_id, warehouse_id)
        except Exception as exc:
            return ToolResult(
                output={"error": db_error_message(exc)},
                audit_payload={
                    "sku_id": sku_id,
                    "warehouse_id": warehouse_id,
                    "atp_units": None,
                },
            )

        atp_units = on_hand_qty + on_order_incoming
        atp_date_horizon = (
            datetime.date.today() + datetime.timedelta(days=30)
        ).isoformat()

        return ToolResult(
            output={
                "sku_id": sku_id,
                "warehouse_id": warehouse_id,
                "on_hand_qty": on_hand_qty,
                "on_order_incoming": on_order_incoming,
                "atp_units": atp_units,
                "atp_date_horizon": atp_date_horizon,
                "missing_data": [],
            },
            audit_payload={
                "sku_id": sku_id,
                "warehouse_id": warehouse_id,
                "atp_units": atp_units,
            },
        )


async def _fetch_atp_data(
    sku_id: str,
    warehouse_id: str | None,
) -> tuple[float, float]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        on_hand_row = await conn.fetchrow(
            """
            SELECT COALESCE(SUM(on_hand), 0) AS on_hand_qty
            FROM inventory_snapshot
            WHERE sku_id = $1
              AND ($2::text IS NULL OR warehouse_id = $2)
            """,
            sku_id,
            warehouse_id,
        )
        on_hand_qty = float(on_hand_row["on_hand_qty"])

        supply_row = await conn.fetchrow(
            """
            SELECT COALESCE(SUM(quantity), 0) AS on_order_incoming
            FROM supply_orders
            WHERE sku_id = $1
              AND status = ANY($2)
            """,
            sku_id,
            _OPEN_STATUSES,
        )
        on_order_incoming = float(supply_row["on_order_incoming"])

    return on_hand_qty, on_order_incoming


