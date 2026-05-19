from __future__ import annotations

from typing import Any

from packages.tools.base import ToolContext, ToolResult


class SimulationTool:
    name = "simulate_inventory"
    description = "Run a deterministic inventory simulation for a SKU and order quantity"
    requires_approval = False
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "sku_id": {"type": "string"},
            "order_qty": {"type": "number"},
            "horizon_days": {"type": "integer", "minimum": 1},
        },
        "required": ["sku_id", "order_qty", "horizon_days"],
    }
    output_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "sku_id": {"type": "string"},
            "ending_on_hand": {"type": "number"},
            "stockout_days": {"type": "integer"},
            "mean_lead_time_days": {"type": "integer"},
        },
    }

    async def handle(self, input: dict[str, Any], ctx: ToolContext) -> ToolResult:
        sku_id: str = input.get("sku_id", "")
        order_qty: float = float(input.get("order_qty", 0.0))
        horizon_days: int = int(input.get("horizon_days", 90))

        ending_on_hand = order_qty * 0.3
        stockout_days = max(0, 5 - int(order_qty / 100))
        mean_lead_time_days = 14

        return ToolResult(
            output={
                "sku_id": sku_id,
                "ending_on_hand": ending_on_hand,
                "stockout_days": stockout_days,
                "mean_lead_time_days": mean_lead_time_days,
            },
            audit_payload={
                "sku_id": sku_id,
                "order_qty": order_qty,
                "horizon_days": horizon_days,
            },
        )
