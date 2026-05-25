from __future__ import annotations

from typing import Any

from packages.tools.base import ToolContext, ToolResult


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
            "prediction": {"type": ["number", "null"]},
            "source": {"type": "string"},
        },
    }

    def __init__(self, predictor: Any) -> None:
        if predictor is None:
            raise RuntimeError(
                "ForecastTool requires a predictor — inject one via __init__"
            )
        self._predictor = predictor

    async def handle(self, input: dict[str, Any], ctx: ToolContext) -> ToolResult:
        sku_id: str = input.get("sku_id", "")
        horizon_days: int = int(input.get("horizon_days", 28))

        result = await self._predictor.predict(sku_id, horizon_days)
        return ToolResult(
            output={
                "sku_id": sku_id,
                "forecast_units": result.predicted_units,
                "model_version": result.model_version,
                "nulls_skipped": 0,
                "prediction": result.predicted_units[0] if result.predicted_units else None,
                "source": result.source,
            },
            audit_payload={
                "sku_id": sku_id,
                "horizon_days": horizon_days,
                "model_version": result.model_version,
                "source": result.source,
            },
        )
