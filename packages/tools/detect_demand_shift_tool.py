"""detect_demand_shift — T-549

Compares aggregated customer_orders quantity between two time windows
(default: last 28 days vs prior 28 days), grouped by customer and by region.

## Demand signal source

Customer/region demand is answered from customer_orders, NOT from demand_history.
demand_history is the SKU consumption series feeding forecast/stockout tools.
All customer and region demand-shift questions must go through this tool.
(ADR docs/adr/2026-06-11-order-to-ship-and-production-data-domains.md)

## Status filter

Includes all non-cancelled orders: open, allocated, shipped.
Cancelled orders are excluded because they represent revoked intent, not
actual demand signal. This tool answers "did ordering behaviour change?" —
not "did fulfilment change?".

## Window parameters

- window_days  : length of each window in days (default 28)
- end_date_offset : number of days before today to use as the current window
  end date (default 1, i.e. yesterday). The current window ends at
  today - end_date_offset; prior window immediately precedes it.

  current window : [today - end_date_offset - window_days + 1, today - end_date_offset]
  prior window   : [today - end_date_offset - 2*window_days + 1,
                    today - end_date_offset - window_days]

## Output contract (hybrid)

- customer_shifts : top shifts grouped by customer (capped to ROW_CAP, truncated flag)
- region_shifts   : top shifts grouped by region (capped to ROW_CAP, truncated flag)
- missing_data    : list of note strings for edge cases

## Baseline handling

- Groups with neither window having activity are excluded entirely.
- Zero prior + positive current → flagged as "new_activity" (pct_change=null).
- Positive prior + zero current → "full_decline" (pct_change=-100.0).
- Both zero → excluded.

No LLM calls. All queries are parameterized and restricted to ALLOWED_READ_TABLES.
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

# Maximum number of shift records returned per grouping axis before truncated=True.
_ROW_CAP = 50

# Non-cancelled statuses representing active demand signal.
_ACTIVE_STATUSES = ["open", "allocated", "shipped"]


class DetectDemandShiftTool:
    """Compare customer_orders quantity between two windows by customer and region.

    Returns top-N shifts (growth and decline) for both grouping axes with
    percent change, absolute change, and contributing SKUs per shifted group.

    No LLM calls — deterministic SQL + Python aggregation only.
    """

    name = "detect_demand_shift"
    description = (
        "Detect demand shifts by customer and by region by comparing customer_orders "
        "quantity between two consecutive time windows (default: last 28 days vs prior "
        "28 days). Returns top growing and declining customers/regions with pct change, "
        "absolute change, and contributing SKUs. "
        "Call this for SPEC Q9 — customer/region demand change questions. "
        "segment_demand and compare_demand_periods are SKU-axis tools (demand_history); "
        "this tool is the customer/region axis (customer_orders). "
        "Excludes cancelled orders; includes open, allocated, shipped."
    )
    safety_level: Literal["read_only", "write", "hitl"] = "read_only"
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "window_days": {
                "type": "integer",
                "minimum": 1,
                "default": 28,
                "description": (
                    "Length of each comparison window in days. "
                    "Current: [today-offset-window_days+1, today-offset]; "
                    "prior: [today-offset-2*window_days, today-offset-window_days-1]. "
                    "Default 28."
                ),
            },
            "end_date_offset": {
                "type": "integer",
                "minimum": 0,
                "default": 1,
                "description": (
                    "Days before today to use as the current window end date. "
                    "Default 1 (yesterday). Set to 0 to include today."
                ),
            },
        },
        "required": [],
    }
    output_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "window": {
                "type": "object",
                "description": "Window date boundaries used in this run",
                "properties": {
                    "current_start": {"type": "string"},
                    "current_end": {"type": "string"},
                    "prior_start": {"type": "string"},
                    "prior_end": {"type": "string"},
                    "window_days": {"type": "integer"},
                },
            },
            "customer_shifts": {
                "type": "object",
                "properties": {
                    "growth": {
                        "type": "array",
                        "description": "Customers with increased quantity (highest first)",
                        "items": {"$ref": "#/$defs/ShiftRecord"},
                    },
                    "decline": {
                        "type": "array",
                        "description": "Customers with decreased qty (highest abs decline first)",
                        "items": {"$ref": "#/$defs/ShiftRecord"},
                    },
                    "truncated": {"type": "boolean"},
                },
            },
            "region_shifts": {
                "type": "object",
                "properties": {
                    "growth": {
                        "type": "array",
                        "description": "Regions with increased quantity (highest first)",
                        "items": {"$ref": "#/$defs/ShiftRecord"},
                    },
                    "decline": {
                        "type": "array",
                        "description": "Regions with decreased qty (highest abs decline first)",
                        "items": {"$ref": "#/$defs/ShiftRecord"},
                    },
                    "truncated": {"type": "boolean"},
                },
            },
            "missing_data": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Notes on edge cases: new_activity (no prior baseline), "
                    "full_decline (prior activity, zero current), or data gaps."
                ),
            },
        },
        "$defs": {
            "ShiftRecord": {
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "description": "customer_id or region name",
                    },
                    "prior_qty": {"type": "integer"},
                    "current_qty": {"type": "integer"},
                    "abs_change": {"type": "integer"},
                    "pct_change": {
                        "type": ["number", "null"],
                        "description": (
                            "Percent change from prior to current. "
                            "null when prior_qty == 0 (new_activity)."
                        ),
                    },
                    "activity_flag": {
                        "type": ["string", "null"],
                        "description": (
                            "'new_activity' when prior_qty == 0; "
                            "'full_decline' when current_qty == 0; "
                            "null otherwise."
                        ),
                    },
                    "top_skus": {
                        "type": "array",
                        "description": "Top SKUs by absolute quantity change within this group",
                        "items": {
                            "type": "object",
                            "properties": {
                                "sku_id": {"type": "string"},
                                "prior_qty": {"type": "integer"},
                                "current_qty": {"type": "integer"},
                                "abs_change": {"type": "integer"},
                            },
                        },
                    },
                },
                "required": ["id", "prior_qty", "current_qty", "abs_change", "pct_change"],
            },
        },
        "required": ["window", "customer_shifts", "region_shifts", "missing_data"],
    }

    def __init__(self, db_session: Any | None = None) -> None:
        pass

    async def handle(self, input: dict[str, Any], ctx: ToolContext) -> ToolResult:  # noqa: A002
        _window_days = input.get("window_days")
        window_days: int = int(_window_days if _window_days is not None else 28)
        _end_date_offset = input.get("end_date_offset")
        end_date_offset: int = int(_end_date_offset if _end_date_offset is not None else 1)

        if window_days < 1:
            return ToolResult(
                output={"error": "window_days must be >= 1"},
                audit_payload={"window_days": window_days, "end_date_offset": end_date_offset},
            )

        today = datetime.date.today()
        current_end = today - datetime.timedelta(days=end_date_offset)
        current_start = current_end - datetime.timedelta(days=window_days - 1)
        prior_end = current_start - datetime.timedelta(days=1)
        prior_start = prior_end - datetime.timedelta(days=window_days - 1)

        window_info = {
            "current_start": current_start.isoformat(),
            "current_end": current_end.isoformat(),
            "prior_start": prior_start.isoformat(),
            "prior_end": prior_end.isoformat(),
            "window_days": window_days,
        }

        try:
            customer_rows = await _fetch_grouped_quantities(
                "customer_id", current_start, current_end, prior_start, prior_end
            )
            region_rows = await _fetch_grouped_quantities(
                "region", current_start, current_end, prior_start, prior_end
            )
        except Exception as exc:
            return ToolResult(
                output={"error": db_error_message(exc)},
                audit_payload={
                    "window_days": window_days,
                    "end_date_offset": end_date_offset,
                    "current_start": current_start.isoformat(),
                    "current_end": current_end.isoformat(),
                },
            )

        # Fetch per-SKU breakdown for top-SKU attribution
        try:
            customer_sku_rows = await _fetch_sku_breakdown(
                "customer_id", current_start, current_end, prior_start, prior_end
            )
            region_sku_rows = await _fetch_sku_breakdown(
                "region", current_start, current_end, prior_start, prior_end
            )
        except Exception as exc:
            _log.warning("SKU breakdown query failed (%s); top_skus will be empty", exc)
            customer_sku_rows = []
            region_sku_rows = []

        missing_data: list[str] = []

        customer_shifts = _build_shifts(customer_rows, customer_sku_rows, missing_data)
        region_shifts = _build_shifts(region_rows, region_sku_rows, missing_data)

        return ToolResult(
            output={
                "window": window_info,
                "customer_shifts": customer_shifts,
                "region_shifts": region_shifts,
                "missing_data": missing_data,
            },
            audit_payload={
                "window_days": window_days,
                "end_date_offset": end_date_offset,
                "current_start": current_start.isoformat(),
                "current_end": current_end.isoformat(),
                "customer_growth_count": len(customer_shifts["growth"]),
                "customer_decline_count": len(customer_shifts["decline"]),
                "region_growth_count": len(region_shifts["growth"]),
                "region_decline_count": len(region_shifts["decline"]),
            },
        )


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------


def _compute_shift(prior_qty: int, current_qty: int) -> tuple[int | float | None, str | None]:
    """Return (pct_change, activity_flag) for a group.

    Returns:
      (float, None)          when both windows have activity
      (None, 'new_activity') when prior_qty == 0 and current_qty > 0
      (-100.0, 'full_decline') when prior_qty > 0 and current_qty == 0
    """
    if prior_qty == 0 and current_qty > 0:
        return None, "new_activity"
    if prior_qty > 0 and current_qty == 0:
        return -100.0, "full_decline"
    if prior_qty == 0 and current_qty == 0:
        # Both zero — caller should filter these out before calling
        return 0.0, None
    pct = round((current_qty - prior_qty) / prior_qty * 100, 4)
    return pct, None


def _build_shift_record(
    group_id: str,
    prior_qty: int,
    current_qty: int,
    top_skus: list[dict[str, Any]],
    missing_data: list[str],
) -> dict[str, Any] | None:
    """Build a single shift record dict, or return None if both windows are zero."""
    if prior_qty == 0 and current_qty == 0:
        return None  # no activity in either window — exclude silently

    abs_change = current_qty - prior_qty
    pct_change, activity_flag = _compute_shift(prior_qty, current_qty)

    if activity_flag == "new_activity":
        missing_data.append(
            f"{group_id}: no prior-window baseline (current_qty={current_qty}); "
            "flagged as new_activity — pct_change=null"
        )

    return {
        "id": group_id,
        "prior_qty": prior_qty,
        "current_qty": current_qty,
        "abs_change": abs_change,
        "pct_change": pct_change,
        "activity_flag": activity_flag,
        "top_skus": top_skus,
    }


def _build_shifts(
    agg_rows: list[dict[str, Any]],
    sku_rows: list[dict[str, Any]],
    missing_data: list[str],
) -> dict[str, Any]:
    """Build growth/decline lists from aggregated rows and SKU detail rows."""
    # Index SKU detail by group_id
    sku_by_group: dict[str, list[dict[str, Any]]] = {}
    for row in sku_rows:
        gid = str(row["group_id"])
        if gid not in sku_by_group:
            sku_by_group[gid] = []
        prior = int(row["prior_qty"])
        current = int(row["current_qty"])
        sku_by_group[gid].append({
            "sku_id": str(row["sku_id"]),
            "prior_qty": prior,
            "current_qty": current,
            "abs_change": current - prior,
        })

    # Sort top SKUs within each group by abs_change desc
    for gid in sku_by_group:
        sku_by_group[gid].sort(key=lambda s: abs(s["abs_change"]), reverse=True)

    records: list[dict[str, Any]] = []
    for row in agg_rows:
        gid = str(row["group_id"])
        prior_qty = int(row["prior_qty"])
        current_qty = int(row["current_qty"])
        top_skus = sku_by_group.get(gid, [])[:5]  # cap to top-5 SKUs per group
        rec = _build_shift_record(gid, prior_qty, current_qty, top_skus, missing_data)
        if rec is not None:
            records.append(rec)

    growth = sorted(
        [r for r in records if r["abs_change"] > 0],
        key=lambda r: r["abs_change"],
        reverse=True,
    )
    decline = sorted(
        [r for r in records if r["abs_change"] < 0],
        key=lambda r: r["abs_change"],  # most negative first
    )

    truncated = len(growth) > _ROW_CAP or len(decline) > _ROW_CAP
    growth = growth[:_ROW_CAP]
    decline = decline[:_ROW_CAP]

    return {"growth": growth, "decline": decline, "truncated": truncated}


# ---------------------------------------------------------------------------
# SQL query helpers
# ---------------------------------------------------------------------------


async def _fetch_grouped_quantities(
    group_col: str,
    current_start: datetime.date,
    current_end: datetime.date,
    prior_start: datetime.date,
    prior_end: datetime.date,
) -> list[dict[str, Any]]:
    """Fetch aggregated prior/current quantities grouped by group_col.

    group_col must be a literal column name (customer_id or region) — never user input.
    Returns groups where at least one window has non-zero quantity.
    """
    # group_col is restricted to known literals; safe to interpolate
    # (never comes from user input — callers pass a string constant).
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT
                {group_col}                                AS group_id,
                COALESCE(SUM(CASE
                    WHEN order_date >= $1 AND order_date <= $2 THEN quantity ELSE 0
                END), 0)::bigint                           AS current_qty,
                COALESCE(SUM(CASE
                    WHEN order_date >= $3 AND order_date <= $4 THEN quantity ELSE 0
                END), 0)::bigint                           AS prior_qty
            FROM customer_orders
            WHERE status <> 'cancelled'
              AND order_date >= $3
              AND order_date <= $2
            GROUP BY {group_col}
            HAVING
                SUM(CASE WHEN order_date >= $1 AND order_date <= $2
                         THEN quantity ELSE 0 END) > 0
                OR
                SUM(CASE WHEN order_date >= $3 AND order_date <= $4
                         THEN quantity ELSE 0 END) > 0
            ORDER BY {group_col}
            """,
            current_start,
            current_end,
            prior_start,
            prior_end,
        )
        return [dict(r) for r in rows]


async def _fetch_sku_breakdown(
    group_col: str,
    current_start: datetime.date,
    current_end: datetime.date,
    prior_start: datetime.date,
    prior_end: datetime.date,
) -> list[dict[str, Any]]:
    """Fetch per-SKU prior/current quantities grouped by (group_col, sku_id).

    Used to populate top_skus in shift records.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT
                {group_col}                                AS group_id,
                sku_id,
                COALESCE(SUM(CASE
                    WHEN order_date >= $1 AND order_date <= $2 THEN quantity ELSE 0
                END), 0)::bigint                           AS current_qty,
                COALESCE(SUM(CASE
                    WHEN order_date >= $3 AND order_date <= $4 THEN quantity ELSE 0
                END), 0)::bigint                           AS prior_qty
            FROM customer_orders
            WHERE status <> 'cancelled'
              AND order_date >= $3
              AND order_date <= $2
            GROUP BY {group_col}, sku_id
            ORDER BY {group_col}, sku_id
            """,
            current_start,
            current_end,
            prior_start,
            prior_end,
        )
        return [dict(r) for r in rows]
