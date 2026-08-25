from __future__ import annotations

import csv
import io
import logging
from typing import Any, Literal

from packages.optimization import OptimizationContext, OptimizationInput, ReplenishmentOptimizer
from packages.tools.base import ToolContext, ToolResult

logger = logging.getLogger(__name__)


def _build_csv(rows: list[dict[str, Any]]) -> bytes:
    """Serialize a list of flat dicts to UTF-8 CSV bytes."""
    if not rows:
        return b""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8")


def _flatten_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    """Flatten a candidate dict — stringify nested structures."""
    flat: dict[str, Any] = {}
    for k, v in candidate.items():
        if isinstance(v, (dict, list)):
            flat[k] = str(v)
        else:
            flat[k] = v
    return flat


class OptimizerTool:
    name = "optimize_replenishment"
    description = "Enumerate MOQ multiples and return top 3 candidates by total supply chain cost"
    safety_level: Literal["read_only", "write", "hitl"] = "write"
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

        runner = getattr(ctx, "runner", None)

        if runner is not None:
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
            handle = await runner.submit(spec, ctx)
            result = await runner.result(handle.job_id, wait=True)
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

        flat_rows = [_flatten_candidate(c) for c in candidates] if candidates else []
        csv_bytes = _build_csv(flat_rows)
        logger.debug(
            "OptimizerTool generated CSV: %d bytes, %d candidates for sku_id=%s",
            len(csv_bytes),
            len(candidates),
            sku_id,
        )
        return ToolResult(
            output={
                "candidates": candidates,
                "generated_files": [
                    {
                        "file_name": "optimization_plan.csv",
                        "mime_type": "text/csv",
                        "file_size_bytes": len(csv_bytes),
                        "file_content": csv_bytes,
                    }
                ],
            },
            audit_payload={
                "sku_id": sku_id,
                "moq": moq,
                "horizon_days": horizon_days,
                "candidate_count": len(candidates),
            },
        )
