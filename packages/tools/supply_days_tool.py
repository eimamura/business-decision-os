from __future__ import annotations

import datetime
from typing import Any, Literal

from packages.persistence.db import get_pool
from packages.tools.base import ToolContext, ToolResult


class CalculateDaysOfSupplyTool:
    name = "calculate_days_of_supply"
    description = (
        "Calculate days of supply remaining and estimated stockout date based on "
        "current inventory and average demand"
    )
    safety_level: Literal["read_only", "write", "hitl"] = "read_only"
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "sku_id": {"type": "string"},
        },
        "required": ["sku_id"],
    }
    output_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "sku_id": {"type": "string"},
            "on_hand_qty": {"type": "number"},
            "avg_daily_demand": {"type": ["number", "null"]},
            "days_of_supply": {"type": ["number", "null"]},
            "stockout_date_estimate": {"type": ["string", "null"]},
            "reorder_signal": {"type": "boolean"},
        },
    }

    def __init__(self, db_session: Any | None = None) -> None:
        pass

    async def handle(self, input: dict[str, Any], ctx: ToolContext) -> ToolResult:
        sku_id: str = input["sku_id"]

        try:
            on_hand_qty, avg_daily_demand, lead_time_mean = await _fetch_days_of_supply_data(
                sku_id
            )
        except Exception as exc:
            return ToolResult(
                output={"error": _db_error_message(exc)},
                audit_payload={
                    "sku_id": sku_id,
                    "on_hand_qty": None,
                    "days_of_supply": None,
                },
            )

        days_of_supply: float | None
        stockout_date_estimate: str | None

        if avg_daily_demand is not None and avg_daily_demand > 0:
            days_of_supply = on_hand_qty / avg_daily_demand
            today = datetime.date.today()
            stockout_date = today + datetime.timedelta(days=days_of_supply)
            stockout_date_estimate = stockout_date.isoformat()
        else:
            days_of_supply = None
            stockout_date_estimate = None

        reorder_threshold = 14.0
        if lead_time_mean is not None:
            reorder_threshold = max(lead_time_mean, 14.0)

        reorder_signal: bool = (
            days_of_supply is not None and days_of_supply < reorder_threshold
        )

        return ToolResult(
            output={
                "sku_id": sku_id,
                "on_hand_qty": on_hand_qty,
                "avg_daily_demand": avg_daily_demand,
                "days_of_supply": days_of_supply,
                "stockout_date_estimate": stockout_date_estimate,
                "reorder_signal": reorder_signal,
            },
            audit_payload={
                "sku_id": sku_id,
                "on_hand_qty": on_hand_qty,
                "days_of_supply": days_of_supply,
            },
        )


async def _fetch_days_of_supply_data(
    sku_id: str,
) -> tuple[float, float | None, float | None]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        on_hand_row = await conn.fetchrow(
            """
            SELECT COALESCE(SUM(on_hand), 0) AS on_hand_qty
            FROM inventory_snapshot
            WHERE sku_id = $1
            """,
            sku_id,
        )
        on_hand_qty = float(on_hand_row["on_hand_qty"])

        demand_row = await conn.fetchrow(
            """
            SELECT AVG(quantity) AS avg_daily
            FROM demand_history
            WHERE sku_id = $1
              AND date >= CURRENT_DATE - (30 * INTERVAL '1 day')
              AND is_missing IS NOT TRUE
            """,
            sku_id,
        )
        raw_avg = demand_row["avg_daily"]
        avg_daily_demand: float | None = float(raw_avg) if raw_avg is not None else None

        sku_row = await conn.fetchrow(
            """
            SELECT lead_time_days_mean
            FROM sku_master
            WHERE sku_id = $1
            """,
            sku_id,
        )
        lead_time_mean: float | None = None
        if sku_row is not None and sku_row["lead_time_days_mean"] is not None:
            lead_time_mean = float(sku_row["lead_time_days_mean"])

    return on_hand_qty, avg_daily_demand, lead_time_mean


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
