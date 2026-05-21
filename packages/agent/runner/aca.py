from __future__ import annotations

import os
from typing import TYPE_CHECKING, Literal, cast
from uuid import UUID

from packages.tools.base import ToolContext

if TYPE_CHECKING:
    from packages.agent.runner import JobHandle, JobResult, JobSpec


class AcaJobsRunner:
    def __init__(self) -> None:
        self._resource_id = os.environ.get("ACA_SIMULATION_JOB_RESOURCE_ID", "").strip()
        if not self._resource_id:
            raise RuntimeError(
                "ACA_SIMULATION_JOB_RESOURCE_ID is not set — required when JOB_RUNNER_BACKEND=aca"
            )

    async def submit(self, spec: JobSpec, ctx: ToolContext) -> JobHandle:
        return await self._aca_submit(spec, ctx)

    async def status(self, job_id: UUID) -> JobHandle:
        return await self._aca_status(job_id)

    async def result(self, job_id: UUID, wait: bool = False) -> JobResult:
        return await self._aca_result(job_id, wait=wait)

    async def cancel(self, job_id: UUID) -> None:
        await self._aca_cancel(job_id)

    async def _aca_submit(self, spec: JobSpec, ctx: ToolContext) -> JobHandle:
        import uuid
        from datetime import datetime, timezone

        import httpx

        from packages.agent.runner import JobHandle

        job_run_id = str(uuid.uuid4())
        arm_url = (
            f"https://management.azure.com{self._resource_id}"
            f"/start?api-version=2024-03-01"
        )
        token = os.environ.get("AZURE_ARM_TOKEN", "")
        body = {
            "properties": {
                "template": {
                    "containers": [
                        {
                            "env": [
                                {"name": "JOB_RUN_ID", "value": job_run_id},
                                {"name": "JOB_PAYLOAD", "value": spec.model_dump_json()},
                            ]
                        }
                    ]
                }
            }
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                arm_url,
                json=body,
                headers={"Authorization": f"Bearer {token}"},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()

        execution_name = data.get("name", job_run_id)
        handle_id = uuid.UUID(job_run_id) if len(job_run_id) == 36 else uuid.uuid4()
        self._execution_map = getattr(self, "_execution_map", {})
        self._execution_map[handle_id] = execution_name

        return JobHandle(
            job_id=handle_id,
            status="queued",
            submitted_at=datetime.now(tz=timezone.utc),
        )

    async def _aca_status(self, job_id: UUID) -> JobHandle:
        from packages.agent.runner import JobHandle

        execution_name = getattr(self, "_execution_map", {}).get(job_id, str(job_id))
        arm_url = (
            f"https://management.azure.com{self._resource_id}"
            f"/executions/{execution_name}?api-version=2024-03-01"
        )
        token = os.environ.get("AZURE_ARM_TOKEN", "")

        import httpx

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                arm_url,
                headers={"Authorization": f"Bearer {token}"},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()

        arm_status = data.get("properties", {}).get("status", "Running")
        status_map: dict[str, Literal["queued", "running", "succeeded", "failed", "cancelled"]] = {
            "Succeeded": "succeeded",
            "Failed": "failed",
            "Running": "running",
            "Pending": "queued",
        }
        from datetime import datetime, timezone

        mapped_status: Literal[
            "queued", "running", "succeeded", "failed", "cancelled"
        ] = status_map.get(arm_status, "running")
        return JobHandle(
            job_id=job_id,
            status=mapped_status,
            submitted_at=datetime.now(tz=timezone.utc),
        )

    async def _aca_result(self, job_id: UUID, wait: bool = False) -> JobResult:
        import asyncio
        from datetime import datetime, timezone

        from packages.agent.runner import JobResult

        start = datetime.now(tz=timezone.utc)
        while True:
            handle = await self._aca_status(job_id)
            if handle.status in ("succeeded", "failed", "cancelled"):
                break
            if not wait:
                break
            await asyncio.sleep(2)

        duration_ms = int(
            (datetime.now(tz=timezone.utc) - start).total_seconds() * 1000
        )
        terminal_statuses = ("succeeded", "failed", "cancelled")
        result_status = cast(
            Literal["succeeded", "failed", "cancelled"],
            handle.status if handle.status in terminal_statuses else "failed",
        )
        return JobResult(
            job_id=job_id,
            status=result_status,
            output=None,
            error=None if handle.status == "succeeded" else "ACA job did not succeed",
            duration_ms=duration_ms,
        )

    async def _aca_cancel(self, job_id: UUID) -> None:
        raise NotImplementedError("ACA job cancellation not implemented in Phase 2")
