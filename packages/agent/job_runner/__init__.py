from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel

from packages.tools.base import ToolContext


class JobSpec(BaseModel):
    kind: Literal["simulation", "optimization", "forecast_batch", "report"]
    payload: dict[str, Any]
    idempotency_key: str
    timeout_seconds: int = 300


class JobHandle(BaseModel):
    job_id: UUID
    status: Literal["queued", "running", "succeeded", "failed", "cancelled"]
    submitted_at: datetime


class JobResult(BaseModel):
    job_id: UUID
    status: Literal["succeeded", "failed", "cancelled"]
    output: dict[str, Any] | None
    error: str | None
    duration_ms: int


class JobRunner(Protocol):
    async def submit(self, spec: JobSpec, ctx: ToolContext) -> JobHandle: ...
    async def status(self, job_id: UUID) -> JobHandle: ...
    async def result(self, job_id: UUID, wait: bool = False) -> JobResult: ...
    async def cancel(self, job_id: UUID) -> None: ...


class InProcessJobRunner:
    def __init__(self) -> None:
        self._handles: dict[UUID, JobHandle] = {}

    async def submit(self, spec: JobSpec, ctx: ToolContext) -> JobHandle:
        handle = JobHandle(
            job_id=uuid4(),
            status="queued",
            submitted_at=datetime.now(tz=timezone.utc),
        )
        self._handles[handle.job_id] = handle
        return handle

    async def status(self, job_id: UUID) -> JobHandle:
        handle = self._handles.get(job_id)
        if handle is None:
            raise KeyError(f"Job {job_id} not found")
        return handle

    async def result(self, job_id: UUID, wait: bool = False) -> JobResult:
        raise NotImplementedError("Phase 2")

    async def cancel(self, job_id: UUID) -> None:
        raise NotImplementedError("Phase 2")
