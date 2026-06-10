from __future__ import annotations

from typing import Any, Literal

from packages.persistence.db import get_pool
from packages.tools._shared import db_error_message
from packages.tools.base import ToolContext, ToolResult


class CompareCostScenariosTool:
    name = "compare_cost_scenarios"
    description = (
        "Compare total cost impact across three supply scenarios: "
        "do_nothing, full_expedite, and partial_fulfill"
    )
    safety_level: Literal["read_only", "write", "hitl"] = "read_only"
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "sku_id": {"type": "string"},
            "shortage_units": {
                "type": "number",
                "minimum": 0,
                "description": "Units of shortage to address",
            },
            "horizon_days": {"type": "integer", "minimum": 1, "default": 30},
        },
        "required": ["sku_id", "shortage_units"],
    }
    output_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "sku_id": {"type": "string"},
            "shortage_units": {"type": "number"},
            "scenarios": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "total_cost": {"type": ["number", "null"]},
                        "cost_components": {
                            "type": "object",
                            "properties": {
                                "holding": {"type": "number"},
                                "stockout": {"type": "number"},
                                "ordering": {"type": "number"},
                            },
                        },
                        "description": {"type": "string"},
                    },
                },
            },
            "recommended_scenario": {"type": ["string", "null"]},
            "recommendation_reason": {"type": ["string", "null"]},
            "missing_data": {"type": "array", "items": {"type": "string"}},
        },
    }

    def __init__(self, db_session: Any | None = None) -> None:
        pass

    async def handle(self, input: dict[str, Any], ctx: ToolContext) -> ToolResult:
        sku_id: str = input["sku_id"]
        shortage_units: float = float(input["shortage_units"])
        recommended_scenario: str | None = None
        recommendation_reason: str | None = None

        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT stockout_cost, ordering_cost, holding_cost
                    FROM cost_master
                    WHERE sku_id = $1
                    ORDER BY period_start DESC
                    LIMIT 1
                    """,
                    sku_id,
                )
        except Exception as exc:
            return ToolResult(
                output={"error": db_error_message(exc)},
                audit_payload={
                    "sku_id": sku_id,
                    "shortage_units": shortage_units,
                    "recommended_scenario": None,
                },
            )

        if row is None:
            empty_scenarios: list[dict[str, Any]] = [
                {
                    "name": "do_nothing",
                    "total_cost": None,
                    "cost_components": {"holding": 0.0, "stockout": 0.0, "ordering": 0.0},
                    "description": "Accept all shortage units as stockouts; no expedite action.",
                },
                {
                    "name": "full_expedite",
                    "total_cost": None,
                    "cost_components": {"holding": 0.0, "stockout": 0.0, "ordering": 0.0},
                    "description": (
                        "Order all shortage units via expedite at 2x standard ordering cost."
                    ),
                },
                {
                    "name": "partial_fulfill",
                    "total_cost": None,
                    "cost_components": {"holding": 0.0, "stockout": 0.0, "ordering": 0.0},
                    "description": (
                        "Fill 50% of shortage via expedite, accept 50% as stockout."
                    ),
                },
            ]
            return ToolResult(
                output={
                    "sku_id": sku_id,
                    "shortage_units": shortage_units,
                    "scenarios": empty_scenarios,
                    "recommended_scenario": None,
                    "recommendation_reason": None,
                    "missing_data": [f"no cost_master row for {sku_id}"],
                },
                audit_payload={
                    "sku_id": sku_id,
                    "shortage_units": shortage_units,
                    "recommended_scenario": None,
                },
            )

        stockout_cost = float(row["stockout_cost"])
        ordering_cost = float(row["ordering_cost"])

        # Scenario 1: do_nothing — all units become stockouts
        do_nothing_stockout = shortage_units * stockout_cost
        do_nothing_cost = do_nothing_stockout

        # Scenario 2: full_expedite — all units ordered at 2x expedite multiplier
        full_expedite_ordering = shortage_units * ordering_cost * 2.0
        full_expedite_cost = full_expedite_ordering

        # Scenario 3: partial_fulfill — 50% expedite, 50% stockout
        partial_ordering = shortage_units * 0.5 * ordering_cost * 2.0
        partial_stockout = shortage_units * 0.5 * stockout_cost
        partial_fulfill_cost = partial_ordering + partial_stockout

        scenarios: list[dict[str, Any]] = [
            {
                "name": "do_nothing",
                "total_cost": do_nothing_cost,
                "cost_components": {
                    "holding": 0.0,
                    "stockout": do_nothing_stockout,
                    "ordering": 0.0,
                },
                "description": "Accept all shortage units as stockouts; no expedite action taken.",
            },
            {
                "name": "full_expedite",
                "total_cost": full_expedite_cost,
                "cost_components": {
                    "holding": 0.0,
                    "stockout": 0.0,
                    "ordering": full_expedite_ordering,
                },
                "description": (
                    "Order all shortage units via expedite at 2x standard ordering cost."
                ),
            },
            {
                "name": "partial_fulfill",
                "total_cost": partial_fulfill_cost,
                "cost_components": {
                    "holding": 0.0,
                    "stockout": partial_stockout,
                    "ordering": partial_ordering,
                },
                "description": (
                    "Fill 50% of shortage via expedite, accept 50% as stockout."
                ),
            },
        ]

        # Determine recommendation: lowest total cost
        named_costs: list[tuple[str, float]] = [
            ("do_nothing", do_nothing_cost),
            ("full_expedite", full_expedite_cost),
            ("partial_fulfill", partial_fulfill_cost),
        ]
        named_costs.sort(key=lambda t: t[1])
        recommended_scenario = named_costs[0][0]
        best_cost = named_costs[0][1]
        second_cost = named_costs[1][1]
        second_name = named_costs[1][0]
        savings = second_cost - best_cost
        recommendation_reason = (
            f"{recommended_scenario} saves ${savings:,.2f} vs {second_name}"
        )

        return ToolResult(
            output={
                "sku_id": sku_id,
                "shortage_units": shortage_units,
                "scenarios": scenarios,
                "recommended_scenario": recommended_scenario,
                "recommendation_reason": recommendation_reason,
                "missing_data": [],
            },
            audit_payload={
                "sku_id": sku_id,
                "shortage_units": shortage_units,
                "recommended_scenario": recommended_scenario,
            },
        )


