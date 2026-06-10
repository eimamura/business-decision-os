from __future__ import annotations

import json
import statistics
from typing import Any, Literal

from packages.persistence.db import get_pool
from packages.tools._shared import db_error_message
from packages.tools.base import ToolContext, ToolResult


class DemandSegmentTool:
    name = "segment_demand"
    description = (
        "Rank SKUs or summarize demand distribution across a dimension (sku or customer)"
    )
    safety_level: Literal["read_only", "write", "hitl"] = "read_only"
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "dimension": {
                "type": "string",
                "enum": ["sku", "customer"],
                "default": "sku",
            },
            "lookback_days": {"type": "integer", "minimum": 1, "default": 90},
            "top_n": {"type": "integer", "minimum": 1, "maximum": 50, "default": 10},
        },
        "required": [],
    }
    output_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "dimension": {"type": "string"},
            "lookback_days": {"type": "integer"},
            "total_demand": {"type": "number"},
            "segments": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "total_qty": {"type": "number"},
                        "demand_share": {"type": "number"},
                        "trend_direction": {"type": "string"},
                        "cv": {"type": ["number", "null"]},
                    },
                },
            },
            "missing_data": {"type": "array", "items": {"type": "string"}},
        },
    }

    def __init__(self, db_session: Any | None = None) -> None:
        pass

    async def handle(self, input: dict[str, Any], ctx: ToolContext) -> ToolResult:
        dimension: str = input.get("dimension", "sku")
        lookback_days: int = int(input.get("lookback_days", 90))
        top_n: int = int(input.get("top_n", 10))

        try:
            if dimension == "sku":
                segments, total_demand = await _compute_sku_segments(lookback_days, top_n)
            else:
                segments, total_demand = await _compute_customer_segments(lookback_days, top_n)
        except Exception as exc:
            return ToolResult(
                output={"error": db_error_message(exc)},
                audit_payload={
                    "dimension": dimension,
                    "lookback_days": lookback_days,
                    "top_n": top_n,
                    "segment_count": 0,
                },
            )

        return ToolResult(
            output={
                "dimension": dimension,
                "lookback_days": lookback_days,
                "total_demand": round(float(total_demand), 4),
                "segments": segments,
                "missing_data": (
                    [f"no demand_history rows in last {lookback_days} days"]
                    if total_demand == 0.0 else []
                ),
            },
            audit_payload={
                "dimension": dimension,
                "lookback_days": lookback_days,
                "top_n": top_n,
                "segment_count": len(segments),
            },
        )


async def _compute_sku_segments(
    lookback_days: int, top_n: int
) -> tuple[list[dict[str, Any]], float]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT sku_id, date, quantity
            FROM demand_history
            WHERE date >= CURRENT_DATE - ($1 * INTERVAL '1 day')
              AND is_missing IS NOT TRUE
              AND quantity IS NOT NULL
            ORDER BY sku_id, date
            """,
            lookback_days,
        )

    # Group rows by sku_id, preserving chronological order
    sku_rows: dict[str, list[tuple[Any, float]]] = {}
    for row in rows:
        sid = row["sku_id"]
        if sid not in sku_rows:
            sku_rows[sid] = []
        sku_rows[sid].append((row["date"], float(row["quantity"])))

    grand_total = sum(
        qty for entries in sku_rows.values() for _, qty in entries
    )

    segments: list[dict[str, Any]] = []
    for sku_id, entries in sku_rows.items():
        quantities = [qty for _, qty in entries]
        total_qty = sum(quantities)
        demand_share = total_qty / grand_total if grand_total > 0 else 0.0

        cv: float | None = None
        if len(quantities) >= 2:
            mean_qty = statistics.mean(quantities)
            if mean_qty > 0:
                cv = round(statistics.stdev(quantities) / mean_qty, 6)
            else:
                cv = 0.0

        trend_direction = _compute_trend(quantities)

        segments.append({
            "id": sku_id,
            "total_qty": round(total_qty, 4),
            "demand_share": round(demand_share, 6),
            "trend_direction": trend_direction,
            "cv": cv,
        })

    segments.sort(key=lambda s: s["total_qty"], reverse=True)
    return segments[:top_n], grand_total


async def _compute_customer_segments(
    lookback_days: int, top_n: int
) -> tuple[list[dict[str, Any]], float]:
    pool = await get_pool()

    # Fetch all customer affinity data
    async with pool.acquire() as conn:
        customer_rows = await conn.fetch(
            """
            SELECT customer_id, sku_affinity_json
            FROM customer_master
            """
        )

    # Collect all SKU IDs referenced in affinities
    customer_affinities: dict[str, dict[str, float]] = {}
    all_sku_ids: set[str] = set()

    for row in customer_rows:
        raw = row.get("sku_affinity_json")
        if not raw:
            continue
        affinity = _parse_affinity(raw)
        if affinity is None:
            continue
        weights = _affinity_to_weights(affinity)
        if weights:
            customer_affinities[row["customer_id"]] = weights
            all_sku_ids.update(weights.keys())

    if not customer_affinities:
        return [], 0.0

    # Fetch total demand for each referenced SKU
    async with pool.acquire() as conn:
        sku_totals_rows = await conn.fetch(
            """
            SELECT sku_id, COALESCE(SUM(quantity), 0) AS total_qty
            FROM demand_history
            WHERE date >= CURRENT_DATE - ($1 * INTERVAL '1 day')
              AND is_missing IS NOT TRUE
              AND quantity IS NOT NULL
            GROUP BY sku_id
            """,
            lookback_days,
        )

    sku_totals: dict[str, float] = {r["sku_id"]: float(r["total_qty"]) for r in sku_totals_rows}

    # Distribute SKU demand proportionally across customers with affinity
    # First, for each SKU compute total affinity weight across all customers
    sku_weight_totals: dict[str, float] = {}
    for weights in customer_affinities.values():
        for sku_id, w in weights.items():
            sku_weight_totals[sku_id] = sku_weight_totals.get(sku_id, 0.0) + w

    customer_demand: dict[str, float] = {}
    for customer_id, weights in customer_affinities.items():
        total = 0.0
        for sku_id, w in weights.items():
            sku_total = sku_totals.get(sku_id, 0.0)
            wt = sku_weight_totals.get(sku_id, 0.0)
            if wt > 0:
                total += sku_total * (w / wt)
        customer_demand[customer_id] = total

    grand_total = sum(customer_demand.values())
    segments: list[dict[str, Any]] = []
    for customer_id, demand in customer_demand.items():
        demand_share = demand / grand_total if grand_total > 0 else 0.0
        segments.append({
            "id": customer_id,
            "total_qty": round(demand, 4),
            "demand_share": round(demand_share, 6),
            "trend_direction": "flat",
            "cv": None,
        })

    segments.sort(key=lambda s: s["total_qty"], reverse=True)
    return segments[:top_n], grand_total


def _compute_trend(quantities: list[float]) -> str:
    """Compare first-half vs second-half averages to determine trend."""
    n = len(quantities)
    if n < 2:
        return "flat"
    mid = n // 2
    first_half = quantities[:mid]
    second_half = quantities[mid:]
    first_avg = sum(first_half) / len(first_half) if first_half else 0.0
    second_avg = sum(second_half) / len(second_half) if second_half else 0.0
    if first_avg == 0.0:
        return "flat"
    ratio = second_avg / first_avg
    if ratio > 1.05:
        return "up"
    if ratio < 0.95:
        return "down"
    return "flat"


def _parse_affinity(raw: Any) -> dict[str, Any] | list[Any] | None:
    if isinstance(raw, (dict, list)):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, (dict, list)):
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass
    return None


def _affinity_to_weights(affinity: dict[str, Any] | list[Any]) -> dict[str, float]:
    """Convert affinity structure to {sku_id: weight} mapping."""
    if isinstance(affinity, dict):
        result: dict[str, float] = {}
        for sku_id, val in affinity.items():
            try:
                result[sku_id] = float(val)
            except (TypeError, ValueError):
                result[sku_id] = 1.0
        return result
    if isinstance(affinity, list):
        return {sku_id: 1.0 for sku_id in affinity if isinstance(sku_id, str)}
    return {}


