from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/v1/approvals", tags=["approvals"])

_NOT_IMPLEMENTED = JSONResponse(
    status_code=501, content={"detail": "Not implemented — Phase 1"}
)


@router.get("")
async def list_approvals() -> JSONResponse:
    return _NOT_IMPLEMENTED


@router.get("/{approval_id}")
async def get_approval(approval_id: str) -> JSONResponse:
    return _NOT_IMPLEMENTED


@router.post("/{approval_id}/decision")
async def post_decision(approval_id: str) -> JSONResponse:
    return _NOT_IMPLEMENTED
