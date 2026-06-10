from __future__ import annotations

import datetime
from typing import Any, Literal

from packages.persistence.db import get_pool
from packages.tools._shared import db_error_message
from packages.tools.base import ToolContext, ToolResult


class DemandCompareTool:
    name = "compare_demand_periods"
    description = (
        "Compare total and average demand between two date ranges for a SKU or all SKUs"
    )
    safety_level: Literal["read_only", "write", "hitl"] = "read_only"
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "sku_id": {
                "type": "string",
                "description": "Omit for all SKUs",
            },
            "period_a": {
                "type": "object",
                "properties": {
                    "start": {"type": "string", "description": "ISO date YYYY-MM-DD"},
                    "end": {"type": "string", "description": "ISO date YYYY-MM-DD"},
                },
                "required": ["start", "end"],
            },
            "period_b": {
                "type": "object",
                "properties": {
                    "start": {"type": "string", "description": "ISO date YYYY-MM-DD"},
                    "end": {"type": "string", "description": "ISO date YYYY-MM-DD"},
                },
                "required": ["start", "end"],
            },
        },
        "required": ["period_a", "period_b"],
    }
    output_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "sku_id": {"type": ["string", "null"]},
            "period_a": {
                "type": "object",
                "properties": {
                    "start": {"type": "string"},
                    "end": {"type": "string"},
                    "total_qty": {"type": "number"},
                    "daily_avg": {"type": "number"},
                    "days": {"type": "integer"},
                },
            },
            "period_b": {
                "type": "object",
                "properties": {
                    "start": {"type": "string"},
                    "end": {"type": "string"},
                    "total_qty": {"type": "number"},
                    "daily_avg": {"type": "number"},
                    "days": {"type": "integer"},
                },
            },
            "change_units": {"type": "number"},
            "change_pct": {"type": ["number", "null"]},
            "missing_data": {"type": "array", "items": {"type": "string"}},
        },
    }

    def __init__(self, db_session: Any | None = None) -> None:
        pass

    async def handle(self, input: dict[str, Any], ctx: ToolContext) -> ToolResult:
        sku_id: str | None = input.get("sku_id") or None
        period_a_raw: dict[str, str] = input.get("period_a", {})
        period_b_raw: dict[str, str] = input.get("period_b", {})

        try:
            a_start = datetime.date.fromisoformat(period_a_raw["start"])
            a_end = datetime.date.fromisoformat(period_a_raw["end"])
            b_start = datetime.date.fromisoformat(period_b_raw["start"])
            b_end = datetime.date.fromisoformat(period_b_raw["end"])
        except (KeyError, ValueError) as exc:
            return ToolResult(
                output={"error": f"Invalid date format: {exc}"},
                audit_payload={
                    "sku_id": sku_id,
                    "period_a_start": period_a_raw.get("start"),
                    "period_b_end": period_b_raw.get("end"),
                },
            )

        try:
            total_a = await _fetch_period_total(sku_id, a_start, a_end)
            total_b = await _fetch_period_total(sku_id, b_start, b_end)
        except Exception as exc:
            return ToolResult(
                output={"error": db_error_message(exc)},
                audit_payload={
                    "sku_id": sku_id,
                    "period_a_start": a_start.isoformat(),
                    "period_b_end": b_end.isoformat(),
                },
            )

        days_a = (a_end - a_start).days + 1
        days_b = (b_end - b_start).days + 1

        daily_avg_a = total_a / days_a if days_a > 0 else 0.0
        daily_avg_b = total_b / days_b if days_b > 0 else 0.0

        change_units = total_b - total_a
        change_pct: float | None = None
        if total_a > 0:
            change_pct = round(change_units / total_a * 100, 6)

        missing_data: list[str] = []
        sku_label = sku_id or "all SKUs"
        if total_a == 0.0:
            missing_data.append(
                f"no demand_history rows for {sku_label} in period_a "
                f"({a_start.isoformat()} to {a_end.isoformat()})"
            )
        if total_b == 0.0:
            missing_data.append(
                f"no demand_history rows for {sku_label} in period_b "
                f"({b_start.isoformat()} to {b_end.isoformat()})"
            )

        return ToolResult(
            output={
                "sku_id": sku_id,
                "period_a": {
                    "start": a_start.isoformat(),
                    "end": a_end.isoformat(),
                    "total_qty": round(total_a, 4),
                    "daily_avg": round(daily_avg_a, 6),
                    "days": days_a,
                },
                "period_b": {
                    "start": b_start.isoformat(),
                    "end": b_end.isoformat(),
                    "total_qty": round(total_b, 4),
                    "daily_avg": round(daily_avg_b, 6),
                    "days": days_b,
                },
                "change_units": round(change_units, 4),
                "change_pct": change_pct,
                "missing_data": missing_data,
            },
            audit_payload={
                "sku_id": sku_id,
                "period_a_start": a_start.isoformat(),
                "period_b_end": b_end.isoformat(),
            },
        )


async def _fetch_period_total(
    sku_id: str | None,
    start: datetime.date,
    end: datetime.date,
) -> float:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT COALESCE(SUM(quantity), 0) AS total_qty
            FROM demand_history
            WHERE date >= $1 AND date <= $2
              AND ($3::text IS NULL OR sku_id = $3)
              AND is_missing IS NOT TRUE
            """,
            start,
            end,
            sku_id,
        )
        return float(row["total_qty"]) if row else 0.0


