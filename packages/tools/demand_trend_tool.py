from __future__ import annotations

from typing import Any, Literal

from packages.persistence.db import get_pool
from packages.tools._shared import db_error_message
from packages.tools.base import ToolContext, ToolResult


class DemandTrendTool:
    name = "analyze_demand_trend"
    description = (
        "Analyze demand trend direction, slope, and period-over-period growth for a SKU"
    )
    safety_level: Literal["read_only", "write", "hitl"] = "read_only"
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "sku_id": {"type": "string"},
            "lookback_days": {"type": "integer", "minimum": 7, "default": 90},
            "granularity": {
                "type": "string",
                "enum": ["weekly", "monthly"],
                "default": "weekly",
            },
        },
        "required": ["sku_id"],
    }
    output_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "sku_id": {"type": "string"},
            "granularity": {"type": "string"},
            "trend_direction": {"type": "string"},
            "trend_slope": {"type": "number"},
            "r_squared": {"type": "number"},
            "period_over_period_growth": {"type": ["number", "null"]},
            "peak_period": {"type": ["string", "null"]},
            "trough_period": {"type": ["string", "null"]},
            "periods": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "period": {"type": "string"},
                        "quantity": {"type": "number"},
                    },
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
        granularity: str = input.get("granularity", "weekly")

        try:
            rows = await _fetch_demand_rows(sku_id, lookback_days)
        except Exception as exc:
            return ToolResult(
                output={"error": db_error_message(exc)},
                audit_payload={
                    "sku_id": sku_id,
                    "lookback_days": lookback_days,
                    "granularity": granularity,
                },
            )

        periods = _aggregate_by_period(rows, granularity)

        if len(periods) < 2:
            return ToolResult(
                output={
                    "sku_id": sku_id,
                    "granularity": granularity,
                    "trend_direction": "flat",
                    "trend_slope": 0.0,
                    "r_squared": 0.0,
                    "period_over_period_growth": None,
                    "peak_period": periods[0]["period"] if periods else None,
                    "trough_period": periods[0]["period"] if periods else None,
                    "periods": periods,
                    "missing_data": (
                        [f"no demand_history rows for {sku_id} in last {lookback_days} days"]
                        if not periods else []
                    ),
                },
                audit_payload={
                    "sku_id": sku_id,
                    "lookback_days": lookback_days,
                    "granularity": granularity,
                },
            )

        labels = [p["period"] for p in periods]
        quantities = [p["quantity"] for p in periods]
        n = len(quantities)
        xs = list(range(n))

        slope, intercept = _linear_regression(xs, quantities)
        r_squared = _r_squared(xs, quantities, slope, intercept)

        if slope > 0.5:
            trend_direction = "up"
        elif slope < -0.5:
            trend_direction = "down"
        else:
            trend_direction = "flat"

        last_qty = quantities[-1]
        prev_qty = quantities[-2]
        if prev_qty != 0:
            period_over_period_growth: float | None = (last_qty - prev_qty) / prev_qty
        else:
            period_over_period_growth = None

        max_qty = max(quantities)
        min_qty = min(quantities)
        peak_period = labels[quantities.index(max_qty)]
        trough_period = labels[quantities.index(min_qty)]

        return ToolResult(
            output={
                "sku_id": sku_id,
                "granularity": granularity,
                "trend_direction": trend_direction,
                "trend_slope": slope,
                "r_squared": r_squared,
                "period_over_period_growth": period_over_period_growth,
                "peak_period": peak_period,
                "trough_period": trough_period,
                "periods": periods,
                "missing_data": [],
            },
            audit_payload={
                "sku_id": sku_id,
                "lookback_days": lookback_days,
                "granularity": granularity,
            },
        )


async def _fetch_demand_rows(sku_id: str, lookback_days: int) -> list[dict[str, Any]]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT date, quantity
            FROM demand_history
            WHERE sku_id = $1
              AND date >= CURRENT_DATE - ($2 * INTERVAL '1 day')
              AND is_missing IS NOT TRUE
            ORDER BY date
            """,
            sku_id,
            lookback_days,
        )
        return [dict(r) for r in rows]


def _period_label(row_date: Any, granularity: str) -> str:
    from datetime import date as date_type
    d: date_type
    if isinstance(row_date, date_type):
        d = row_date
    else:
        from datetime import datetime
        d = datetime.fromisoformat(str(row_date)).date()

    if granularity == "monthly":
        return d.strftime("%Y-%m")
    # weekly: ISO week format YYYY-Www
    iso_year, iso_week, _ = d.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def _aggregate_by_period(rows: list[dict[str, Any]], granularity: str) -> list[dict[str, Any]]:
    aggregated: dict[str, float] = {}
    for row in rows:
        if row["quantity"] is None:
            continue
        label = _period_label(row["date"], granularity)
        aggregated[label] = aggregated.get(label, 0.0) + float(row["quantity"])
    return [{"period": k, "quantity": v} for k, v in sorted(aggregated.items())]


def _linear_regression(xs: list[int], ys: list[float]) -> tuple[float, float]:
    n = len(xs)
    if n < 2:
        return 0.0, ys[0] if ys else 0.0
    sum_x = sum(xs)
    sum_y = sum(ys)
    sum_xx = sum(x * x for x in xs)
    sum_xy = sum(x * y for x, y in zip(xs, ys))
    denom = n * sum_xx - sum_x * sum_x
    if denom == 0:
        return 0.0, sum_y / n
    slope = (n * sum_xy - sum_x * sum_y) / denom
    intercept = (sum_y - slope * sum_x) / n
    return slope, intercept


def _r_squared(xs: list[int], ys: list[float], slope: float, intercept: float) -> float:
    n = len(ys)
    if n < 2:
        return 0.0
    mean_y = sum(ys) / n
    ss_tot = sum((y - mean_y) ** 2 for y in ys)
    if ss_tot == 0:
        return 1.0
    ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(xs, ys))
    return max(0.0, 1.0 - ss_res / ss_tot)


