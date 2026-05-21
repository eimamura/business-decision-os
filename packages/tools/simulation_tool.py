from __future__ import annotations

from typing import Any

from packages.tools.base import ToolContext, ToolResult


class SimulationTool:
    name = "simulate_inventory"
    description = "Run a deterministic inventory simulation for a SKU and order quantity"
    requires_approval = False
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "sku_id": {"type": "string"},
            "order_qty": {"type": "number"},
            "horizon_days": {"type": "integer", "minimum": 1},
        },
        "required": ["sku_id", "order_qty", "horizon_days"],
    }
    output_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "sku_id": {"type": "string"},
            "ending_on_hand": {"type": "number"},
            "stockout_days": {"type": "integer"},
            "mean_lead_time_days": {"type": "integer"},
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
        order_qty: float = float(input.get("order_qty", 0.0))
        horizon_days: int = int(input.get("horizon_days", 90))

        spec = JobSpec(
            kind="simulation",
            payload={
                "sku_id": sku_id,
                "order_qty": order_qty,
                "horizon_days": horizon_days,
            },
            idempotency_key=str(ctx.agent_step_id),
        )
        handle = await self._runner.submit(spec, ctx)
        job_result = await self._runner.result(handle.job_id, wait=True)

        if job_result.status != "succeeded" or job_result.output is None:
            raise RuntimeError(
                f"Simulation job failed: {job_result.error}"
            )

        output = job_result.output
        return ToolResult(
            output={
                "sku_id": output.get("sku_id", sku_id),
                "ending_on_hand": output.get("ending_on_hand", 0.0),
                "stockout_days": output.get("stockout_days", 0),
                "mean_lead_time_days": output.get("mean_lead_time_days", 14),
            },
            audit_payload={
                "sku_id": sku_id,
                "order_qty": order_qty,
                "horizon_days": horizon_days,
            },
        )
