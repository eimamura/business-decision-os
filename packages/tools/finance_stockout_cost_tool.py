from __future__ import annotations

from typing import Any, Literal

from packages.persistence.db import get_pool
from packages.tools.base import ToolContext, ToolResult


class CalculateStockoutCostImpactTool:
    name = "calculate_stockout_cost_impact"
    description = "Calculate opportunity cost of a stockout for a SKU"
    safety_level: Literal["read_only", "write", "hitl"] = "read_only"
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "sku_id": {"type": "string"},
            "shortage_units": {"type": "number", "minimum": 0},
        },
        "required": ["sku_id", "shortage_units"],
    }
    output_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "sku_id": {"type": "string"},
            "shortage_units": {"type": "number"},
            "unit_stockout_cost": {"type": ["number", "null"]},
            "total_stockout_cost": {"type": ["number", "null"]},
            "opportunity_cost_estimate": {"type": ["number", "null"]},
            "period_label": {"type": ["string", "null"]},
        },
    }

    def __init__(self, db_session: Any | None = None) -> None:
        pass

    async def handle(self, input: dict[str, Any], ctx: ToolContext) -> ToolResult:
        sku_id: str = input["sku_id"]
        shortage_units: float = float(input["shortage_units"])

        unit_stockout_cost: float | None = None
        total_stockout_cost: float | None = None
        opportunity_cost_estimate: float | None = None
        period_label: str | None = None

        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT stockout_cost, cogs, period_start
                    FROM cost_master
                    WHERE sku_id = $1
                    ORDER BY period_start DESC
                    LIMIT 1
                    """,
                    sku_id,
                )
        except Exception as exc:
            return ToolResult(
                output={"error": _db_error_message(exc)},
                audit_payload={
                    "sku_id": sku_id,
                    "shortage_units": shortage_units,
                    "total_stockout_cost": None,
                },
            )

        if row is not None:
            unit_stockout_cost = float(row["stockout_cost"])
            total_stockout_cost = shortage_units * unit_stockout_cost
            opportunity_cost_estimate = shortage_units * float(row["cogs"])
            period_label = row["period_start"].isoformat()

        return ToolResult(
            output={
                "sku_id": sku_id,
                "shortage_units": shortage_units,
                "unit_stockout_cost": unit_stockout_cost,
                "total_stockout_cost": total_stockout_cost,
                "opportunity_cost_estimate": opportunity_cost_estimate,
                "period_label": period_label,
            },
            audit_payload={
                "sku_id": sku_id,
                "shortage_units": shortage_units,
                "total_stockout_cost": total_stockout_cost,
            },
        )


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
