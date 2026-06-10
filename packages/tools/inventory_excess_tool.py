from __future__ import annotations

from typing import Any, Literal

from packages.persistence.db import get_pool
from packages.tools._shared import db_error_message
from packages.tools.base import ToolContext, ToolResult


class CalculateExcessInventoryRiskTool:
    name = "calculate_excess_inventory_risk"
    description = (
        "Identify excess inventory risk by comparing on-hand stock to recent demand rate"
    )
    safety_level: Literal["read_only", "write", "hitl"] = "read_only"
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "sku_id": {"type": "string"},
            "lookback_days": {"type": "integer", "minimum": 7, "default": 90},
        },
        "required": ["sku_id"],
    }
    output_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "sku_id": {"type": "string"},
            "lookback_days": {"type": "integer"},
            "on_hand_qty": {"type": "number"},
            "avg_daily_demand": {"type": ["number", "null"]},
            "excess_units": {"type": ["number", "null"]},
            "excess_days": {"type": ["number", "null"]},
            "excess_risk_level": {"type": "string"},
            "missing_data": {"type": "array", "items": {"type": "string"}},
        },
    }

    def __init__(self, db_session: Any | None = None) -> None:
        pass

    async def handle(self, input: dict[str, Any], ctx: ToolContext) -> ToolResult:
        sku_id: str = input["sku_id"]
        lookback_days: int = int(input.get("lookback_days", 90))

        try:
            on_hand_qty, avg_daily_demand = await _fetch_excess_data(sku_id, lookback_days)
        except Exception as exc:
            return ToolResult(
                output={"error": db_error_message(exc)},
                audit_payload={
                    "sku_id": sku_id,
                    "lookback_days": lookback_days,
                    "excess_units": None,
                    "excess_risk_level": None,
                },
            )

        excess_units: float | None
        excess_days: float | None

        if avg_daily_demand is None or avg_daily_demand == 0:
            excess_units = None
            excess_days = None
            excess_risk_level = "unknown"
        else:
            excess_units = on_hand_qty - avg_daily_demand * 30
            if excess_units > 0:
                excess_days = excess_units / avg_daily_demand
            else:
                excess_days = None

            if excess_units <= 0:
                excess_risk_level = "none"
            elif excess_days is not None and excess_days <= 30:
                excess_risk_level = "low"
            elif excess_days is not None and excess_days <= 60:
                excess_risk_level = "medium"
            else:
                excess_risk_level = "high"

        missing_data: list[str] = []
        if avg_daily_demand is None or avg_daily_demand == 0:
            missing_data.append(
                f"no demand_history rows for {sku_id} in last {lookback_days} days"
            )

        return ToolResult(
            output={
                "sku_id": sku_id,
                "lookback_days": lookback_days,
                "on_hand_qty": on_hand_qty,
                "avg_daily_demand": avg_daily_demand,
                "excess_units": excess_units,
                "excess_days": excess_days,
                "excess_risk_level": excess_risk_level,
                "missing_data": missing_data,
            },
            audit_payload={
                "sku_id": sku_id,
                "lookback_days": lookback_days,
                "excess_units": excess_units,
                "excess_risk_level": excess_risk_level,
            },
        )


async def _fetch_excess_data(
    sku_id: str,
    lookback_days: int,
) -> tuple[float, float | None]:
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
              AND date >= CURRENT_DATE - ($2 * INTERVAL '1 day')
              AND is_missing IS NOT TRUE
            """,
            sku_id,
            lookback_days,
        )
        raw_avg = demand_row["avg_daily"]
        avg_daily_demand: float | None = float(raw_avg) if raw_avg is not None else None

    return on_hand_qty, avg_daily_demand


