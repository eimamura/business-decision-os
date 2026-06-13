from __future__ import annotations

import asyncio
import logging
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from apps.api.state import get_orchestrator
from packages.agent.orchestrator import SessionOrchestrator
from packages.agent.orchestrator.session_orchestrator import NoPendingInterruptError
from packages.persistence.approvals import ApprovalStatus, ApprovalTransition
from packages.persistence.approvals_repo import ApprovalsRepository
from packages.persistence.notifications_repo import NotificationsRepository

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/approvals", tags=["approvals"])

_approvals_repo = ApprovalsRepository()
_notifications_repo = NotificationsRepository()


async def _resume_with_logging(
    orchestrator: SessionOrchestrator,
    session_id: UUID,
    approval_id: UUID,
) -> None:
    """Thin wrapper around ``orchestrator.resume`` that logs typed errors cleanly.

    ``NoPendingInterruptError`` means the LangGraph checkpoint is absent or already
    consumed; log at WARNING (not as an unhandled exception) so it does not produce
    a misleading 500 traceback in the approval response path.
    All other exceptions are logged at ERROR level and re-raised so callers see them.
    """
    try:
        await orchestrator.resume(session_id, approval_id)
    except NoPendingInterruptError as exc:
        _log.warning(
            "approval resume found no pending interrupt for session %s — "
            "checkpoint may have been lost on a server restart: %s",
            session_id,
            exc,
        )
    except Exception as exc:
        _log.error(
            "approval resume failed for session %s approval %s: %s",
            session_id,
            approval_id,
            exc,
        )
        raise


def get_orchestrator_dep() -> SessionOrchestrator:
    """Dependency that returns a SessionOrchestrator for HITL resume operations.

    No SSE broadcaster is injected — the orchestrator uses the persisted
    LangGraph checkpoint state to resume the graph from the interrupt point.
    """
    return get_orchestrator(sse_queue=None)


class DecisionBody(BaseModel):
    decision: Literal["approved", "rejected", "needs_revision"]
    reason: str | None = None
    weight_override: dict[str, Any] | None = None


class CreateApprovalBody(BaseModel):
    session_id: UUID
    recommendation_id: UUID | None = None
    reason: str | None = None


@router.get("")
async def list_approvals(status: str = Query(default="pending")) -> JSONResponse:
    try:
        records = await _approvals_repo.list(status=status)
    except NotImplementedError:
        return JSONResponse(status_code=200, content=[])
    return JSONResponse(status_code=200, content=jsonable_encoder(records))


@router.get("/{approval_id}")
async def get_approval(approval_id: UUID) -> JSONResponse:
    try:
        record = await _approvals_repo.get(approval_id)
    except NotImplementedError:
        raise HTTPException(status_code=404, detail="Approval not found")
    if record is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    return JSONResponse(status_code=200, content=jsonable_encoder(record))


@router.post("/{approval_id}/decision")
async def post_decision(
    approval_id: UUID,
    body: DecisionBody,
    x_dev_user: str | None = Header(default=None),
    orchestrator: SessionOrchestrator = Depends(get_orchestrator_dep),
) -> JSONResponse:
    try:
        record = await _approvals_repo.get(approval_id)
    except NotImplementedError:
        raise HTTPException(status_code=404, detail="Approval not found")
    if record is None:
        raise HTTPException(status_code=404, detail="Approval not found")

    _valid: set[str] = {"pending", "approved", "rejected", "needs_revision", "expired"}
    raw_status = record.get("status", "pending") if isinstance(record, dict) else "pending"
    current_status: ApprovalStatus = raw_status if raw_status in _valid else "pending"
    try:
        ApprovalTransition(from_status=current_status, to_status=body.decision)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    try:
        updated = await _approvals_repo.update(
            approval_id,
            status=body.decision,
            reason=body.reason,
            weight_override_json=body.weight_override,
            actor=x_dev_user,
        )
    except NotImplementedError:
        return JSONResponse(
            status_code=200,
            content={"approval_id": str(approval_id), "status": body.decision},
        )

    if body.decision == "approved" and isinstance(updated, dict):
        session_id_str = str(updated.get("session_id", ""))
        if session_id_str:
            try:
                from packages.persistence.sessions_repo import DecisionSessionRepository
                await DecisionSessionRepository().update_status(session_id_str, "completed")
            except Exception:
                pass  # non-blocking: session status is best-effort here

        # Dispatch the linked job directly instead of resuming LangGraph.
        # LangGraph resume re-creates the specialist from scratch (MemorySaver is
        # ephemeral per call), causing the LLM to re-request HITL approval and
        # triggering a second interrupt() → RuntimeError("Graph resume produced no result").
        _job_dispatched = False
        if session_id_str:
            try:
                from apps.api.state import broadcasters as _broadcasters
                from packages.agent.job_executor import execute_job as _execute_job
                from packages.persistence.jobs_repo import JobsRepository as _JobsRepo

                _jr = _JobsRepo()
                _linked_job = await _jr.get_by_approval_id(approval_id)
                if _linked_job is not None:
                    _job_id_val = _linked_job.get("id")
                    if _job_id_val is not None:
                        _job_uuid = (
                            _job_id_val
                            if isinstance(_job_id_val, UUID)
                            else UUID(_job_id_val)
                        )
                        # Transition to queued before background dispatch so UI shows the
                        # intermediate state (pending_approval → queued → running → completed).
                        await _jr.update_status(_job_uuid, "queued")
                        asyncio.create_task(
                            _execute_job(
                                _job_uuid,
                                sse_queue=_broadcasters.get(session_id_str),
                            ),
                            name=f"execute_job_{_job_id_val}",
                        )
                        _job_dispatched = True
            except Exception as exc:
                _log.warning("job dispatch failed for approval %s: %s", approval_id, exc)

        # Fallback: resume LangGraph only when no linked job exists (e.g. manually
        # created approvals without a job record).
        if not _job_dispatched and session_id_str:
            try:
                asyncio.create_task(
                    _resume_with_logging(orchestrator, UUID(session_id_str), approval_id)
                )
            except Exception:
                pass  # non-blocking

    elif body.decision == "needs_revision" and isinstance(updated, dict):
        session_id_str = str(updated.get("session_id", ""))
        # Cancel linked job — needs_revision is a terminal approval state;
        # the user must submit a new request after addressing the revision feedback.
        try:
            from packages.persistence.jobs_repo import JobsRepository as _JobsRepo
            _jr = _JobsRepo()
            _job = await _jr.get_by_approval_id(approval_id)
            if _job is not None:
                _job_id_val = _job.get("id")
                if _job_id_val is not None:
                    await _jr.update_status(
                        UUID(_job_id_val) if not isinstance(_job_id_val, UUID) else _job_id_val,
                        "cancelled",
                    )
        except Exception:
            pass  # non-blocking
        if session_id_str:
            try:
                from packages.persistence.sessions_repo import DecisionSessionRepository
                await DecisionSessionRepository().update_status(session_id_str, "failed")
            except Exception:
                pass

    elif body.decision == "rejected" and isinstance(updated, dict):
        session_id_str = str(updated.get("session_id", ""))
        if session_id_str:
            try:
                from packages.persistence.sessions_repo import DecisionSessionRepository
                await DecisionSessionRepository().update_status(session_id_str, "failed")
            except Exception:
                pass

        # Cancel linked job if this approval is rejected
        try:
            from packages.persistence.jobs_repo import JobsRepository as _JobsRepo
            _jr = _JobsRepo()
            _job = await _jr.get_by_approval_id(approval_id)
            if _job is not None:
                _job_id_val = _job.get("id")
                if _job_id_val is not None:
                    await _jr.update_status(
                        UUID(_job_id_val) if not isinstance(_job_id_val, UUID) else _job_id_val,
                        "cancelled",
                    )
        except Exception:
            pass  # non-blocking: job cancellation failure must not fail the approval response

    return JSONResponse(status_code=200, content=jsonable_encoder(updated))


@router.post("")
async def create_approval(
    body: CreateApprovalBody,
    x_dev_user: str | None = Header(default=None),
) -> JSONResponse:
    record: dict[str, Any] = {
        "session_id": str(body.session_id),
        "recommendation_id": str(body.recommendation_id) if body.recommendation_id else None,
        "status": "pending",
        "reason": body.reason,
        "actor": x_dev_user,
    }
    try:
        created = await _approvals_repo.create(record)
    except NotImplementedError:
        return JSONResponse(status_code=201, content=record)

    approval_id_val = created.get("id") if isinstance(created, dict) else None
    try:
        await _notifications_repo.create({
            "approval_id": approval_id_val,
            "type": "approval_pending",
        })
    except NotImplementedError:
        pass

    return JSONResponse(status_code=201, content=jsonable_encoder(created))


