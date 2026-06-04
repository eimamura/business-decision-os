from __future__ import annotations

from typing import Any, Literal

from packages.persistence.db import get_pool
from packages.tools.base import ToolContext, ToolResult


class CalculateExpediteCostTool:
    name = "calculate_expedite_cost"
    description = "Calculate the cost of expediting an urgent supply order for a SKU"
    safety_level: Literal["read_only", "write", "hitl"] = "read_only"
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "sku_id": {"type": "string"},
            "expedite_units": {"type": "number", "minimum": 0},
            "expedite_multiplier": {
                "type": "number",
                "minimum": 1.0,
                "default": 2.0,
                "description": "Expedite cost as multiple of standard ordering cost",
            },
        },
        "required": ["sku_id", "expedite_units"],
    }
    output_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "sku_id": {"type": "string"},
            "expedite_units": {"type": "number"},
            "expedite_multiplier": {"type": "number"},
            "base_ordering_cost": {"type": ["number", "null"]},
            "expedite_premium": {"type": ["number", "null"]},
            "total_expedite_cost": {"type": ["number", "null"]},
            "cost_vs_stockout_comparison": {"type": ["string", "null"]},
        },
    }

    def __init__(self, db_session: Any | None = None) -> None:
        pass

    async def handle(self, input: dict[str, Any], ctx: ToolContext) -> ToolResult:
        sku_id: str = input["sku_id"]
        expedite_units: float = float(input["expedite_units"])
        expedite_multiplier: float = float(input.get("expedite_multiplier", 2.0))

        base_ordering_cost: float | None = None
        expedite_premium: float | None = None
        total_expedite_cost: float | None = None
        cost_vs_stockout_comparison: str | None = None

        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT ordering_cost, stockout_cost
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
                    "expedite_units": expedite_units,
                    "total_expedite_cost": None,
                },
            )

        if row is not None:
            ordering_cost = float(row["ordering_cost"])
            base_ordering_cost = expedite_units * ordering_cost
            expedite_premium = base_ordering_cost * (expedite_multiplier - 1.0)
            total_expedite_cost = base_ordering_cost * expedite_multiplier

            stockout_cost = row["stockout_cost"]
            if stockout_cost is not None:
                stockout_total = expedite_units * float(stockout_cost)
                diff = abs(total_expedite_cost - stockout_total)
                if total_expedite_cost < stockout_total:
                    cost_vs_stockout_comparison = (
                        f"expedite is cheaper than stockout by ${diff:,.2f}"
                    )
                else:
                    cost_vs_stockout_comparison = (
                        f"stockout is cheaper than expedite by ${diff:,.2f}"
                    )

        return ToolResult(
            output={
                "sku_id": sku_id,
                "expedite_units": expedite_units,
                "expedite_multiplier": expedite_multiplier,
                "base_ordering_cost": base_ordering_cost,
                "expedite_premium": expedite_premium,
                "total_expedite_cost": total_expedite_cost,
                "cost_vs_stockout_comparison": cost_vs_stockout_comparison,
            },
            audit_payload={
                "sku_id": sku_id,
                "expedite_units": expedite_units,
                "total_expedite_cost": total_expedite_cost,
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
