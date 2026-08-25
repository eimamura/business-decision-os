from __future__ import annotations

import csv
import io
import logging
from typing import Any, Literal

from packages.tools.base import ToolContext, ToolResult

logger = logging.getLogger(__name__)


def _build_forecast_csv(
    sku_id: str,
    forecast_units: list[Any],
    model_version: str,
    source: str,
) -> bytes:
    """Build a per-day CSV from a forecast_units list."""
    if not forecast_units:
        return b""
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf, fieldnames=["sku_id", "day", "forecast_units", "model_version", "source"]
    )
    writer.writeheader()
    for i, units in enumerate(forecast_units):
        writer.writerow({
            "sku_id": sku_id,
            "day": i + 1,
            "forecast_units": units,
            "model_version": model_version,
            "source": source,
        })
    return buf.getvalue().encode("utf-8")


class ForecastTool:
    name = "forecast"
    description = "Forecast future demand for a SKU using a 28-day moving average"
    safety_level: Literal["read_only", "write", "hitl"] = "write"
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
        csv_bytes = _build_forecast_csv(
            sku_id=sku_id,
            forecast_units=result.predicted_units,
            model_version=result.model_version,
            source=result.source,
        )
        logger.debug(
            "ForecastTool generated CSV: %d bytes for sku_id=%s",
            len(csv_bytes),
            sku_id,
        )
        return ToolResult(
            output={
                "sku_id": sku_id,
                "forecast_units": result.predicted_units,
                "model_version": result.model_version,
                "nulls_skipped": 0,
                "prediction": result.predicted_units[0] if result.predicted_units else None,
                "source": result.source,
                "generated_files": [
                    {
                        "file_name": "forecast_result.csv",
                        "mime_type": "text/csv",
                        "file_size_bytes": len(csv_bytes),
                        "file_content": csv_bytes,
                    }
                ],
            },
            audit_payload={
                "sku_id": sku_id,
                "horizon_days": horizon_days,
                "model_version": result.model_version,
                "source": result.source,
            },
        )
