from __future__ import annotations

import datetime
from typing import Any, Literal

from packages.persistence.db import get_pool
from packages.tools.base import ToolContext, ToolResult

_OPEN_STATUSES = ["pending", "confirmed", "in_transit"]


class CalculateStockoutRiskTool:
    name = "calculate_stockout_risk"
    description = (
        "Project inventory position over a horizon to estimate stockout risk and date"
    )
    safety_level: Literal["read_only", "write", "hitl"] = "read_only"
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "sku_id": {"type": "string"},
            "horizon_days": {"type": "integer", "minimum": 1, "default": 30},
        },
        "required": ["sku_id"],
    }
    output_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "sku_id": {"type": "string"},
            "horizon_days": {"type": "integer"},
            "on_hand_qty": {"type": "number"},
            "demand_forecast": {"type": "number"},
            "incoming_supply": {"type": "number"},
            "projected_ending_stock": {"type": "number"},
            "stockout_date_estimate": {"type": ["string", "null"]},
            "risk_level": {"type": "string"},
        },
    }

    def __init__(self, db_session: Any | None = None) -> None:
        pass

    async def handle(self, input: dict[str, Any], ctx: ToolContext) -> ToolResult:
        sku_id: str = input["sku_id"]
        horizon_days: int = int(input.get("horizon_days", 30))

        try:
            on_hand_qty, avg_daily, incoming_supply = await _fetch_stockout_risk_data(
                sku_id, horizon_days
            )
        except Exception as exc:
            return ToolResult(
                output={"error": _db_error_message(exc)},
                audit_payload={
                    "sku_id": sku_id,
                    "horizon_days": horizon_days,
                    "projected_ending_stock": None,
                    "risk_level": None,
                },
            )

        demand_forecast = avg_daily * horizon_days
        projected_ending_stock = on_hand_qty + incoming_supply - demand_forecast

        stockout_date_estimate: str | None
        if projected_ending_stock >= 0:
            stockout_date_estimate = None
        else:
            if avg_daily > 0:
                days_until_stockout = (on_hand_qty + incoming_supply) / avg_daily
                stockout_date = (
                    datetime.date.today() + datetime.timedelta(days=int(days_until_stockout))
                )
                stockout_date_estimate = stockout_date.isoformat()
            else:
                stockout_date_estimate = None

        risk_level = _classify_stockout_risk(projected_ending_stock, demand_forecast)

        return ToolResult(
            output={
                "sku_id": sku_id,
                "horizon_days": horizon_days,
                "on_hand_qty": on_hand_qty,
                "demand_forecast": demand_forecast,
                "incoming_supply": incoming_supply,
                "projected_ending_stock": projected_ending_stock,
                "stockout_date_estimate": stockout_date_estimate,
                "risk_level": risk_level,
            },
            audit_payload={
                "sku_id": sku_id,
                "horizon_days": horizon_days,
                "projected_ending_stock": projected_ending_stock,
                "risk_level": risk_level,
            },
        )


def _classify_stockout_risk(projected_ending_stock: float, demand_forecast: float) -> str:
    if demand_forecast == 0:
        return "none"
    if projected_ending_stock < 0:
        return "critical"
    ratio = projected_ending_stock / demand_forecast
    if ratio >= 0.5:
        return "low"
    if ratio >= 0.1:
        return "medium"
    return "high"


async def _fetch_stockout_risk_data(
    sku_id: str,
    horizon_days: int,
) -> tuple[float, float, float]:
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
            SELECT COALESCE(AVG(quantity), 0) AS avg_daily
            FROM demand_history
            WHERE sku_id = $1
              AND date >= CURRENT_DATE - (30 * INTERVAL '1 day')
              AND is_missing IS NOT TRUE
            """,
            sku_id,
        )
        avg_daily = float(demand_row["avg_daily"])

        supply_row = await conn.fetchrow(
            """
            SELECT COALESCE(SUM(quantity), 0) AS incoming_supply
            FROM supply_orders
            WHERE sku_id = $1
              AND status = ANY($2)
              AND expected_arrival <= CURRENT_DATE + ($3 * INTERVAL '1 day')
            """,
            sku_id,
            _OPEN_STATUSES,
            horizon_days,
        )
        incoming_supply = float(supply_row["incoming_supply"])

    return on_hand_qty, avg_daily, incoming_supply


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
