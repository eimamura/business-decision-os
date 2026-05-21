from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from packages.persistence.approvals import ApprovalStatus, ApprovalTransition
from packages.persistence.approvals_repo import ApprovalsRepository
from packages.persistence.notifications_repo import NotificationsRepository
from packages.tools.guardrail import can_execute

router = APIRouter(prefix="/api/v1/approvals", tags=["approvals"])

_approvals_repo = ApprovalsRepository()
_notifications_repo = NotificationsRepository()


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
    return JSONResponse(status_code=200, content=records)


@router.get("/{approval_id}")
async def get_approval(approval_id: UUID) -> JSONResponse:
    try:
        record = await _approvals_repo.get(approval_id)
    except NotImplementedError:
        raise HTTPException(status_code=404, detail="Approval not found")
    if record is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    return JSONResponse(status_code=200, content=record)


@router.post("/{approval_id}/decision")
async def post_decision(
    approval_id: UUID,
    body: DecisionBody,
    x_dev_user: str | None = Header(default=None),
) -> JSONResponse:
    if not can_execute(action="approve_recommendation", actor=x_dev_user):
        raise HTTPException(
            status_code=403, detail="Insufficient role — approver or admin required"
        )

    try:
        record = await _approvals_repo.get(approval_id)
    except NotImplementedError:
        raise HTTPException(status_code=404, detail="Approval not found")
    if record is None:
        raise HTTPException(status_code=404, detail="Approval not found")

    _valid: set[str] = {"pending", "approved", "rejected", "needs_revision", "expired"}
    raw_status = record.get("status", "pending") if isinstance(record, dict) else "pending"
    current_status: ApprovalStatus = raw_status if raw_status in _valid else "pending"  # type: ignore[assignment]
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
    return JSONResponse(status_code=200, content=updated)


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

    return JSONResponse(status_code=201, content=created)


