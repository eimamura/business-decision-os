from __future__ import annotations

import statistics
from typing import Any, Literal

from packages.persistence.db import get_pool
from packages.tools._shared import db_error_message
from packages.tools.base import ToolContext, ToolResult

_OPEN_STATUSES = ["pending", "confirmed", "in_transit"]


class AnalyzeSupplyRiskTool:
    name = "analyze_supply_risk"
    description = (
        "Compute a composite supply risk score combining gap risk, lead time variability, "
        "and supplier concentration"
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
            "risk_score": {"type": "number"},
            "risk_level": {"type": "string"},
            "gap_risk": {"type": "number"},
            "lead_time_risk": {"type": "number"},
            "concentration_risk": {"type": "number"},
            "top_risk_factors": {
                "type": "array",
                "items": {"type": "string"},
            },
            "missing_data": {"type": "array", "items": {"type": "string"}},
        },
    }

    def __init__(self, db_session: Any | None = None) -> None:
        pass

    async def handle(self, input: dict[str, Any], ctx: ToolContext) -> ToolResult:
        sku_id: str = input["sku_id"]
        horizon_days: int = int(input.get("horizon_days", 30))

        try:
            gap_risk, lead_time_risk, concentration_risk = await _compute_risk_components(
                sku_id, horizon_days
            )
        except Exception as exc:
            return ToolResult(
                output={"error": db_error_message(exc)},
                audit_payload={
                    "sku_id": sku_id,
                    "risk_score": None,
                    "risk_level": None,
                },
            )

        risk_score = (
            0.5 * gap_risk
            + 0.3 * lead_time_risk
            + 0.2 * concentration_risk
        )

        risk_level = _classify_risk_level(risk_score)

        top_risk_factors: list[str] = []
        if gap_risk > 0.5:
            top_risk_factors.append(
                f"High supply gap risk (gap_risk={gap_risk:.2f}): "
                "available supply is significantly below forecast demand"
            )
        if lead_time_risk > 0.5:
            top_risk_factors.append(
                f"High lead time variability risk (lead_time_risk={lead_time_risk:.2f}): "
                "supplier delivery times are unpredictable"
            )
        if concentration_risk > 0.5:
            top_risk_factors.append(
                f"High supplier concentration risk (concentration_risk={concentration_risk:.2f}): "
                "supply is concentrated among few suppliers"
            )

        return ToolResult(
            output={
                "sku_id": sku_id,
                "horizon_days": horizon_days,
                "risk_score": risk_score,
                "risk_level": risk_level,
                "gap_risk": gap_risk,
                "lead_time_risk": lead_time_risk,
                "concentration_risk": concentration_risk,
                "top_risk_factors": top_risk_factors,
                "missing_data": [],
            },
            audit_payload={
                "sku_id": sku_id,
                "risk_score": risk_score,
                "risk_level": risk_level,
            },
        )


def _classify_risk_level(score: float) -> str:
    if score < 0.2:
        return "low"
    if score < 0.4:
        return "medium"
    if score < 0.7:
        return "high"
    return "critical"


async def _compute_risk_components(
    sku_id: str, horizon_days: int
) -> tuple[float, float, float]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        # --- gap risk ---
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
              AND is_missing IS NOT TRUE
              AND date >= CURRENT_DATE - (90 * INTERVAL '1 day')
            """,
            sku_id,
        )
        avg_daily_demand = float(demand_row["avg_daily"])

        forecast_demand = avg_daily_demand * horizon_days
        total_available = on_hand_qty + incoming_qty

        gap_pct: float | None = None
        if forecast_demand > 0:
            gap_units = forecast_demand - total_available
            gap_pct = gap_units / forecast_demand * 100

        gap_risk: float
        if gap_pct is None:
            gap_risk = 0.0
        else:
            gap_risk = min(1.0, max(0.0, gap_pct / 100.0))

        # --- lead time risk (CV of lead times) ---
        lt_rows = await conn.fetch(
            """
            SELECT order_date, expected_arrival
            FROM supply_orders
            WHERE sku_id = $1
              AND expected_arrival IS NOT NULL
            """,
            sku_id,
        )

        import datetime as _dt

        lead_times: list[float] = []
        for row in lt_rows:
            od = row["order_date"]
            ea = row["expected_arrival"]
            if isinstance(od, _dt.datetime):
                od = od.date()
            if isinstance(ea, _dt.datetime):
                ea = ea.date()
            if od is not None and ea is not None:
                lead_times.append(float((ea - od).days))

        lead_time_risk: float
        if len(lead_times) >= 2:
            lt_mean = statistics.mean(lead_times)
            lt_std = statistics.stdev(lead_times)
            if lt_mean > 0:
                cv = lt_std / lt_mean
                lead_time_risk = min(1.0, cv)
            else:
                lead_time_risk = 0.5
        else:
            lead_time_risk = 0.5

        # --- supplier concentration (HHI) ---
        supplier_rows = await conn.fetch(
            """
            SELECT supplier_id, SUM(quantity) AS total_qty
            FROM supply_orders
            WHERE sku_id = $1
            GROUP BY supplier_id
            """,
            sku_id,
        )

        concentration_risk: float
        if supplier_rows:
            total_qty = sum(float(r["total_qty"]) for r in supplier_rows)
            if total_qty > 0:
                hhi = sum(
                    (float(r["total_qty"]) / total_qty) ** 2 for r in supplier_rows
                )
                concentration_risk = float(hhi)
            else:
                concentration_risk = 1.0
        else:
            concentration_risk = 1.0

    return gap_risk, lead_time_risk, concentration_risk


