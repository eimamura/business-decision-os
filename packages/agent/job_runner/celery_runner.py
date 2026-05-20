from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Literal
from uuid import UUID, uuid4

from packages.tools.base import ToolContext

if TYPE_CHECKING:
    from packages.agent.job_runner import JobHandle, JobResult, JobSpec


def _require_celery() -> None:
    broker = os.environ.get("CELERY_BROKER_URL", "").strip()
    if not broker:
        raise RuntimeError(
            "CELERY_BROKER_URL is not set — required when JOB_RUNNER_BACKEND=celery"
        )


_STATUS_MAP: dict[str, Literal["queued", "running", "succeeded", "failed", "cancelled"]] = {
    "PENDING": "queued",
    "RECEIVED": "queued",
    "STARTED": "running",
    "SUCCESS": "succeeded",
    "FAILURE": "failed",
    "REVOKED": "cancelled",
    "RETRY": "running",
}


class CeleryJobRunner:
    def __init__(self) -> None:
        _require_celery()
        from packages.agent.job_runner.celery_app import celery_app

        self._app = celery_app
        self._task_ids: dict[UUID, str] = {}

    async def submit(self, spec: JobSpec, ctx: ToolContext) -> JobHandle:
        from packages.agent.job_runner import JobHandle

        task_name_map = {
            "simulation": "bdos.run_simulation",
            "optimization": "bdos.run_optimization",
        }
        task_name = task_name_map.get(spec.kind)
        if task_name is None:
            raise NotImplementedError(f"CeleryJobRunner does not support kind={spec.kind}")

        job_id = uuid4()
        result = self._app.send_task(
            task_name,
            args=[spec.payload],
            task_id=str(job_id),
        )
        self._task_ids[job_id] = result.id

        return JobHandle(
            job_id=job_id,
            status="queued",
            submitted_at=datetime.now(tz=timezone.utc),
        )

    async def status(self, job_id: UUID) -> JobHandle:
        from packages.agent.job_runner import JobHandle

        task_id = self._task_ids.get(job_id, str(job_id))
        result = self._app.AsyncResult(task_id)
        celery_state = result.state
        mapped: Literal["queued", "running", "succeeded", "failed", "cancelled"] = (
            _STATUS_MAP.get(celery_state, "running")
        )
        return JobHandle(
            job_id=job_id,
            status=mapped,
            submitted_at=datetime.now(tz=timezone.utc),
        )

    async def result(self, job_id: UUID, wait: bool = False) -> JobResult:
        import asyncio

        from packages.agent.job_runner import JobResult

        task_id = self._task_ids.get(job_id, str(job_id))
        start = datetime.now(tz=timezone.utc)

        async_result = self._app.AsyncResult(task_id)
        if wait:
            while async_result.state in ("PENDING", "RECEIVED", "STARTED", "RETRY"):
                await asyncio.sleep(0.5)
                async_result = self._app.AsyncResult(task_id)

        duration_ms = int((datetime.now(tz=timezone.utc) - start).total_seconds() * 1000)
        celery_state = async_result.state

        if celery_state == "SUCCESS":
            return JobResult(
                job_id=job_id,
                status="succeeded",
                output=async_result.result,
                error=None,
                duration_ms=duration_ms,
            )
        if celery_state == "FAILURE":
            return JobResult(
                job_id=job_id,
                status="failed",
                output=None,
                error=str(async_result.result),
                duration_ms=duration_ms,
            )
        return JobResult(
            job_id=job_id,
            status="failed",
            output=None,
            error=f"Job in state {celery_state}",
            duration_ms=duration_ms,
        )

    async def cancel(self, job_id: UUID) -> None:
        task_id = self._task_ids.get(job_id, str(job_id))
        self._app.control.revoke(task_id, terminate=True)
