from __future__ import annotations

import statistics
from typing import Any, Literal

from packages.persistence.db import get_pool
from packages.tools._shared import db_error_message
from packages.tools.base import ToolContext, ToolResult

_DOW_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
_MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


class DemandSeasonalityTool:
    name = "analyze_seasonality"
    description = "Detect weekly and monthly demand seasonality patterns for a SKU"
    safety_level: Literal["read_only", "write", "hitl"] = "read_only"
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "sku_id": {"type": "string"},
            "lookback_days": {"type": "integer", "minimum": 28, "default": 365},
        },
        "required": ["sku_id"],
    }
    output_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "sku_id": {"type": "string"},
            "lookback_days": {"type": "integer"},
            "record_count": {"type": "integer"},
            "has_weekly_pattern": {"type": "boolean"},
            "has_monthly_pattern": {"type": "boolean"},
            "peak_periods": {"type": "array", "items": {"type": "string"}},
            "trough_periods": {"type": "array", "items": {"type": "string"}},
            "seasonality_index": {"type": "number"},
            "missing_data": {"type": "array", "items": {"type": "string"}},
        },
    }

    def __init__(self, db_session: Any | None = None) -> None:
        pass

    async def handle(self, input: dict[str, Any], ctx: ToolContext) -> ToolResult:
        sku_id: str = input.get("sku_id", "")
        lookback_days: int = int(input.get("lookback_days", 365))

        try:
            rows = await _fetch_demand_rows(sku_id, lookback_days)
        except Exception as exc:
            return ToolResult(
                output={"error": db_error_message(exc)},
                audit_payload={"sku_id": sku_id, "lookback_days": lookback_days, "record_count": 0},
            )

        record_count = len(rows)

        if record_count < 14:
            return ToolResult(
                output={
                    "sku_id": sku_id,
                    "lookback_days": lookback_days,
                    "record_count": record_count,
                    "has_weekly_pattern": False,
                    "has_monthly_pattern": False,
                    "peak_periods": [],
                    "trough_periods": [],
                    "seasonality_index": 0.0,
                    "missing_data": (
                        [f"no demand_history rows for {sku_id} in last {lookback_days} days"]
                        if record_count == 0 else []
                    ),
                },
                audit_payload={
                    "sku_id": sku_id,
                    "lookback_days": lookback_days,
                    "record_count": record_count,
                },
            )

        # Group quantities by day-of-week (0=Mon…6=Sun) and by month (1–12)
        dow_buckets: dict[int, list[float]] = {i: [] for i in range(7)}
        month_buckets: dict[int, list[float]] = {m: [] for m in range(1, 13)}

        for row in rows:
            qty = float(row["quantity"])
            d = row["date"]
            dow_buckets[d.weekday()].append(qty)
            month_buckets[d.month].append(qty)

        # Weekly CV
        dow_averages = {
            dow: statistics.mean(vals) for dow, vals in dow_buckets.items() if vals
        }
        cv_weekly = 0.0
        if len(dow_averages) >= 2:
            avgs = list(dow_averages.values())
            mean_avgs = statistics.mean(avgs)
            if mean_avgs > 0:
                std_avgs = statistics.stdev(avgs) if len(avgs) >= 2 else 0.0
                cv_weekly = std_avgs / mean_avgs

        # Monthly CV
        month_averages = {
            m: statistics.mean(vals) for m, vals in month_buckets.items() if vals
        }
        cv_monthly = 0.0
        if len(month_averages) >= 2:
            avgs = list(month_averages.values())
            mean_avgs = statistics.mean(avgs)
            if mean_avgs > 0:
                std_avgs = statistics.stdev(avgs) if len(avgs) >= 2 else 0.0
                cv_monthly = std_avgs / mean_avgs

        has_weekly_pattern = cv_weekly > 0.15
        has_monthly_pattern = cv_monthly > 0.10

        # Peak and trough periods (combined, deduped, max 5)
        peak_periods: list[str] = []
        trough_periods: list[str] = []

        if dow_averages:
            overall_dow_mean = statistics.mean(dow_averages.values())
            for dow, avg in sorted(dow_averages.items()):
                if avg > overall_dow_mean:
                    peak_periods.append(_DOW_NAMES[dow])
                elif avg < overall_dow_mean:
                    trough_periods.append(_DOW_NAMES[dow])

        if month_averages:
            overall_month_mean = statistics.mean(month_averages.values())
            for m, avg in sorted(month_averages.items()):
                name = _MONTH_NAMES[m - 1]
                if avg > overall_month_mean and name not in peak_periods:
                    peak_periods.append(name)
                elif avg < overall_month_mean and name not in trough_periods:
                    trough_periods.append(name)

        seasonality_index = max(cv_weekly, cv_monthly) if record_count >= 28 else 0.0

        return ToolResult(
            output={
                "sku_id": sku_id,
                "lookback_days": lookback_days,
                "record_count": record_count,
                "has_weekly_pattern": has_weekly_pattern,
                "has_monthly_pattern": has_monthly_pattern,
                "peak_periods": peak_periods[:5],
                "trough_periods": trough_periods[:5],
                "seasonality_index": round(seasonality_index, 6),
                "missing_data": [],
            },
            audit_payload={
                "sku_id": sku_id,
                "lookback_days": lookback_days,
                "record_count": record_count,
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
              AND quantity IS NOT NULL
            ORDER BY date
            """,
            sku_id,
            lookback_days,
        )
        return [dict(r) for r in rows]


