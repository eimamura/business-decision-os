"""analyze_supply_order_timing — T-583

Classifies open supply orders as pull_forward_candidate, push_out_candidate,
or on_track by comparing each order's expected_arrival against the SKU's
projected stockout date (derived from on-hand inventory and demand run-rate).

## Classification rules

For each open supply_orders row (status in pending / confirmed / in_transit):

  1. Join inventory_snapshot.on_hand (SUM across warehouses) for the SKU.
  2. Join demand_history avg_daily run-rate (30-day rolling window, same as
     other tools in this codebase).
  3. Compute:
       projected_stockout_date = today + floor(on_hand / avg_daily)
         (null / missing_data when avg_daily == 0 → "zero-demand SKU ...")
       days_of_cover_at_arrival = (on_hand / avg_daily) - days_until_arrival
         (how many days of cover remain when the order lands)

  4. Classify:
       pull_forward_candidate: expected_arrival > projected_stockout_date
         (supply lands after projected stockout; arrival is too late)
         days_misaligned = (expected_arrival - projected_stockout_date).days  [positive]

       push_out_candidate: days_of_cover_at_arrival >= PUSH_OUT_COVER_DAYS
         (at arrival the SKU still has ≥ 30 days of cover remaining; order is early)
         days_misaligned = floor(days_of_cover_at_arrival - PUSH_OUT_COVER_DAYS)
         expressed as negative (arrival is N days too early relative to the threshold)
         NOTE: a push_out_candidate CANNOT also be a pull_forward_candidate
         (pull_forward takes precedence — if arrival is after stockout, supply is needed).

       on_track: otherwise

  5. PUSH_OUT_COVER_DAYS = 30 (documented constant).
     Rationale: 30 days of remaining cover at the time of arrival means the
     existing inventory could carry the SKU for another month without this
     order.  This is a conservative threshold — higher values reduce false
     push-out signals for fast-movers; lower values increase them.  30 days
     is a common supply-chain reorder-cycle target.

## Output contract (hybrid)

- ``orders`` : per-order rows, sorted by severity (pull_forward first, then
               push_out, then on_track; within each class by |days_misaligned|
               descending; then by order id ascending for determinism).
               Capped to ROW_CAP with ``truncated`` flag.
- ``count``  : total rows PRE-cap (P89 lesson — summary counts before truncation).
- ``summary``: counts per class computed pre-cap:
                 pull_forward_count, push_out_count, on_track_count.
- ``missing_data``: mandatory — zero-demand SKUs, orders with null expected_arrival,
                    SKUs with no inventory_snapshot row.

ANALYTICAL OUTPUT ONLY — no recommendations.  Control Agent concludes.

## Constraints

No LLM calls. All SQL parameterized. Tables used:
  supply_orders, inventory_snapshot, demand_history, sku_master
All are in ALLOWED_READ_TABLES.

Output follows the hybrid tool output contract
(ADR docs/adr/2026-06-10-tool-output-contract-hybrid.md).
"""
from __future__ import annotations

import datetime
import logging
import math
from typing import Any, Literal

from packages.persistence.db import get_pool
from packages.tools._shared import db_error_message
from packages.tools.base import ToolContext, ToolResult

_log = logging.getLogger(__name__)

# Row cap for returned order records.
_ROW_CAP = 100

# Open supply order statuses — same convention as supply_open_orders_tool.py.
_OPEN_STATUSES = ["pending", "confirmed", "in_transit"]

# Demand history look-back for run-rate (days) — house convention (30d).
_RUNRATE_LOOKBACK_DAYS = 30

# Days-of-cover remaining at arrival threshold for push_out classification.
# Documented in module docstring above.
PUSH_OUT_COVER_DAYS = 30

# Classification labels.
_PULL_FORWARD = "pull_forward_candidate"
_PUSH_OUT = "push_out_candidate"
_ON_TRACK = "on_track"

# Sort-key priority per classification (lower = more severe = first).
_CLASSIFICATION_SORT_ORDER: dict[str, int] = {
    _PULL_FORWARD: 0,
    _PUSH_OUT: 1,
    _ON_TRACK: 2,
}


class AnalyzeSupplyOrderTimingTool:
    """Classify open supply orders as pull_forward, push_out, or on_track.

    Computes projected stockout date from on-hand inventory and 30-day demand
    run-rate, then compares each open order's expected_arrival against that date.

    Analytical output only — no recommendations.  No LLM calls — deterministic SQL only.
    """

    name = "analyze_supply_order_timing"
    description = (
        "Classify open supply orders by timing fit: "
        "pull_forward_candidate (arrival after projected stockout — order is too late), "
        "push_out_candidate (arrival while days-of-cover still >= 30 days — order is too early), "
        "or on_track. "
        "Per-order output includes projected_stockout_date, days_of_cover_at_arrival, "
        "days_misaligned (positive = days late past stockout; negative = excess days of cover "
        "above threshold at arrival), and evidence numbers (on_hand, avg_daily_demand). "
        "Ranked by severity (pull_forward first, then push_out, then on_track; within each "
        "class by |days_misaligned| descending). "
        "Call this for SPEC Q8 — 'Which materials or items should be purchased earlier or later?'. "
        "get_delayed_supply_orders is the 'what is already late by status' axis; "
        "this tool is the timing-misalignment axis (arrival vs projected need). "
        "Analytical output only — does not recommend actions."
    )
    safety_level: Literal["read_only", "write", "hitl"] = "read_only"
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "sku_id": {
                "type": "string",
                "description": (
                    "Optional: restrict analysis to a single SKU. "
                    "Omit to analyse all open supply orders."
                ),
            },
        },
        "required": [],
    }
    output_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "orders": {
                "type": "array",
                "description": (
                    "Open supply order timing analysis, sorted by severity: "
                    "pull_forward_candidate first (most urgent), then push_out_candidate, "
                    "then on_track. Within each class by |days_misaligned| descending, "
                    "then order_id ascending."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "order_id": {
                            "type": "string",
                            "description": (
                                "Composite key: sku_id:supplier_id:order_date "
                                "(no DB surrogate key)."
                            ),
                        },
                        "sku_id": {"type": "string"},
                        "supplier_id": {"type": "string"},
                        "order_date": {"type": "string"},
                        "expected_arrival": {"type": "string"},
                        "quantity": {"type": "number"},
                        "status": {"type": "string"},
                        "on_hand": {"type": "number"},
                        "avg_daily_demand": {"type": "number"},
                        "projected_stockout_date": {
                            "type": ["string", "null"],
                            "description": "ISO date string or null when avg_daily_demand == 0.",
                        },
                        "days_of_cover_at_arrival": {
                            "type": ["number", "null"],
                            "description": (
                                "Days of remaining cover when the order is expected to arrive. "
                                "Null when avg_daily_demand == 0."
                            ),
                        },
                        "days_misaligned": {
                            "type": "integer",
                            "description": (
                                "Signed integer: positive = arrival N days after projected "
                                "stockout (pull_forward); negative = excess days of cover "
                                "above threshold at arrival (push_out). Zero for on_track."
                            ),
                        },
                        "classification": {
                            "type": "string",
                            "enum": [
                                "pull_forward_candidate",
                                "push_out_candidate",
                                "on_track",
                            ],
                        },
                    },
                    "required": [
                        "order_id",
                        "sku_id",
                        "supplier_id",
                        "order_date",
                        "expected_arrival",
                        "quantity",
                        "status",
                        "on_hand",
                        "avg_daily_demand",
                        "projected_stockout_date",
                        "days_of_cover_at_arrival",
                        "days_misaligned",
                        "classification",
                    ],
                },
            },
            "count": {
                "type": "integer",
                "description": "Total classified orders (pre-cap).",
            },
            "truncated": {"type": "boolean"},
            "summary": {
                "type": "object",
                "description": "Per-class counts, computed pre-cap.",
                "properties": {
                    "pull_forward_count": {"type": "integer"},
                    "push_out_count": {"type": "integer"},
                    "on_track_count": {"type": "integer"},
                },
                "required": [
                    "pull_forward_count",
                    "push_out_count",
                    "on_track_count",
                ],
            },
            "missing_data": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Notes on data gaps: zero-demand SKUs, orders with null expected_arrival, "
                    "SKUs with no inventory_snapshot row."
                ),
            },
        },
        "required": ["orders", "count", "truncated", "summary", "missing_data"],
    }

    def __init__(self, db_session: Any | None = None) -> None:
        pass

    async def handle(self, input: dict[str, Any], ctx: ToolContext) -> ToolResult:  # noqa: A002
        sku_filter: str | None = input.get("sku_id") or None

        today = datetime.date.today()

        try:
            order_rows = await _fetch_open_orders(sku_filter)
            inventory_map = await _fetch_inventory_map(sku_filter)
            demand_map = await _fetch_demand_map(sku_filter)
        except Exception as exc:
            return ToolResult(
                output={"error": db_error_message(exc)},
                audit_payload={"sku_id": sku_filter},
            )

        classified: list[dict[str, Any]] = []
        missing_data: list[str] = []
        seen_missing: set[str] = set()

        for row in order_rows:
            sku_id: str = str(row["sku_id"])
            supplier_id: str = str(row["supplier_id"])
            order_date_raw = row["order_date"]
            expected_arrival_raw = row["expected_arrival"]
            quantity: float = float(row["quantity"])
            status: str = str(row["status"])

            # --- Normalize dates ---
            order_date_str: str = _date_to_iso(order_date_raw)
            expected_arrival_date: datetime.date | None = _to_date(expected_arrival_raw)
            expected_arrival_str: str | None = (
                expected_arrival_date.isoformat() if expected_arrival_date is not None else None
            )

            # Composite order_id (supply_orders has no surrogate PK).
            order_id = f"{sku_id}:{supplier_id}:{order_date_str}"

            # --- null expected_arrival → missing_data, skip classification ---
            if expected_arrival_date is None:
                note = f"order {order_id}: null expected_arrival — cannot classify timing"
                if note not in seen_missing:
                    missing_data.append(note)
                    seen_missing.add(note)
                continue

            # --- Inventory on-hand ---
            on_hand: float = inventory_map.get(sku_id, 0.0)
            if sku_id not in inventory_map:
                note = f"no inventory_snapshot row for {sku_id} — on_hand assumed 0"
                if note not in seen_missing:
                    missing_data.append(note)
                    seen_missing.add(note)

            # --- Demand run-rate ---
            avg_daily: float = demand_map.get(sku_id, 0.0)
            if avg_daily == 0.0:
                note = (
                    f"zero-demand SKU {sku_id}: no demand_history in last "
                    f"{_RUNRATE_LOOKBACK_DAYS}d — cannot compute projected stockout"
                )
                if note not in seen_missing:
                    missing_data.append(note)
                    seen_missing.add(note)
                # Still include the order in results but classify as on_track with null dates.
                classified.append({
                    "order_id": order_id,
                    "sku_id": sku_id,
                    "supplier_id": supplier_id,
                    "order_date": order_date_str,
                    "expected_arrival": expected_arrival_str,
                    "quantity": quantity,
                    "status": status,
                    "on_hand": on_hand,
                    "avg_daily_demand": 0.0,
                    "projected_stockout_date": None,
                    "days_of_cover_at_arrival": None,
                    "days_misaligned": 0,
                    "classification": _ON_TRACK,
                })
                continue

            # --- Core timing calculations ---
            days_of_stock = on_hand / avg_daily
            projected_stockout_date = today + datetime.timedelta(days=math.floor(days_of_stock))
            days_until_arrival = (expected_arrival_date - today).days

            # days_of_cover_at_arrival: how many days of cover remain when order lands.
            # = (on_hand / avg_daily) - days_until_arrival
            # Positive: stock lasts beyond arrival; negative: already stocked out by arrival.
            days_of_cover_at_arrival = days_of_stock - days_until_arrival

            # --- Classification ---
            if expected_arrival_date > projected_stockout_date:
                # Arrival is after projected stockout → pull_forward_candidate.
                days_misaligned = (expected_arrival_date - projected_stockout_date).days
                classification = _PULL_FORWARD
            elif days_of_cover_at_arrival >= PUSH_OUT_COVER_DAYS:
                # At arrival, cover still >= threshold → push_out_candidate.
                # days_misaligned is negative: excess cover above threshold.
                excess = days_of_cover_at_arrival - PUSH_OUT_COVER_DAYS
                days_misaligned = -int(math.floor(excess))
                classification = _PUSH_OUT
            else:
                days_misaligned = 0
                classification = _ON_TRACK

            classified.append({
                "order_id": order_id,
                "sku_id": sku_id,
                "supplier_id": supplier_id,
                "order_date": order_date_str,
                "expected_arrival": expected_arrival_str,
                "quantity": quantity,
                "status": status,
                "on_hand": on_hand,
                "avg_daily_demand": round(avg_daily, 6),
                "projected_stockout_date": projected_stockout_date.isoformat(),
                "days_of_cover_at_arrival": round(days_of_cover_at_arrival, 4),
                "days_misaligned": days_misaligned,
                "classification": classification,
            })

        # --- Summary counts (pre-cap) ---
        pull_forward_count = sum(1 for o in classified if o["classification"] == _PULL_FORWARD)
        push_out_count = sum(1 for o in classified if o["classification"] == _PUSH_OUT)
        on_track_count = sum(1 for o in classified if o["classification"] == _ON_TRACK)

        # --- Sort: severity class first, then |days_misaligned| desc, then order_id asc ---
        classified.sort(
            key=lambda o: (
                _CLASSIFICATION_SORT_ORDER[o["classification"]],
                -abs(o["days_misaligned"]),
                o["order_id"],
            )
        )

        count = len(classified)
        truncated = count > _ROW_CAP
        classified = classified[:_ROW_CAP]

        return ToolResult(
            output={
                "orders": classified,
                "count": count,
                "truncated": truncated,
                "summary": {
                    "pull_forward_count": pull_forward_count,
                    "push_out_count": push_out_count,
                    "on_track_count": on_track_count,
                },
                "missing_data": missing_data,
            },
            audit_payload={
                "sku_id": sku_filter,
                "order_count": count,
                "pull_forward_count": pull_forward_count,
                "push_out_count": push_out_count,
                "on_track_count": on_track_count,
                "truncated": truncated,
                "missing_data_count": len(missing_data),
            },
        )


# ---------------------------------------------------------------------------
# SQL helpers
# ---------------------------------------------------------------------------


async def _fetch_open_orders(sku_filter: str | None) -> list[dict[str, Any]]:
    """Return all open supply_orders rows for classification."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        if sku_filter:
            rows = await conn.fetch(
                """
                SELECT sku_id, supplier_id, order_date, expected_arrival, quantity, status
                FROM supply_orders
                WHERE status = ANY($1)
                  AND sku_id = $2
                ORDER BY sku_id, expected_arrival ASC NULLS LAST, order_date ASC
                """,
                _OPEN_STATUSES,
                sku_filter,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT sku_id, supplier_id, order_date, expected_arrival, quantity, status
                FROM supply_orders
                WHERE status = ANY($1)
                ORDER BY sku_id, expected_arrival ASC NULLS LAST, order_date ASC
                """,
                _OPEN_STATUSES,
            )
        return [dict(r) for r in rows]


async def _fetch_inventory_map(sku_filter: str | None) -> dict[str, float]:
    """Return {sku_id: total_on_hand} from inventory_snapshot."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        if sku_filter:
            rows = await conn.fetch(
                """
                SELECT sku_id, COALESCE(SUM(on_hand), 0) AS on_hand_qty
                FROM inventory_snapshot
                WHERE sku_id = $1
                GROUP BY sku_id
                """,
                sku_filter,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT sku_id, COALESCE(SUM(on_hand), 0) AS on_hand_qty
                FROM inventory_snapshot
                GROUP BY sku_id
                """
            )
        return {str(r["sku_id"]): float(r["on_hand_qty"]) for r in rows}


async def _fetch_demand_map(sku_filter: str | None) -> dict[str, float]:
    """Return {sku_id: avg_daily_demand} from the last 30-day demand_history window."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        if sku_filter:
            rows = await conn.fetch(
                """
                SELECT sku_id, COALESCE(AVG(quantity), 0) AS avg_daily
                FROM demand_history
                WHERE date >= CURRENT_DATE - ($1 * INTERVAL '1 day')
                  AND is_missing IS NOT TRUE
                  AND sku_id = $2
                GROUP BY sku_id
                """,
                _RUNRATE_LOOKBACK_DAYS,
                sku_filter,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT sku_id, COALESCE(AVG(quantity), 0) AS avg_daily
                FROM demand_history
                WHERE date >= CURRENT_DATE - ($1 * INTERVAL '1 day')
                  AND is_missing IS NOT TRUE
                GROUP BY sku_id
                """,
                _RUNRATE_LOOKBACK_DAYS,
            )
        return {str(r["sku_id"]): float(r["avg_daily"]) for r in rows}


# ---------------------------------------------------------------------------
# Pure-Python date helpers (exported for unit tests)
# ---------------------------------------------------------------------------


def _to_date(value: Any) -> datetime.date | None:
    """Coerce an asyncpg date/datetime/str value to datetime.date or None."""
    if value is None:
        return None
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    try:
        return datetime.date.fromisoformat(str(value))
    except ValueError:
        return None


def _date_to_iso(value: Any) -> str:
    """Coerce a date/datetime to an ISO string; return empty string on None."""
    d = _to_date(value)
    return d.isoformat() if d is not None else ""
