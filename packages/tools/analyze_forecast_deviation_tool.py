"""analyze_forecast_deviation — T-577

Decomposes the gap between demand forecast and actual demand at SKU × ISO-week
grain over a rolling window of complete ISO weeks ending before the current week.

## Forecast dedupe

forecast_history can contain multiple forecast runs for the same (sku_id,
target_date).  Only the latest forecast_date row per (sku_id, target_date) is
used (DISTINCT ON pattern).  SUM(forecast_qty) is then computed over those
deduped rows whose target_date falls inside the analysis window.

## Actual demand basis

Actual demand is drawn from demand_history.quantity grouped by sku_id and ISO
week.  Rows where is_missing IS TRUE are excluded from the sum — they represent
known data gaps, not zero consumption.  SKUs that have is_missing actuals within
the window are reported in missing_data (partial-window note).

## Bias direction thresholds (documented)

Per-SKU bias is determined from the sign of total_gap_qty over the window:

  bias direction = SUM(forecast_qty - actual_qty) across all weeks for the SKU

  - total_bias_qty > +BIAS_THRESHOLD_PCT% of total_actual_qty
        → over_forecast  (systematic upward bias; forecast > actual)
  - total_bias_qty < -BIAS_THRESHOLD_PCT% of total_actual_qty
        → under_forecast (systematic downward bias; forecast < actual)
  - |total_bias_qty| ≤ BIAS_THRESHOLD_PCT% of total_actual_qty
        → mixed          (no clear directional bias; noise-level)

  BIAS_THRESHOLD_PCT = 10.0 %  (±10 % noise band)

  When total_actual_qty == 0 (all actuals missing or truly zero):
  - forecast_qty > 0 → over_forecast
  - forecast_qty == 0 → mixed (neither over nor under)

## Output contract (hybrid)

- ``skus``          : per-SKU objects, each containing a weekly_breakdown list
                      and aggregate metrics; capped to ROW_CAP with truncated flag.
                      Count reflects the FULL pre-cap length.
- ``weeks_analysed``: number of ISO weeks actually analysed.
- ``window``        : {start_iso_week, end_iso_week, weeks_requested}.
- ``missing_data``  : list of note strings:
                        - SKUs with no forecast rows in the window
                        - SKUs with no actuals in the window
                        - SKUs with is_missing actual rows (partial data)

## Ranking

Ranked by total absolute gap descending (sum of |gap_qty| across all weeks),
with sku_id ascending as a deterministic tie-break.

## Constraints

No LLM calls. All SQL parameterized. Tables used:
  forecast_history, demand_history, sku_master
All are in ALLOWED_READ_TABLES.

Output follows the hybrid tool output contract
(ADR docs/adr/2026-06-10-tool-output-contract-hybrid.md).
"""
from __future__ import annotations

import datetime
import logging
from typing import Any, Literal

from packages.persistence.db import get_pool
from packages.tools._shared import db_error_message
from packages.tools.base import ToolContext, ToolResult

_log = logging.getLogger(__name__)

# Maximum number of SKU rows returned before truncated=True.
# Summary counts reflect the FULL pre-cap set (P88 lesson).
_ROW_CAP = 100

# Directional bias threshold as a percentage of total actual quantity.
# Documented in module docstring.
_BIAS_THRESHOLD_PCT = 10.0

# Default number of complete ISO weeks to analyse.
_DEFAULT_WEEKS = 4


class AnalyzeForecastDeviationTool:
    """Compare forecast_history against demand_history at SKU × ISO-week grain.

    Returns per-SKU weekly breakdown (forecast, actual, gap), per-SKU bias
    direction (over_forecast / under_forecast / mixed), aggregate absolute
    deviation pct, and missing_data notes.

    No LLM calls — deterministic SQL + Python aggregation only.
    """

    name = "analyze_forecast_deviation"
    description = (
        "Decompose the gap between demand forecast and actual demand at SKU × ISO-week "
        "grain over the last N complete ISO weeks (default 4). "
        "Per SKU: weekly forecast vs actual breakdown (gap_qty, gap_pct), bias direction "
        "(over_forecast / under_forecast / mixed), and aggregate absolute deviation pct. "
        "Ranked by total absolute gap descending. "
        "Call this for SPEC Q5 — 'Why is there a gap between the demand forecast and actual "
        "demand?'. "
        "evaluate_forecast_accuracy is the model-quality axis (MAPE/bias of the forecasting "
        "model); this tool is the operational gap axis (what the forecast said vs what "
        "actually happened). "
        "Pair with detect_demand_shift when the user asks which customer or region drives "
        "the gap."
    )
    safety_level: Literal["read_only", "write", "hitl"] = "read_only"
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "weeks": {
                "type": "integer",
                "minimum": 1,
                "default": _DEFAULT_WEEKS,
                "description": (
                    "Number of complete ISO weeks to analyse, ending before the current "
                    "week (i.e. fully elapsed weeks). Default 4."
                ),
            },
            "sku_id": {
                "type": "string",
                "description": (
                    "Optional: restrict analysis to a single SKU. "
                    "Omit to analyse all SKUs with forecast or actual data in the window."
                ),
            },
        },
        "required": [],
    }
    output_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "weeks_analysed": {"type": "integer"},
            "window": {
                "type": "object",
                "properties": {
                    "start_iso_week": {"type": "string"},
                    "end_iso_week": {"type": "string"},
                    "weeks_requested": {"type": "integer"},
                },
                "required": ["start_iso_week", "end_iso_week", "weeks_requested"],
            },
            "skus": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "sku_id": {"type": "string"},
                        "bias_direction": {
                            "type": "string",
                            "enum": ["over_forecast", "under_forecast", "mixed"],
                        },
                        "total_forecast_qty": {"type": "number"},
                        "total_actual_qty": {"type": "number"},
                        "total_gap_qty": {"type": "number"},
                        "total_abs_gap_qty": {"type": "number"},
                        "aggregate_abs_deviation_pct": {
                            "type": ["number", "null"],
                            "description": (
                                "SUM(|gap_qty|) / SUM(actual_qty) × 100. "
                                "null when total actual = 0."
                            ),
                        },
                        "weekly_breakdown": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "iso_week": {"type": "string"},
                                    "week_start": {"type": "string"},
                                    "forecast_qty": {"type": "number"},
                                    "actual_qty": {"type": "number"},
                                    "gap_qty": {"type": "number"},
                                    "gap_pct": {"type": ["number", "null"]},
                                },
                                "required": [
                                    "iso_week",
                                    "week_start",
                                    "forecast_qty",
                                    "actual_qty",
                                    "gap_qty",
                                    "gap_pct",
                                ],
                            },
                        },
                    },
                    "required": [
                        "sku_id",
                        "bias_direction",
                        "total_forecast_qty",
                        "total_actual_qty",
                        "total_gap_qty",
                        "total_abs_gap_qty",
                        "aggregate_abs_deviation_pct",
                        "weekly_breakdown",
                    ],
                },
            },
            "count": {"type": "integer"},
            "truncated": {"type": "boolean"},
            "missing_data": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Notes on data gaps: SKUs with no forecast rows in the window, "
                    "no actuals in the window, or is_missing actual rows (partial data)."
                ),
            },
        },
        "required": [
            "weeks_analysed",
            "window",
            "skus",
            "count",
            "truncated",
            "missing_data",
        ],
    }

    def __init__(self, db_session: Any | None = None) -> None:
        pass

    async def handle(self, input: dict[str, Any], ctx: ToolContext) -> ToolResult:  # noqa: A002
        _w = input.get("weeks")
        weeks: int = int(_w if _w is not None else _DEFAULT_WEEKS)
        if weeks < 1:
            weeks = _DEFAULT_WEEKS

        sku_filter: str | None = input.get("sku_id") or None

        # Compute ISO-week window: last N complete weeks before the current week.
        # ISO week starts on Monday.  "Current week" = the Monday of today's week.
        today = datetime.date.today()
        # Monday of the current (incomplete) week
        current_week_start = today - datetime.timedelta(days=today.weekday())
        # End of our window = last day of the previous week (Sunday)
        window_end = current_week_start - datetime.timedelta(days=1)
        # Start of our window = Monday N weeks ago
        window_start = current_week_start - datetime.timedelta(weeks=weeks)

        # ISO-week labels for the window boundary documentation
        start_iso = _iso_week_label(window_start)
        # end_iso: label of the week containing window_end
        end_week_start = current_week_start - datetime.timedelta(weeks=1)
        end_iso = _iso_week_label(end_week_start)

        window_info: dict[str, Any] = {
            "start_iso_week": start_iso,
            "end_iso_week": end_iso,
            "weeks_requested": weeks,
        }

        audit_base: dict[str, Any] = {
            "weeks": weeks,
            "sku_id": sku_filter,
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat(),
        }

        try:
            forecast_rows = await _fetch_forecast_by_week(
                window_start, window_end, sku_filter
            )
            actual_rows = await _fetch_actuals_by_week(
                window_start, window_end, sku_filter
            )
            missing_actual_rows = await _fetch_is_missing_actuals(
                window_start, window_end, sku_filter
            )
        except Exception as exc:
            return ToolResult(
                output={"error": db_error_message(exc)},
                audit_payload=audit_base,
            )

        # Collect the set of ISO weeks in the window
        week_starts = _enumerate_week_starts(window_start, weeks)

        # Build {sku_id: {iso_week: forecast_qty}}
        forecast_map: dict[str, dict[str, float]] = {}
        for row in forecast_rows:
            sid = str(row["sku_id"])
            wlabel = str(row["iso_week"])
            qty = float(row["forecast_qty"])
            if sid not in forecast_map:
                forecast_map[sid] = {}
            forecast_map[sid][wlabel] = qty

        # Build {sku_id: {iso_week: actual_qty}}
        actual_map: dict[str, dict[str, float]] = {}
        for row in actual_rows:
            sid = str(row["sku_id"])
            wlabel = str(row["iso_week"])
            qty = float(row["actual_qty"])
            if sid not in actual_map:
                actual_map[sid] = {}
            actual_map[sid][wlabel] = qty

        # Build {sku_id: set of iso_weeks with is_missing actuals}
        missing_actual_map: dict[str, set[str]] = {}
        for row in missing_actual_rows:
            sid = str(row["sku_id"])
            wlabel = str(row["iso_week"])
            if sid not in missing_actual_map:
                missing_actual_map[sid] = set()
            missing_actual_map[sid].add(wlabel)

        # Union of all SKUs observed in either forecast or actual
        all_skus: set[str] = set(forecast_map.keys()) | set(actual_map.keys())
        if sku_filter:
            all_skus = {s for s in all_skus if s == sku_filter}

        missing_data: list[str] = []
        sku_results: list[dict[str, Any]] = []

        for sku_id in sorted(all_skus):
            fmap = forecast_map.get(sku_id, {})
            amap = actual_map.get(sku_id, {})
            mmap = missing_actual_map.get(sku_id, set())

            has_forecast = bool(fmap)
            has_actuals = bool(amap)

            if not has_forecast:
                missing_data.append(
                    f"{sku_id}: no forecast rows in window "
                    f"({start_iso}–{end_iso})"
                )
            if not has_actuals:
                missing_data.append(
                    f"{sku_id}: no actual demand rows in window "
                    f"({start_iso}–{end_iso})"
                )
            if mmap:
                missing_data.append(
                    f"{sku_id}: is_missing actuals in "
                    f"{len(mmap)} week(s) — partial window data"
                )

            # Build weekly breakdown
            weekly: list[dict[str, Any]] = []
            for ws in week_starts:
                wlabel = _iso_week_label(ws)
                forecast_qty = fmap.get(wlabel, 0.0)
                actual_qty = amap.get(wlabel, 0.0)
                gap_qty = forecast_qty - actual_qty
                gap_pct = _gap_pct(forecast_qty, actual_qty)
                weekly.append({
                    "iso_week": wlabel,
                    "week_start": ws.isoformat(),
                    "forecast_qty": round(forecast_qty, 4),
                    "actual_qty": round(actual_qty, 4),
                    "gap_qty": round(gap_qty, 4),
                    "gap_pct": gap_pct,
                })

            total_forecast = sum(w["forecast_qty"] for w in weekly)
            total_actual = sum(w["actual_qty"] for w in weekly)
            total_gap = total_forecast - total_actual
            total_abs_gap = sum(abs(w["gap_qty"]) for w in weekly)
            agg_dev_pct = _aggregate_abs_deviation_pct(total_abs_gap, total_actual)
            bias = _classify_bias(total_forecast, total_actual)

            sku_results.append({
                "sku_id": sku_id,
                "bias_direction": bias,
                "total_forecast_qty": round(total_forecast, 4),
                "total_actual_qty": round(total_actual, 4),
                "total_gap_qty": round(total_gap, 4),
                "total_abs_gap_qty": round(total_abs_gap, 4),
                "aggregate_abs_deviation_pct": agg_dev_pct,
                "weekly_breakdown": weekly,
            })

        # Rank: total absolute gap descending; sku_id ascending as tie-break (deterministic)
        sku_results.sort(
            key=lambda r: (-r["total_abs_gap_qty"], r["sku_id"])
        )

        count = len(sku_results)
        truncated = count > _ROW_CAP
        sku_results = sku_results[:_ROW_CAP]

        return ToolResult(
            output={
                "weeks_analysed": weeks,
                "window": window_info,
                "skus": sku_results,
                "count": count,
                "truncated": truncated,
                "missing_data": missing_data,
            },
            audit_payload={
                **audit_base,
                "sku_count": count,
                "truncated": truncated,
                "missing_data_count": len(missing_data),
            },
        )


# ---------------------------------------------------------------------------
# Pure-Python helpers (exported for unit tests)
# ---------------------------------------------------------------------------


def _iso_week_label(week_start: datetime.date) -> str:
    """Return 'YYYY-Www' ISO week label for the week beginning on week_start (Monday)."""
    iso = week_start.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def _enumerate_week_starts(
    window_start: datetime.date,
    weeks: int,
) -> list[datetime.date]:
    """Return list of N Monday dates starting from window_start."""
    return [window_start + datetime.timedelta(weeks=i) for i in range(weeks)]


def _gap_pct(forecast_qty: float, actual_qty: float) -> float | None:
    """Return gap_pct = (forecast - actual) / actual × 100, or None when actual == 0."""
    if actual_qty == 0:
        return None
    return round((forecast_qty - actual_qty) / actual_qty * 100.0, 4)


def _aggregate_abs_deviation_pct(
    total_abs_gap: float,
    total_actual: float,
) -> float | None:
    """Return SUM(|gap|) / SUM(actual) × 100, or None when total_actual == 0."""
    if total_actual == 0:
        return None
    return round(total_abs_gap / total_actual * 100.0, 4)


def _classify_bias(
    total_forecast: float,
    total_actual: float,
) -> str:
    """Return bias direction from total forecast vs total actual over the window.

    Rules (BIAS_THRESHOLD_PCT = 10 %):
      - total_actual == 0 AND total_forecast > 0 → over_forecast
      - total_actual == 0 AND total_forecast == 0 → mixed
      - bias_pct = (total_forecast - total_actual) / total_actual × 100
        - bias_pct >  +BIAS_THRESHOLD_PCT → over_forecast
        - bias_pct < -BIAS_THRESHOLD_PCT  → under_forecast
        - |bias_pct| ≤ BIAS_THRESHOLD_PCT → mixed
    """
    if total_actual == 0:
        return "over_forecast" if total_forecast > 0 else "mixed"
    bias_pct = (total_forecast - total_actual) / total_actual * 100.0
    if bias_pct > _BIAS_THRESHOLD_PCT:
        return "over_forecast"
    if bias_pct < -_BIAS_THRESHOLD_PCT:
        return "under_forecast"
    return "mixed"


# ---------------------------------------------------------------------------
# SQL query helpers
# ---------------------------------------------------------------------------


async def _fetch_forecast_by_week(
    window_start: datetime.date,
    window_end: datetime.date,
    sku_filter: str | None,
) -> list[dict[str, Any]]:
    """Return aggregated forecast_qty per (sku_id, ISO week) in the window.

    Dedupes to the latest forecast_date per (sku_id, target_date) before summing.
    The target_date is bucketed to its ISO week start (Monday via DATE_TRUNC).
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        if sku_filter:
            rows = await conn.fetch(
                """
                WITH latest_forecast AS (
                    SELECT DISTINCT ON (sku_id, target_date)
                        sku_id,
                        target_date,
                        forecast_qty
                    FROM forecast_history
                    WHERE target_date >= $1
                      AND target_date <= $2
                      AND sku_id = $3
                    ORDER BY sku_id, target_date, forecast_date DESC
                )
                SELECT
                    sku_id,
                    TO_CHAR(
                        DATE_TRUNC('week', target_date)::date,
                        'IYYY-"W"IW'
                    )                           AS iso_week,
                    SUM(forecast_qty)            AS forecast_qty
                FROM latest_forecast
                GROUP BY sku_id, DATE_TRUNC('week', target_date)
                ORDER BY sku_id, DATE_TRUNC('week', target_date)
                """,
                window_start,
                window_end,
                sku_filter,
            )
        else:
            rows = await conn.fetch(
                """
                WITH latest_forecast AS (
                    SELECT DISTINCT ON (sku_id, target_date)
                        sku_id,
                        target_date,
                        forecast_qty
                    FROM forecast_history
                    WHERE target_date >= $1
                      AND target_date <= $2
                    ORDER BY sku_id, target_date, forecast_date DESC
                )
                SELECT
                    sku_id,
                    TO_CHAR(
                        DATE_TRUNC('week', target_date)::date,
                        'IYYY-"W"IW'
                    )                           AS iso_week,
                    SUM(forecast_qty)            AS forecast_qty
                FROM latest_forecast
                GROUP BY sku_id, DATE_TRUNC('week', target_date)
                ORDER BY sku_id, DATE_TRUNC('week', target_date)
                """,
                window_start,
                window_end,
            )
        return [dict(r) for r in rows]


async def _fetch_actuals_by_week(
    window_start: datetime.date,
    window_end: datetime.date,
    sku_filter: str | None,
) -> list[dict[str, Any]]:
    """Return summed actual demand_history.quantity per (sku_id, ISO week) in window.

    Excludes rows where is_missing IS TRUE (known data gaps, not zero consumption).
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        if sku_filter:
            rows = await conn.fetch(
                """
                SELECT
                    sku_id,
                    TO_CHAR(
                        DATE_TRUNC('week', date)::date,
                        'IYYY-"W"IW'
                    )               AS iso_week,
                    SUM(quantity)   AS actual_qty
                FROM demand_history
                WHERE date >= $1
                  AND date <= $2
                  AND is_missing IS NOT TRUE
                  AND sku_id = $3
                GROUP BY sku_id, DATE_TRUNC('week', date)
                ORDER BY sku_id, DATE_TRUNC('week', date)
                """,
                window_start,
                window_end,
                sku_filter,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT
                    sku_id,
                    TO_CHAR(
                        DATE_TRUNC('week', date)::date,
                        'IYYY-"W"IW'
                    )               AS iso_week,
                    SUM(quantity)   AS actual_qty
                FROM demand_history
                WHERE date >= $1
                  AND date <= $2
                  AND is_missing IS NOT TRUE
                GROUP BY sku_id, DATE_TRUNC('week', date)
                ORDER BY sku_id, DATE_TRUNC('week', date)
                """,
                window_start,
                window_end,
            )
        return [dict(r) for r in rows]


async def _fetch_is_missing_actuals(
    window_start: datetime.date,
    window_end: datetime.date,
    sku_filter: str | None,
) -> list[dict[str, Any]]:
    """Return distinct (sku_id, ISO week) pairs that have is_missing actuals.

    Used to populate missing_data partial-data notes.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        if sku_filter:
            rows = await conn.fetch(
                """
                SELECT DISTINCT
                    sku_id,
                    TO_CHAR(
                        DATE_TRUNC('week', date)::date,
                        'IYYY-"W"IW'
                    ) AS iso_week
                FROM demand_history
                WHERE date >= $1
                  AND date <= $2
                  AND is_missing IS TRUE
                  AND sku_id = $3
                ORDER BY sku_id, iso_week
                """,
                window_start,
                window_end,
                sku_filter,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT DISTINCT
                    sku_id,
                    TO_CHAR(
                        DATE_TRUNC('week', date)::date,
                        'IYYY-"W"IW'
                    ) AS iso_week
                FROM demand_history
                WHERE date >= $1
                  AND date <= $2
                  AND is_missing IS TRUE
                ORDER BY sku_id, iso_week
                """,
                window_start,
                window_end,
            )
        return [dict(r) for r in rows]
