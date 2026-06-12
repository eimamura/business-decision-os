"""analyze_production_plan_gap — T-557

Compares planned production against forward demand on a per-SKU + per-location
basis and classifies each combination as overproduction, underproduction, or
balanced.

## Demand basis selection

For each (sku_id, location_id) pair, the tool tries to find a suitable forward
demand estimate in the following order:

  1. **forecast_history** — uses the latest forecast record whose
     ``forecast_date`` is within the horizon window
     [CURRENT_DATE, CURRENT_DATE + horizon_weeks * 7 days).
     When a forecast row exists, the ``demand_basis`` is "forecast".

  2. **demand_history run-rate** — falls back to the 30-day avg_daily approach
     from the established inventory-tools pattern:

       avg_daily = AVG(quantity)
                   FROM demand_history
                   WHERE sku_id = $sku_id
                     AND date >= CURRENT_DATE - 30 days
                     AND is_missing IS NOT TRUE

     Expected demand over the horizon = avg_daily × (horizon_weeks × 7).
     ``demand_basis`` is "run_rate".

     SKUs present in production_plan but with zero demand history AND no
     forecast are surfaced in ``missing_data``.

## Classification thresholds (documented)

The relative gap is defined as:

    gap_pct = (planned_qty - expected_demand) / expected_demand × 100

  - gap_pct >  +25 % (or expected_demand == 0 and planned_qty > 0) → overproduction
  - gap_pct < -25 %                                                  → underproduction
  - |gap_pct| ≤ 25 %                                                 → balanced

A ±25 % window is used because weekly production schedules include batch-size
rounding and safety stock buffer; deviations within 25 % are operationally
acceptable.  Deviations beyond ±25 % represent a meaningful misalignment with
demand.

## Output contract (hybrid)

- ``items``          : per-SKU+location details, capped to ROW_CAP with
                       ``truncated`` flag.
- ``summary``        : overproduction_count, underproduction_count, balanced_count.
- ``horizon_weeks``  : planning horizon actually used.
- ``missing_data``   : list of note strings for SKUs with zero demand history
                       AND no forecast — these cannot be reliably classified.

## Constraints

No LLM calls. All SQL parameterized. Tables used:
  production_plan, forecast_history, demand_history
All are in ALLOWED_READ_TABLES.

Output follows the hybrid tool output contract
(ADR docs/adr/2026-06-10-tool-output-contract-hybrid.md).
"""
from __future__ import annotations

import logging
from typing import Any, Literal

from packages.persistence.db import get_pool
from packages.tools._shared import db_error_message
from packages.tools.base import ToolContext, ToolResult

_log = logging.getLogger(__name__)

# Maximum number of detail rows returned before truncated=True.
_ROW_CAP = 100

# Relative gap threshold for overproduction / underproduction classification (%).
# Documented in module docstring.
_GAP_THRESHOLD_PCT = 25.0

# Default planning horizon in weeks.
_DEFAULT_HORIZON_WEEKS = 4

# Demand history look-back window for run-rate (days).
_RUNRATE_LOOKBACK_DAYS = 30


class AnalyzeProductionPlanGapTool:
    """Compare production_plan against forward demand and classify over/underproduction.

    Uses forecast_history where a forecast covering the horizon exists; falls back
    to demand_history 30-day run-rate otherwise.  No LLM calls — deterministic SQL only.
    """

    name = "analyze_production_plan_gap"
    description = (
        "Compare planned production quantities against expected demand (forecast or "
        "recent run-rate) for each SKU+location over a forward horizon. "
        "Classifies each combination as overproduction (planned > expected + 25%), "
        "underproduction (planned < expected - 25%), or balanced. "
        "Call this for SPEC Q7 — 'which products require production plan adjustments?'. "
        "Returns gap_qty, gap_pct, demand_basis (forecast|run_rate), "
        "per-class counts, and missing_data for SKUs with no demand signal."
    )
    safety_level: Literal["read_only", "write", "hitl"] = "read_only"
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "horizon_weeks": {
                "type": "integer",
                "minimum": 1,
                "default": _DEFAULT_HORIZON_WEEKS,
                "description": (
                    "Number of forward weeks of production_plan to compare against demand. "
                    "Default 4 weeks."
                ),
            },
            "location_id": {
                "type": "string",
                "description": (
                    "Optional: restrict analysis to a specific location_id. "
                    "Omit to analyse all locations."
                ),
            },
        },
        "required": [],
    }
    output_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "horizon_weeks": {"type": "integer"},
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "sku_id": {"type": "string"},
                        "location_id": {"type": "string"},
                        "planned_qty": {"type": "number"},
                        "expected_demand": {"type": "number"},
                        "gap_qty": {"type": "number"},
                        "gap_pct": {"type": ["number", "null"]},
                        "classification": {
                            "type": "string",
                            "enum": ["overproduction", "underproduction", "balanced"],
                        },
                        "demand_basis": {
                            "type": "string",
                            "enum": ["forecast", "run_rate"],
                        },
                    },
                    "required": [
                        "sku_id",
                        "location_id",
                        "planned_qty",
                        "expected_demand",
                        "gap_qty",
                        "gap_pct",
                        "classification",
                        "demand_basis",
                    ],
                },
            },
            "summary": {
                "type": "object",
                "properties": {
                    "overproduction_count": {"type": "integer"},
                    "underproduction_count": {"type": "integer"},
                    "balanced_count": {"type": "integer"},
                },
                "required": ["overproduction_count", "underproduction_count", "balanced_count"],
            },
            "truncated": {"type": "boolean"},
            "missing_data": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "SKUs present in production_plan with zero demand history "
                    "AND no forecast — classification is unreliable for these."
                ),
            },
        },
        "required": ["horizon_weeks", "items", "summary", "truncated", "missing_data"],
    }

    def __init__(self, db_session: Any | None = None) -> None:
        pass

    async def handle(self, input: dict[str, Any], ctx: ToolContext) -> ToolResult:  # noqa: A002
        _hw = input.get("horizon_weeks")
        horizon_weeks: int = int(_hw if _hw is not None else _DEFAULT_HORIZON_WEEKS)
        if horizon_weeks < 1:
            horizon_weeks = _DEFAULT_HORIZON_WEEKS

        location_filter: str | None = input.get("location_id") or None

        try:
            rows = await _fetch_production_plan_rows(horizon_weeks, location_filter)
        except Exception as exc:
            return ToolResult(
                output={"error": db_error_message(exc)},
                audit_payload={
                    "horizon_weeks": horizon_weeks,
                    "location_id": location_filter,
                },
            )

        # Fetch forecast and run-rate demand for observed SKUs
        sku_ids = list({r["sku_id"] for r in rows})
        try:
            forecast_map = await _fetch_forecast_demand(sku_ids, horizon_weeks)
            runrate_map = await _fetch_runrate_demand(sku_ids)
        except Exception as exc:
            return ToolResult(
                output={"error": db_error_message(exc)},
                audit_payload={
                    "horizon_weeks": horizon_weeks,
                    "location_id": location_filter,
                },
            )

        horizon_days: float = horizon_weeks * 7.0

        items: list[dict[str, Any]] = []
        missing_data: list[str] = []
        seen_missing: set[str] = set()

        for row in rows:
            sku_id: str = row["sku_id"]
            location_id: str = row["location_id"]
            planned_qty: float = float(row["planned_qty"])

            # Demand basis: prefer forecast, fall back to run-rate
            if sku_id in forecast_map:
                expected_demand = float(forecast_map[sku_id])
                demand_basis: str = "forecast"
            else:
                avg_daily = runrate_map.get(sku_id, 0.0)
                expected_demand = avg_daily * horizon_days
                demand_basis = "run_rate"
                if avg_daily == 0.0 and sku_id not in seen_missing:
                    missing_data.append(
                        f"{sku_id}: no demand_history (30d) and no forecast — "
                        "classification unreliable"
                    )
                    seen_missing.add(sku_id)

            classification, gap_qty, gap_pct = _classify_gap(planned_qty, expected_demand)

            items.append(
                {
                    "sku_id": sku_id,
                    "location_id": location_id,
                    "planned_qty": planned_qty,
                    "expected_demand": expected_demand,
                    "gap_qty": gap_qty,
                    "gap_pct": gap_pct,
                    "classification": classification,
                    "demand_basis": demand_basis,
                }
            )

        # Sort: overproduction first (highest gap_qty), then underproduction
        # (largest magnitude shortfall), then balanced — deterministic tie-break by sku_id
        def _sort_key(item: dict[str, Any]) -> tuple[int, float, str]:
            cls = item["classification"]
            order = {"overproduction": 0, "underproduction": 1, "balanced": 2}[cls]
            # For overproduction: sort by gap_qty desc (negate); for underproduction: asc
            sign = -1.0 if cls == "overproduction" else 1.0
            gap = float(item["gap_qty"]) * sign
            return (order, gap, item["sku_id"])

        items.sort(key=_sort_key)

        # Compute counts from the FULL classified list before applying the cap so that
        # summary totals reflect all items even when truncated=True.
        summary = {
            "overproduction_count": sum(
                1 for i in items if i["classification"] == "overproduction"
            ),
            "underproduction_count": sum(
                1 for i in items if i["classification"] == "underproduction"
            ),
            "balanced_count": sum(1 for i in items if i["classification"] == "balanced"),
        }

        truncated = len(items) > _ROW_CAP
        items = items[:_ROW_CAP]

        return ToolResult(
            output={
                "horizon_weeks": horizon_weeks,
                "items": items,
                "summary": summary,
                "truncated": truncated,
                "missing_data": missing_data,
            },
            audit_payload={
                "horizon_weeks": horizon_weeks,
                "location_id": location_filter,
                "overproduction_count": summary["overproduction_count"],
                "underproduction_count": summary["underproduction_count"],
                "balanced_count": summary["balanced_count"],
                "missing_data_count": len(missing_data),
            },
        )


# ---------------------------------------------------------------------------
# Classification helper
# ---------------------------------------------------------------------------


def _classify_gap(
    planned_qty: float,
    expected_demand: float,
) -> tuple[str, float, float | None]:
    """Return (classification, gap_qty, gap_pct) for a plan vs demand pair.

    gap_qty  = planned_qty - expected_demand
    gap_pct  = gap_qty / expected_demand × 100   (None when expected_demand == 0)

    Classification rules (threshold = ±25 %):
      - expected_demand == 0 AND planned_qty > 0  → overproduction (gap_pct=None)
      - expected_demand == 0 AND planned_qty == 0 → balanced
      - gap_pct >  +25                             → overproduction
      - gap_pct < -25                              → underproduction
      - |gap_pct| ≤ 25                             → balanced
    """
    gap_qty = planned_qty - expected_demand

    if expected_demand == 0:
        gap_pct: float | None = None
        if planned_qty > 0:
            classification = "overproduction"
        else:
            classification = "balanced"
        return classification, gap_qty, gap_pct

    gap_pct = gap_qty / expected_demand * 100.0

    if gap_pct > _GAP_THRESHOLD_PCT:
        classification = "overproduction"
    elif gap_pct < -_GAP_THRESHOLD_PCT:
        classification = "underproduction"
    else:
        classification = "balanced"

    return classification, gap_qty, round(gap_pct, 4)


# ---------------------------------------------------------------------------
# SQL helpers
# ---------------------------------------------------------------------------


async def _fetch_production_plan_rows(
    horizon_weeks: int,
    location_filter: str | None,
) -> list[dict[str, Any]]:
    """Return aggregated planned_qty per (sku_id, location_id) within the horizon."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        if location_filter:
            rows = await conn.fetch(
                """
                SELECT
                    sku_id,
                    location_id,
                    SUM(planned_qty) AS planned_qty
                FROM production_plan
                WHERE week_start >= DATE_TRUNC('week', CURRENT_DATE)
                  AND week_start < DATE_TRUNC('week', CURRENT_DATE)
                             + ($1 * INTERVAL '1 week')
                  AND location_id = $2
                GROUP BY sku_id, location_id
                ORDER BY sku_id, location_id
                """,
                horizon_weeks,
                location_filter,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT
                    sku_id,
                    location_id,
                    SUM(planned_qty) AS planned_qty
                FROM production_plan
                WHERE week_start >= DATE_TRUNC('week', CURRENT_DATE)
                  AND week_start < DATE_TRUNC('week', CURRENT_DATE)
                             + ($1 * INTERVAL '1 week')
                GROUP BY sku_id, location_id
                ORDER BY sku_id, location_id
                """,
                horizon_weeks,
            )
        return [dict(r) for r in rows]


async def _fetch_forecast_demand(
    sku_ids: list[str],
    horizon_weeks: int,
) -> dict[str, float]:
    """Return {sku_id: total_forecast_quantity} for SKUs that have forecast rows in horizon.

    Uses the most recent forecast_date for each SKU within the horizon window
    [CURRENT_DATE, CURRENT_DATE + horizon_weeks weeks).
    Returns only SKUs that have at least one qualifying forecast row.
    """
    if not sku_ids:
        return {}
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                sku_id,
                SUM(forecast_qty) AS total_forecast
            FROM forecast_history
            WHERE sku_id = ANY($1)
              AND forecast_date >= CURRENT_DATE
              AND forecast_date < CURRENT_DATE + ($2 * INTERVAL '1 week')
            GROUP BY sku_id
            """,
            sku_ids,
            horizon_weeks,
        )
        return {str(r["sku_id"]): float(r["total_forecast"]) for r in rows}


async def _fetch_runrate_demand(
    sku_ids: list[str],
) -> dict[str, float]:
    """Return {sku_id: avg_daily_demand} from demand_history (30-day window).

    Follows the established avg_daily SQL pattern used across inventory tools.
    SKUs with no rows in the window return 0.0 (surfaced in missing_data by caller).
    """
    if not sku_ids:
        return {}
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                sku_id,
                COALESCE(AVG(quantity), 0) AS avg_daily
            FROM demand_history
            WHERE sku_id = ANY($1)
              AND date >= CURRENT_DATE - ($2 * INTERVAL '1 day')
              AND is_missing IS NOT TRUE
            GROUP BY sku_id
            """,
            sku_ids,
            _RUNRATE_LOOKBACK_DAYS,
        )
        return {str(r["sku_id"]): float(r["avg_daily"]) for r in rows}
