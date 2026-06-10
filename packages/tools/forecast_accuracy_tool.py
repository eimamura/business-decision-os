from __future__ import annotations

from typing import Any, Literal

from packages.persistence.db import get_pool
from packages.tools._shared import db_error_message
from packages.tools.base import ToolContext, ToolResult


class ForecastAccuracyTool:
    name = "evaluate_forecast_accuracy"
    description = (
        "Compute MAPE, WAPE, and bias for a SKU by comparing forecast_history "
        "against demand_history"
    )
    safety_level: Literal["read_only", "write", "hitl"] = "read_only"
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "sku_id": {"type": "string"},
            "lookback_days": {"type": "integer", "minimum": 1, "default": 90},
        },
        "required": ["sku_id"],
    }
    output_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "sku_id": {"type": "string"},
            "sample_size": {"type": "integer"},
            "mape": {"type": ["number", "null"]},
            "wape": {"type": "number"},
            "bias": {"type": "number"},
            "coverage": {"type": "number"},
            "worst_period": {
                "type": ["object", "null"],
                "properties": {
                    "date": {"type": "string"},
                    "forecast_qty": {"type": "number"},
                    "actual_qty": {"type": "number"},
                    "error_pct": {"type": "number"},
                },
            },
            "missing_data": {"type": "array", "items": {"type": "string"}},
        },
    }

    def __init__(self, db_session: Any | None = None) -> None:
        pass

    async def handle(self, input: dict[str, Any], ctx: ToolContext) -> ToolResult:
        sku_id: str = input.get("sku_id", "")
        lookback_days: int = int(input.get("lookback_days", 90))

        try:
            joined_rows = await _fetch_joined_rows(sku_id, lookback_days)
            demand_count = await _fetch_demand_count(sku_id, lookback_days)
        except Exception as exc:
            return ToolResult(
                output={"error": db_error_message(exc)},
                audit_payload={"sku_id": sku_id, "lookback_days": lookback_days, "sample_size": 0},
            )

        sample_size = len(joined_rows)

        if sample_size == 0:
            missing_data_no_forecast: list[str] = []
            if demand_count == 0:
                missing_data_no_forecast.append(
                    f"no demand_history rows for {sku_id} in last {lookback_days} days"
                )
            else:
                missing_data_no_forecast.append(
                    f"no forecast_history rows for {sku_id} in last {lookback_days} days"
                )
            return ToolResult(
                output={
                    "sku_id": sku_id,
                    "sample_size": 0,
                    "mape": None,
                    "wape": 0.0,
                    "bias": 0.0,
                    "coverage": 0.0,
                    "worst_period": None,
                    "missing_data": missing_data_no_forecast,
                },
                audit_payload={"sku_id": sku_id, "lookback_days": lookback_days, "sample_size": 0},
            )

        errors = [
            float(r["forecast_qty"]) - float(r["actual_qty"]) for r in joined_rows
        ]
        bias = sum(errors) / len(errors)

        positive_actual_rows = [
            (r, e)
            for r, e in zip(joined_rows, errors)
            if float(r["actual_qty"]) > 0
        ]

        mape: float | None = None
        if positive_actual_rows:
            mape = sum(abs(e) / float(r["actual_qty"]) for r, e in positive_actual_rows) / len(
                positive_actual_rows
            )

        sum_abs_errors = sum(abs(e) for r, e in positive_actual_rows)
        sum_actuals = sum(float(r["actual_qty"]) for r, e in positive_actual_rows)
        wape = sum_abs_errors / sum_actuals if sum_actuals > 0 else 0.0

        coverage = sample_size / demand_count if demand_count > 0 else 0.0

        worst_period: dict[str, Any] | None = None
        if positive_actual_rows:
            worst_row, worst_error = max(
                positive_actual_rows,
                key=lambda re: abs(re[1]) / float(re[0]["actual_qty"]),
            )
            error_pct = worst_error / float(worst_row["actual_qty"])
            target_date = worst_row["target_date"]
            worst_period = {
                "date": (
                    target_date.isoformat()
                    if hasattr(target_date, "isoformat")
                    else str(target_date)
                ),
                "forecast_qty": float(worst_row["forecast_qty"]),
                "actual_qty": float(worst_row["actual_qty"]),
                "error_pct": error_pct,
            }

        return ToolResult(
            output={
                "sku_id": sku_id,
                "sample_size": sample_size,
                "mape": mape,
                "wape": wape,
                "bias": bias,
                "coverage": coverage,
                "worst_period": worst_period,
                "missing_data": [],
            },
            audit_payload={
                "sku_id": sku_id,
                "lookback_days": lookback_days,
                "sample_size": sample_size,
            },
        )


async def _fetch_joined_rows(sku_id: str, lookback_days: int) -> list[dict[str, Any]]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT fh.target_date, fh.forecast_qty, dh.quantity AS actual_qty
            FROM forecast_history fh
            JOIN demand_history dh
              ON fh.sku_id = dh.sku_id AND fh.target_date = dh.date
            WHERE fh.sku_id = $1
              AND fh.target_date >= CURRENT_DATE - ($2 * INTERVAL '1 day')
            ORDER BY fh.target_date
            """,
            sku_id,
            lookback_days,
        )
        return [dict(r) for r in rows]


async def _fetch_demand_count(sku_id: str, lookback_days: int) -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        count = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM demand_history
            WHERE sku_id = $1
              AND date >= CURRENT_DATE - ($2 * INTERVAL '1 day')
            """,
            sku_id,
            lookback_days,
        )
        return int(count) if count is not None else 0


