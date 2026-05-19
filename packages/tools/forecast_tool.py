from __future__ import annotations

from typing import Any

from packages.tools.base import ToolContext, ToolResult

_MODEL_VERSION = "moving_avg_v1"


class ForecastTool:
    name = "forecast"
    description = "Forecast future demand for a SKU using a 28-day moving average"
    requires_approval = False
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "sku_id": {"type": "string"},
            "horizon_days": {"type": "integer", "minimum": 1},
        },
        "required": ["sku_id", "horizon_days"],
    }
    output_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "sku_id": {"type": "string"},
            "forecast_units": {"type": "array", "items": {"type": "number"}},
            "model_version": {"type": "string"},
            "nulls_skipped": {"type": "integer"},
        },
    }

    def __init__(self, db_session: Any | None = None) -> None:
        self._db_session = db_session

    async def handle(self, input: dict[str, Any], ctx: ToolContext) -> ToolResult:
        sku_id: str = input.get("sku_id", "")
        horizon_days: int = int(input.get("horizon_days", 28))

        if self._db_session is not None:
            return await self._handle_with_db(sku_id, horizon_days)

        return ToolResult(
            output={
                "sku_id": sku_id,
                "forecast_units": [10.0] * horizon_days,
                "model_version": _MODEL_VERSION,
                "nulls_skipped": 0,
            },
            audit_payload={
                "sku_id": sku_id,
                "horizon_days": horizon_days,
                "model_version": _MODEL_VERSION,
            },
        )

    async def _handle_with_db(self, sku_id: str, horizon_days: int) -> ToolResult:
        from sqlalchemy import text

        assert self._db_session is not None
        sql = text(
            "SELECT units FROM demand_history "
            "WHERE sku = :sku AND units IS NOT NULL "
            "ORDER BY date DESC LIMIT 28"
        )
        result = await self._db_session.execute(sql, {"sku": sku_id})
        rows = result.fetchall()
        nulls_skipped = 28 - len(rows)

        if rows:
            values = [float(row[0]) for row in rows]
            avg = sum(values) / len(values)
        else:
            avg = 10.0

        return ToolResult(
            output={
                "sku_id": sku_id,
                "forecast_units": [round(avg, 2)] * horizon_days,
                "model_version": _MODEL_VERSION,
                "nulls_skipped": max(0, nulls_skipped),
            },
            audit_payload={
                "sku_id": sku_id,
                "horizon_days": horizon_days,
                "model_version": _MODEL_VERSION,
            },
        )
