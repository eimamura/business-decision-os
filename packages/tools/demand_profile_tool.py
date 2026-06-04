from __future__ import annotations

import statistics
from typing import Any, Literal

from packages.persistence.db import get_pool
from packages.tools.base import ToolContext, ToolResult


class DemandProfileTool:
    name = "profile_demand_data"
    description = (
        "Profile demand data quality and statistical distribution for a SKU "
        "over a lookback period"
    )
    safety_level: Literal["read_only", "write", "hitl"] = "read_only"
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "sku_id": {
                "type": "string",
                "description": "SKU to profile; omit for cross-SKU summary",
            },
            "lookback_days": {"type": "integer", "minimum": 1, "default": 90},
        },
        "required": [],
    }
    output_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "sku_id": {"type": ["string", "null"]},
            "record_count": {"type": "integer"},
            "missing_rate": {"type": "number"},
            "zero_demand_days": {"type": "integer"},
            "stockout_suspected_days": {"type": "integer"},
            "mean": {"type": ["number", "null"]},
            "std": {"type": ["number", "null"]},
            "cv": {"type": ["number", "null"]},
            "data_quality_score": {"type": "number"},
            "date_range": {
                "type": "object",
                "properties": {
                    "start": {"type": "string"},
                    "end": {"type": "string"},
                },
            },
        },
    }

    def __init__(self, db_session: Any | None = None) -> None:
        pass

    async def handle(self, input: dict[str, Any], ctx: ToolContext) -> ToolResult:
        sku_id: str | None = input.get("sku_id") or None
        lookback_days: int = int(input.get("lookback_days", 90))

        try:
            rows = await _fetch_demand_rows(sku_id, lookback_days)
        except Exception as exc:
            return ToolResult(
                output={"error": _connection_error_message(exc)},
                audit_payload={"sku_id": sku_id, "lookback_days": lookback_days, "record_count": 0},
            )

        record_count = len(rows)

        if record_count == 0:
            return ToolResult(
                output={
                    "sku_id": sku_id,
                    "record_count": 0,
                    "missing_rate": 0.0,
                    "zero_demand_days": 0,
                    "stockout_suspected_days": 0,
                    "mean": None,
                    "std": None,
                    "cv": None,
                    "data_quality_score": 1.0,
                    "date_range": {"start": "", "end": ""},
                },
                audit_payload={"sku_id": sku_id, "lookback_days": lookback_days, "record_count": 0},
            )

        missing_count = sum(1 for r in rows if r["is_missing"])
        zero_demand_days = sum(1 for r in rows if r["quantity"] == 0)
        stockout_suspected_days = missing_count
        missing_rate = missing_count / record_count

        non_null_quantities = [
            float(r["quantity"]) for r in rows if r["quantity"] is not None
        ]
        mean: float | None = None
        std: float | None = None
        cv: float | None = None

        if non_null_quantities:
            mean = statistics.mean(non_null_quantities)
            std = statistics.stdev(non_null_quantities) if len(non_null_quantities) >= 2 else 0.0
            if mean and mean != 0.0:
                cv = std / mean
            else:
                cv = None

        raw_score = 1.0 - min(1.0, missing_rate + zero_demand_days / max(record_count, 1) * 0.5)
        data_quality_score = max(0.0, min(1.0, raw_score))

        dates = [r["date"] for r in rows if r["date"] is not None]
        date_start = min(dates).isoformat() if dates else ""
        date_end = max(dates).isoformat() if dates else ""

        return ToolResult(
            output={
                "sku_id": sku_id,
                "record_count": record_count,
                "missing_rate": missing_rate,
                "zero_demand_days": zero_demand_days,
                "stockout_suspected_days": stockout_suspected_days,
                "mean": mean,
                "std": std,
                "cv": cv,
                "data_quality_score": data_quality_score,
                "date_range": {"start": date_start, "end": date_end},
            },
            audit_payload={
                "sku_id": sku_id,
                "lookback_days": lookback_days,
                "record_count": record_count,
            },
        )


async def _fetch_demand_rows(sku_id: str | None, lookback_days: int) -> list[dict[str, Any]]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        if sku_id is None:
            rows = await conn.fetch(
                """
                SELECT date, quantity, is_missing
                FROM demand_history
                WHERE date >= CURRENT_DATE - ($1 * INTERVAL '1 day')
                ORDER BY date
                """,
                lookback_days,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT date, quantity, is_missing
                FROM demand_history
                WHERE date >= CURRENT_DATE - ($1 * INTERVAL '1 day')
                  AND sku_id = $2
                ORDER BY date
                """,
                lookback_days,
                sku_id,
            )
        return [dict(r) for r in rows]


def _connection_error_message(exc: Exception) -> str:
    message = str(exc).lower()
    class_name = exc.__class__.__name__.lower()
    module_name = exc.__class__.__module__.lower()
    if isinstance(exc, RuntimeError) and "database_url" in message:
        return "no database connection"
    if "asyncpg" in module_name and (
        "connection" in class_name
        or "connection" in message
        or "connect call failed" in message
    ):
        return "no database connection"
    return str(exc)
