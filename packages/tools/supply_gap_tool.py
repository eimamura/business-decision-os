from __future__ import annotations

from typing import Any, Literal

from packages.persistence.db import get_pool
from packages.tools.base import ToolContext, ToolResult

_OPEN_STATUSES = ["pending", "confirmed", "in_transit"]


class CalculateSupplyGapTool:
    name = "calculate_supply_gap"
    description = (
        "Calculate the supply gap between forecasted demand and available supply "
        "(on-hand + incoming orders) over a horizon"
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
            "incoming_qty": {"type": "number"},
            "total_available": {"type": "number"},
            "forecast_demand": {"type": "number"},
            "gap_units": {"type": "number"},
            "gap_pct": {"type": ["number", "null"]},
            "risk_level": {"type": "string"},
        },
    }

    def __init__(self, db_session: Any | None = None) -> None:
        pass

    async def handle(self, input: dict[str, Any], ctx: ToolContext) -> ToolResult:
        sku_id: str = input["sku_id"]
        horizon_days: int = int(input.get("horizon_days", 30))

        try:
            on_hand_qty, incoming_qty, avg_daily_demand = await _fetch_supply_gap_data(
                sku_id, horizon_days
            )
        except Exception as exc:
            return ToolResult(
                output={"error": _db_error_message(exc)},
                audit_payload={
                    "sku_id": sku_id,
                    "horizon_days": horizon_days,
                    "gap_units": None,
                    "risk_level": None,
                },
            )

        forecast_demand = avg_daily_demand * horizon_days
        total_available = on_hand_qty + incoming_qty
        gap_units = forecast_demand - total_available

        gap_pct: float | None
        if forecast_demand > 0:
            gap_pct = gap_units / forecast_demand * 100
        else:
            gap_pct = None

        risk_level = _classify_risk(gap_units, gap_pct)

        return ToolResult(
            output={
                "sku_id": sku_id,
                "horizon_days": horizon_days,
                "on_hand_qty": on_hand_qty,
                "incoming_qty": incoming_qty,
                "total_available": total_available,
                "forecast_demand": forecast_demand,
                "gap_units": gap_units,
                "gap_pct": gap_pct,
                "risk_level": risk_level,
            },
            audit_payload={
                "sku_id": sku_id,
                "horizon_days": horizon_days,
                "gap_units": gap_units,
                "risk_level": risk_level,
            },
        )


def _classify_risk(gap_units: float, gap_pct: float | None) -> str:
    if gap_units <= 0:
        return "none"
    if gap_pct is None:
        return "critical"
    if gap_pct < 10:
        return "low"
    if gap_pct < 25:
        return "medium"
    if gap_pct < 50:
        return "high"
    return "critical"


async def _fetch_supply_gap_data(
    sku_id: str, horizon_days: int
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

        incoming_row = await conn.fetchrow(
            """
            SELECT COALESCE(SUM(quantity), 0) AS incoming_qty
            FROM supply_orders
            WHERE sku_id = $1
              AND status = ANY($2)
              AND expected_arrival <= CURRENT_DATE + ($3 * INTERVAL '1 day')
            """,
            sku_id,
            _OPEN_STATUSES,
            horizon_days,
        )
        incoming_qty = float(incoming_row["incoming_qty"])

        demand_row = await conn.fetchrow(
            """
            SELECT COALESCE(AVG(quantity), 0) AS avg_daily
            FROM demand_history
            WHERE sku_id = $1
              AND date >= CURRENT_DATE - (90 * INTERVAL '1 day')
              AND is_missing IS NOT TRUE
            """,
            sku_id,
        )
        avg_daily_demand = float(demand_row["avg_daily"])

    return on_hand_qty, incoming_qty, avg_daily_demand


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
