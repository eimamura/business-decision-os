from __future__ import annotations

from typing import Any, Literal

from packages.tools.base import ToolContext, ToolResult


class JobDispatchTool:
    name = "job_dispatch"
    description = (
        "Dispatch a job for execution. The job will be paused for human approval "
        "before running. Supported job_types: simulate, inventory_simulation, optimize, forecast, train_forecast."
    )
    safety_level: Literal["read_only", "write", "hitl"] = "hitl"
    input_schema: dict[str, Any] = {  # Any: JSON schema values are untyped
        "type": "object",
        "properties": {
            "job_type": {
                "type": "string",
                "enum": ["simulate", "inventory_simulation", "optimize", "forecast", "train_forecast"],
                "description": "The type of computation to run.",
            },
            "params": {
                "type": "object",
                "description": "Input parameters forwarded to the job executor.",
            },
            "description": {
                "type": "string",
                "description": "Human-readable summary shown in the approval card.",
            },
        },
        "required": ["job_type", "params", "description"],
    }
    output_schema: dict[str, Any] = {  # Any: JSON schema values are untyped
        "type": "object",
        "properties": {
            "job_id": {"type": "string"},
            "approval_id": {"type": "string"},
            "status": {"type": "string"},
            "description": {"type": "string"},
        },
    }

    async def handle(self, input: dict[str, Any], ctx: ToolContext) -> ToolResult:
        # AgentRuntime intercepts safety_level="hitl" BEFORE calling handle().
        # This method is only reached in unit tests that call handle() directly.
        from packages.persistence.jobs_repo import JobsRepository

        repo = JobsRepository()
        job = await repo.create(
            session_id=ctx.session_id,
            job_type=input["job_type"],
            params=input.get("params", {}),
        )
        job_id = str(job["id"])
        return ToolResult(
            output={
                "job_id": job_id,
                "approval_id": None,
                "status": "pending_approval",
                "description": input.get("description", ""),
            },
            audit_payload={
                "job_id": job_id,
                "job_type": input["job_type"],
                "description": input.get("description", ""),
            },
        )
