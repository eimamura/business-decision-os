from __future__ import annotations

from typing import Any

from packages.tools.base import ToolContext, ToolResult


class OptimizerTool:
    name = "optimize_replenishment"
    description = "Enumerate MOQ multiples and return top 3 candidates by total supply chain cost"
    requires_approval = False
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "sku_id": {"type": "string"},
            "moq": {"type": "number"},
            "horizon_days": {"type": "integer", "minimum": 1},
        },
        "required": ["sku_id", "moq", "horizon_days"],
    }
    output_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "candidates": {"type": "array"},
        },
    }

    async def handle(self, input: dict[str, Any], ctx: ToolContext) -> ToolResult:
        sku_id: str = input.get("sku_id", "")
        moq: float = float(input.get("moq", 100.0))
        horizon_days: int = int(input.get("horizon_days", 90))

        multiples = [0, 1, 2, 3, 4, 5]
        candidates = []
        for m in multiples:
            order_qty = moq * m
            total_cost = order_qty * 1.2
            candidates.append({
                "order_qty": order_qty,
                "total_supply_chain_cost": total_cost,
                "constraints_satisfied": ["MOQ"] if m >= 1 else [],
                "constraints_violated": [] if m >= 1 else ["MOQ"],
            })

        feasible = [c for c in candidates if not c["constraints_violated"]]
        feasible.sort(key=lambda c: c["total_supply_chain_cost"])  # type: ignore[arg-type,return-value]
        top3 = feasible[:3]

        if len(top3) < 3:
            top3 = candidates[:3]

        return ToolResult(
            output={"candidates": top3},
            audit_payload={
                "sku_id": sku_id,
                "moq": moq,
                "horizon_days": horizon_days,
                "candidate_count": len(top3),
            },
        )
