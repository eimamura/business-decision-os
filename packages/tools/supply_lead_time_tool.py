from __future__ import annotations

import datetime
import statistics
from typing import Any, Literal

from packages.persistence.db import get_pool
from packages.tools.base import ToolContext, ToolResult


class AnalyzeSupplyLeadTimeTool:
    name = "analyze_supply_lead_time"
    description = "Analyze historical supplier lead times from supply order history"
    safety_level: Literal["read_only", "write", "hitl"] = "read_only"
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "sku_id": {
                "type": "string",
                "description": "Filter by SKU; omit for all SKUs",
            },
            "lookback_days": {
                "type": "integer",
                "minimum": 7,
                "default": 180,
            },
        },
        "required": [],
    }
    output_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "sku_id": {"type": ["string", "null"]},
            "lookback_days": {"type": "integer"},
            "order_count": {"type": "integer"},
            "avg_lead_time_days": {"type": ["number", "null"]},
            "min_lead_time_days": {"type": ["integer", "null"]},
            "max_lead_time_days": {"type": ["integer", "null"]},
            "lead_time_std": {"type": ["number", "null"]},
            "supplier_count": {"type": "integer"},
        },
    }

    def __init__(self, db_session: Any | None = None) -> None:
        pass

    async def handle(self, input: dict[str, Any], ctx: ToolContext) -> ToolResult:
        sku_id: str | None = input.get("sku_id") or None
        lookback_days: int = int(input.get("lookback_days", 180))

        try:
            rows = await _fetch_lead_time_rows(sku_id, lookback_days)
        except Exception as exc:
            return ToolResult(
                output={"error": _db_error_message(exc)},
                audit_payload={
                    "sku_id": sku_id,
                    "lookback_days": lookback_days,
                    "order_count": 0,
                },
            )

        order_count = len(rows)

        if order_count == 0:
            return ToolResult(
                output={
                    "sku_id": sku_id,
                    "lookback_days": lookback_days,
                    "order_count": 0,
                    "avg_lead_time_days": None,
                    "min_lead_time_days": None,
                    "max_lead_time_days": None,
                    "lead_time_std": None,
                    "supplier_count": 0,
                },
                audit_payload={
                    "sku_id": sku_id,
                    "lookback_days": lookback_days,
                    "order_count": 0,
                },
            )

        lead_times: list[int] = []
        supplier_ids: set[str] = set()

        for row in rows:
            order_date = row["order_date"]
            expected_arrival = row["expected_arrival"]
            supplier_id = row["supplier_id"]

            if isinstance(order_date, datetime.datetime):
                order_date = order_date.date()
            if isinstance(expected_arrival, datetime.datetime):
                expected_arrival = expected_arrival.date()

            if order_date is not None and expected_arrival is not None:
                lead_time = (expected_arrival - order_date).days
                lead_times.append(lead_time)

            if supplier_id is not None:
                supplier_ids.add(str(supplier_id))

        supplier_count = len(supplier_ids)

        if not lead_times:
            return ToolResult(
                output={
                    "sku_id": sku_id,
                    "lookback_days": lookback_days,
                    "order_count": order_count,
                    "avg_lead_time_days": None,
                    "min_lead_time_days": None,
                    "max_lead_time_days": None,
                    "lead_time_std": None,
                    "supplier_count": supplier_count,
                },
                audit_payload={
                    "sku_id": sku_id,
                    "lookback_days": lookback_days,
                    "order_count": order_count,
                },
            )

        avg_lead_time = statistics.mean(lead_times)
        min_lead_time = min(lead_times)
        max_lead_time = max(lead_times)
        lead_time_std: float | None = (
            statistics.stdev(lead_times) if len(lead_times) >= 2 else 0.0
        )

        return ToolResult(
            output={
                "sku_id": sku_id,
                "lookback_days": lookback_days,
                "order_count": order_count,
                "avg_lead_time_days": avg_lead_time,
                "min_lead_time_days": min_lead_time,
                "max_lead_time_days": max_lead_time,
                "lead_time_std": lead_time_std,
                "supplier_count": supplier_count,
            },
            audit_payload={
                "sku_id": sku_id,
                "lookback_days": lookback_days,
                "order_count": order_count,
            },
        )


async def _fetch_lead_time_rows(
    sku_id: str | None, lookback_days: int
) -> list[dict[str, Any]]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT order_date, expected_arrival, supplier_id
            FROM supply_orders
            WHERE order_date >= CURRENT_DATE - ($1 * INTERVAL '1 day')
              AND ($2::text IS NULL OR sku_id = $2)
              AND expected_arrival IS NOT NULL
            """,
            lookback_days,
            sku_id,
        )
        return [dict(r) for r in rows]


def _db_error_message(exc: Exception) -> str:
    message = str(exc).lower()
    class_name = exc.__class__.__name__.lower()
    module_name = exc.__class__.__module__.lower()
    if isinstance(exc, RuntimeError) and "database_url" in message:
        return "no database connection"
    if "asyncpg" in module_name and (
        "connection" in class_name
        or "connection" in message
        or "connect call failed" in message
    ):
        return "no database connection"
    return str(exc)
