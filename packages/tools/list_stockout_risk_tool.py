from __future__ import annotations

import datetime
from typing import Any, Literal

from packages.persistence.db import get_pool
from packages.tools._shared import classify_stockout_risk, db_error_message
from packages.tools.base import ToolContext, ToolResult

_OPEN_STATUSES = ["pending", "confirmed", "in_transit"]

_RISK_LEVEL_ORDER: dict[str, int] = {
    "none": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}


class ListStockoutRiskTool:
    """Retrieve stockout risk for all SKUs in a single bulk query.

    Unlike ``calculate_stockout_risk`` (which requires a specific ``sku_id``),
    this tool fetches every SKU at once and filters by ``min_risk_level`` so
    the agent can answer "which products have stockout risk?" with one call
    instead of N database round-trips.
    """

    name = "list_stockout_risk"
    description = (
        "List all SKUs with stockout risk at or above a minimum level "
        "using a single bulk query. "
        "Use this tool instead of looping calculate_stockout_risk per SKU."
    )
    safety_level: Literal["read_only", "write", "hitl"] = "read_only"
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "horizon_days": {
                "type": "integer",
                "minimum": 1,
                "default": 7,
                "description": "Planning horizon in days for demand and supply projections",
            },
            "min_risk_level": {
                "type": "string",
                "enum": ["low", "medium", "high", "critical"],
                "default": "medium",
                "description": (
                    "Minimum risk level to include in results "
                    "(low < medium < high < critical)"
                ),
            },
        },
        "required": [],
    }
    output_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "sku_id": {"type": "string"},
                        "on_hand_qty": {"type": "number"},
                        "demand_forecast": {"type": "number"},
                        "incoming_supply": {"type": "number"},
                        "projected_ending_stock": {"type": "number"},
                        "risk_level": {"type": "string"},
                        "stockout_date_estimate": {"type": ["string", "null"]},
                    },
                },
            },
            "count": {"type": "integer"},
            "missing_data": {"type": "array", "items": {"type": "string"}},
        },
    }

    def __init__(self, db_session: Any | None = None) -> None:
        pass

    async def handle(self, input: dict[str, Any], ctx: ToolContext) -> ToolResult:
        horizon_days: int = int(input.get("horizon_days") or 7)
        min_risk_level: str = str(input.get("min_risk_level") or "medium")

        # Clamp to valid values; default to "medium" if unrecognised.
        if min_risk_level not in _RISK_LEVEL_ORDER:
            min_risk_level = "medium"

        try:
            raw_rows = await _fetch_all_stockout_risk(horizon_days)
        except Exception as exc:
            return ToolResult(
                output={"error": db_error_message(exc)},
                audit_payload={
                    "horizon_days": horizon_days,
                    "min_risk_level": min_risk_level,
                    "count": 0,
                },
            )

        min_order = _RISK_LEVEL_ORDER[min_risk_level]
        items: list[dict[str, Any]] = []
        today = datetime.date.today()

        for row in raw_rows:
            on_hand_qty = float(row["on_hand_qty"])
            avg_daily = float(row["avg_daily"])
            incoming_supply = float(row["incoming_supply"])

            demand_forecast = avg_daily * horizon_days
            projected_ending_stock = on_hand_qty + incoming_supply - demand_forecast

            risk_level = classify_stockout_risk(projected_ending_stock, demand_forecast)

            # Apply filter — skip "none" risk and items below the threshold.
            row_order = _RISK_LEVEL_ORDER.get(risk_level, 0)
            if risk_level == "none" or row_order < min_order:
                continue

            stockout_date_estimate: str | None
            if projected_ending_stock >= 0:
                stockout_date_estimate = None
            elif avg_daily > 0:
                days_until_stockout = (on_hand_qty + incoming_supply) / avg_daily
                stockout_date = today + datetime.timedelta(days=int(days_until_stockout))
                stockout_date_estimate = stockout_date.isoformat()
            else:
                stockout_date_estimate = None

            items.append(
                {
                    "sku_id": row["sku_id"],
                    "on_hand_qty": on_hand_qty,
                    "demand_forecast": demand_forecast,
                    "incoming_supply": incoming_supply,
                    "projected_ending_stock": projected_ending_stock,
                    "risk_level": risk_level,
                    "stockout_date_estimate": stockout_date_estimate,
                }
            )

        # Sort by risk descending (critical first), then by projected_ending_stock ascending.
        items.sort(
            key=lambda x: (
                -_RISK_LEVEL_ORDER.get(x["risk_level"], 0),
                x["projected_ending_stock"],
            )
        )

        return ToolResult(
            output={"items": items, "count": len(items), "missing_data": []},
            audit_payload={
                "horizon_days": horizon_days,
                "min_risk_level": min_risk_level,
                "count": len(items),
            },
        )


async def _fetch_all_stockout_risk(horizon_days: int) -> list[dict[str, Any]]:
    """Single query aggregating inventory, demand, and supply for every SKU."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                inv.sku_id,
                COALESCE(inv.on_hand_qty, 0)      AS on_hand_qty,
                COALESCE(dh.avg_daily, 0)          AS avg_daily,
                COALESCE(so.incoming_supply, 0)    AS incoming_supply
            FROM (
                SELECT sku_id, SUM(on_hand) AS on_hand_qty
                FROM inventory_snapshot
                GROUP BY sku_id
            ) inv
            LEFT JOIN (
                SELECT sku_id, AVG(quantity) AS avg_daily
                FROM demand_history
                WHERE date >= CURRENT_DATE - (30 * INTERVAL '1 day')
                  AND is_missing IS NOT TRUE
                GROUP BY sku_id
            ) dh ON dh.sku_id = inv.sku_id
            LEFT JOIN (
                SELECT sku_id, SUM(quantity) AS incoming_supply
                FROM supply_orders
                WHERE status = ANY($1)
                  AND expected_arrival <= CURRENT_DATE + ($2 * INTERVAL '1 day')
                GROUP BY sku_id
            ) so ON so.sku_id = inv.sku_id
            ORDER BY inv.sku_id
            """,
            _OPEN_STATUSES,
            horizon_days,
        )
        return [dict(r) for r in rows]


