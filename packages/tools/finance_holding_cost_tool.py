from __future__ import annotations

from typing import Any, Literal

from packages.persistence.db import get_pool
from packages.tools.base import ToolContext, ToolResult


class CalculateHoldingCostImpactTool:
    name = "calculate_holding_cost_impact"
    description = "Calculate inventory holding cost for excess stock of a SKU"
    safety_level: Literal["read_only", "write", "hitl"] = "read_only"
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "sku_id": {"type": "string"},
            "excess_units": {
                "type": "number",
                "minimum": 0,
                "description": "Units of excess inventory above demand forecast",
            },
        },
        "required": ["sku_id", "excess_units"],
    }
    output_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "sku_id": {"type": "string"},
            "excess_units": {"type": "number"},
            "unit_holding_cost": {"type": ["number", "null"]},
            "total_holding_cost": {"type": ["number", "null"]},
            "annualized_holding_cost": {"type": ["number", "null"]},
            "period_label": {"type": ["string", "null"]},
        },
    }

    def __init__(self, db_session: Any | None = None) -> None:
        pass

    async def handle(self, input: dict[str, Any], ctx: ToolContext) -> ToolResult:
        sku_id: str = input["sku_id"]
        excess_units: float = float(input["excess_units"])

        unit_holding_cost: float | None = None
        total_holding_cost: float | None = None
        annualized_holding_cost: float | None = None
        period_label: str | None = None

        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT holding_cost, period_start
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
                    "excess_units": excess_units,
                    "total_holding_cost": None,
                },
            )

        if row is not None:
            unit_holding_cost = float(row["holding_cost"])
            total_holding_cost = excess_units * unit_holding_cost
            annualized_holding_cost = total_holding_cost * 12
            period_label = row["period_start"].isoformat()

        return ToolResult(
            output={
                "sku_id": sku_id,
                "excess_units": excess_units,
                "unit_holding_cost": unit_holding_cost,
                "total_holding_cost": total_holding_cost,
                "annualized_holding_cost": annualized_holding_cost,
                "period_label": period_label,
            },
            audit_payload={
                "sku_id": sku_id,
                "excess_units": excess_units,
                "total_holding_cost": total_holding_cost,
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
