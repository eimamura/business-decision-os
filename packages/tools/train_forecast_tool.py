from __future__ import annotations

from typing import Any, Literal

from packages.tools.base import ToolContext, ToolResult


class TrainForecastTool:
    name = "train_forecast"
    description = (
        "Train the demand forecasting model for a SKU. "
        "Reads demand_history, fits a linear regression model, "
        "and writes predictions to prediction_features."
    )
    requires_approval = False
    safety_level: Literal["read_only", "write", "hitl"] = "write"
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "sku_id": {"type": "string"},
        },
        "required": ["sku_id"],
    }
    output_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "sku_id": {"type": "string"},
            "model_version": {"type": "string"},
            "horizon_days": {"type": "integer"},
        },
    }

    def __init__(self, runner: Any | None = None) -> None:
        if runner is not None:
            self._runner = runner
        else:
            from packages.agent.runner import InProcessJobRunner
            self._runner = InProcessJobRunner()

    async def handle(self, input: dict[str, Any], ctx: ToolContext) -> ToolResult:
        from packages.agent.runner import JobSpec

        sku_id: str = input.get("sku_id", "")

        spec = JobSpec(
            kind="train_forecast",
            payload={"sku_id": sku_id},
            idempotency_key=str(ctx.agent_step_id),
        )
        handle = await self._runner.submit(spec, ctx)
        job_result = await self._runner.result(handle.job_id, wait=True)

        if job_result.status != "succeeded" or job_result.output is None:
            raise RuntimeError(f"train_forecast job failed: {job_result.error}")

        output = job_result.output
        return ToolResult(
            output={
                "sku_id": output.get("sku_id", sku_id),
                "model_version": output.get("model_version", ""),
                "horizon_days": output.get("horizon_days", 90),
            },
            audit_payload={"sku_id": sku_id},
        )
