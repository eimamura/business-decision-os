from __future__ import annotations

from typing import Any

from packages.optimization import OptimizationContext, OptimizationInput, ReplenishmentOptimizer
from packages.tools.base import ToolContext, ToolResult


class OptimizerTool:
    name = "optimize_replenishment"
    description = "Enumerate MOQ multiples and return top 3 candidates by total supply chain cost"
    requires_approval = False
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "sku_id": {"type": "string"},
            "moq": {"type": "number"},
            "horizon_days": {"type": "integer", "minimum": 1},
            "max_stockout_days": {"type": "integer", "minimum": 0},
        },
        "required": ["sku_id", "moq", "horizon_days"],
    }
    output_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "candidates": {"type": "array"},
        },
    }

    async def handle(self, input: dict[str, Any], ctx: ToolContext) -> ToolResult:
        sku_id = input.get("sku_id", "")
        moq = float(input.get("moq", 100.0))
        horizon_days = int(input.get("horizon_days", 90))
        max_stockout_days = int(input.get("max_stockout_days", 30))

        job_runner = getattr(ctx, "job_runner", None)

        if job_runner is not None:
            from packages.agent.runner import JobSpec
            spec = JobSpec(
                kind="optimization",
                payload={
                    "sku_id": sku_id,
                    "moq": moq,
                    "horizon_days": horizon_days,
                    "max_stockout_days": max_stockout_days,
                },
                idempotency_key=f"opt-{sku_id}-{moq}-{horizon_days}",
            )
            handle = await job_runner.submit(spec, ctx)
            result = await job_runner.result(handle.job_id, wait=True)
            candidates = result.output.get("candidates", []) if result.output else []
        else:
            opt_input = OptimizationInput(
                sku_id=sku_id,
                moq=moq,
                horizon_days=horizon_days,
                max_stockout_days=max_stockout_days,
            )
            opt_ctx = OptimizationContext(
                session_id=ctx.session_id,
                agent_step_id=ctx.agent_step_id,
                db_session=getattr(ctx, "db_session", None),
            )
            optimizer = ReplenishmentOptimizer()
            output = await optimizer.run(opt_input, opt_ctx)
            candidates = [c.model_dump() for c in output.candidates]

        return ToolResult(
            output={"candidates": candidates},
            audit_payload={
                "sku_id": sku_id,
                "moq": moq,
                "horizon_days": horizon_days,
                "candidate_count": len(candidates),
            },
        )
