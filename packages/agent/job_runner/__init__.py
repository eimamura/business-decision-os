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
        self._specs: dict[UUID, JobSpec] = {}

    async def submit(self, spec: JobSpec, ctx: ToolContext) -> JobHandle:
        handle = JobHandle(
            job_id=uuid4(),
            status="queued",
            submitted_at=datetime.now(tz=timezone.utc),
        )
        self._handles[handle.job_id] = handle
        self._specs[handle.job_id] = spec
        return handle

    async def status(self, job_id: UUID) -> JobHandle:
        handle = self._handles.get(job_id)
        if handle is None:
            raise KeyError(f"Job {job_id} not found")
        return handle

    async def result(self, job_id: UUID, wait: bool = False) -> JobResult:
        spec = self._specs.get(job_id)
        if spec is None:
            raise KeyError(f"Job {job_id} not found")

        if spec.kind == "simulation":
            return await self._run_simulation(job_id, spec)
        if spec.kind == "optimization":
            return await self._run_optimization(job_id, spec)

        raise NotImplementedError(f"InProcess does not support kind={spec.kind}")

    async def _run_simulation(self, job_id: UUID, spec: JobSpec) -> JobResult:
        from packages.simulation import InventorySimulator, SimulationContext, SimulationInput

        start = datetime.now(tz=timezone.utc)
        try:
            sim_input = SimulationInput(
                sku_id=spec.payload["sku_id"],
                order_qty=float(spec.payload["order_qty"]),
                horizon_days=int(spec.payload.get("horizon_days", 90)),
            )
            sim_ctx = SimulationContext(db_session=None)
            output = await InventorySimulator().run(sim_input, sim_ctx)
            duration_ms = int(
                (datetime.now(tz=timezone.utc) - start).total_seconds() * 1000
            )
            return JobResult(
                job_id=job_id,
                status="succeeded",
                output=output.model_dump(),
                error=None,
                duration_ms=duration_ms,
            )
        except Exception as exc:
            duration_ms = int(
                (datetime.now(tz=timezone.utc) - start).total_seconds() * 1000
            )
            return JobResult(
                job_id=job_id,
                status="failed",
                output=None,
                error=str(exc),
                duration_ms=duration_ms,
            )

    async def _run_optimization(self, job_id: UUID, spec: JobSpec) -> JobResult:
        from packages.optimization import (  # noqa: E402
            OptimizationContext,
            OptimizationInput,
            ReplenishmentOptimizer,
        )

        start = datetime.now(tz=timezone.utc)
        try:
            opt_input = OptimizationInput(
                sku_id=spec.payload["sku_id"],
                moq=float(spec.payload.get("moq", 100.0)),
                horizon_days=int(spec.payload.get("horizon_days", 90)),
                max_stockout_days=int(spec.payload.get("max_stockout_days", 30)),
            )
            opt_ctx = OptimizationContext(db_session=None)
            output = await ReplenishmentOptimizer().run(opt_input, opt_ctx)
            duration_ms = int(
                (datetime.now(tz=timezone.utc) - start).total_seconds() * 1000
            )
            return JobResult(
                job_id=job_id,
                status="succeeded",
                output=output.model_dump(),
                error=None,
                duration_ms=duration_ms,
            )
        except Exception as exc:
            duration_ms = int(
                (datetime.now(tz=timezone.utc) - start).total_seconds() * 1000
            )
            return JobResult(
                job_id=job_id,
                status="failed",
                output=None,
                error=str(exc),
                duration_ms=duration_ms,
            )

    async def cancel(self, job_id: UUID) -> None:
        raise NotImplementedError("cancel is not supported for InProcessJobRunner")


from packages.agent.job_runner.aca import AcaJobsRunner  # noqa: E402
from packages.agent.job_runner.celery_runner import CeleryJobRunner  # noqa: E402

__all__ = [
    "JobSpec",
    "JobHandle",
    "JobResult",
    "JobRunner",
    "InProcessJobRunner",
    "AcaJobsRunner",
    "CeleryJobRunner",
]
