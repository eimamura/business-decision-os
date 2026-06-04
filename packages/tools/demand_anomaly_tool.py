from __future__ import annotations

from typing import Any, Literal

from packages.persistence.db import get_pool
from packages.tools.base import ToolContext, ToolResult


class DemandAnomalyTool:
    name = "detect_demand_anomalies"
    description = (
        "Detect demand spikes, drops, and stockout periods using z-score analysis"
    )
    safety_level: Literal["read_only", "write", "hitl"] = "read_only"
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "sku_id": {"type": "string"},
            "lookback_days": {"type": "integer", "minimum": 7, "default": 90},
            "z_threshold": {"type": "number", "minimum": 0.5, "default": 2.5},
        },
        "required": ["sku_id"],
    }
    output_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "sku_id": {"type": "string"},
            "anomaly_count": {"type": "integer"},
            "anomalies": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "date": {"type": "string"},
                        "quantity": {"type": ["number", "null"]},
                        "z_score": {"type": ["number", "null"]},
                        "anomaly_type": {"type": "string"},
                    },
                },
            },
        },
    }

    def __init__(self, db_session: Any | None = None) -> None:
        pass

    async def handle(self, input: dict[str, Any], ctx: ToolContext) -> ToolResult:
        sku_id: str = input.get("sku_id", "")
        lookback_days: int = int(input.get("lookback_days", 90))
        z_threshold: float = float(input.get("z_threshold", 2.5))

        try:
            rows = await _fetch_demand_rows(sku_id, lookback_days)
        except Exception as exc:
            return ToolResult(
                output={"error": _connection_error_message(exc)},
                audit_payload={
                    "sku_id": sku_id,
                    "lookback_days": lookback_days,
                    "z_threshold": z_threshold,
                    "anomaly_count": 0,
                },
            )

        if len(rows) < 3:
            return ToolResult(
                output={
                    "sku_id": sku_id,
                    "anomaly_count": 0,
                    "anomalies": [],
                },
                audit_payload={
                    "sku_id": sku_id,
                    "lookback_days": lookback_days,
                    "z_threshold": z_threshold,
                    "anomaly_count": 0,
                },
            )

        non_missing_quantities = [
            float(r["quantity"])
            for r in rows
            if not r["is_missing"] and r["quantity"] is not None
        ]

        mean: float = 0.0
        std: float = 0.0
        if non_missing_quantities:
            mean = sum(non_missing_quantities) / len(non_missing_quantities)
            variance = (
                sum((q - mean) ** 2 for q in non_missing_quantities)
                / len(non_missing_quantities)
            )
            std = variance ** 0.5

        anomalies: list[dict[str, Any]] = []

        for row in rows:
            is_missing: bool = bool(row["is_missing"])
            quantity: float | None = float(row["quantity"]) if row["quantity"] is not None else None
            row_date = row["date"]
            date_str = row_date.isoformat() if hasattr(row_date, "isoformat") else str(row_date)

            if is_missing or quantity is None:
                anomalies.append({
                    "date": date_str,
                    "quantity": quantity,
                    "z_score": None,
                    "anomaly_type": "missing",
                })
                continue

            z_score: float = (quantity - mean) / std if std > 0 else 0.0

            if z_score > z_threshold:
                anomaly_type = "spike"
            elif z_score < -z_threshold:
                anomaly_type = "drop"
            elif quantity == 0:
                anomaly_type = "stockout"
            else:
                # Not anomalous — skip
                continue

            anomalies.append({
                "date": date_str,
                "quantity": quantity,
                "z_score": z_score,
                "anomaly_type": anomaly_type,
            })

        anomaly_count = len(anomalies)

        return ToolResult(
            output={
                "sku_id": sku_id,
                "anomaly_count": anomaly_count,
                "anomalies": anomalies,
            },
            audit_payload={
                "sku_id": sku_id,
                "lookback_days": lookback_days,
                "z_threshold": z_threshold,
                "anomaly_count": anomaly_count,
            },
        )


async def _fetch_demand_rows(sku_id: str, lookback_days: int) -> list[dict[str, Any]]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT date, quantity, is_missing
            FROM demand_history
            WHERE sku_id = $1
              AND date >= CURRENT_DATE - ($2 * INTERVAL '1 day')
            ORDER BY date
            """,
            sku_id,
            lookback_days,
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
