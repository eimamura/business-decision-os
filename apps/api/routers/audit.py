from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])

_NOT_IMPLEMENTED = JSONResponse(
    status_code=501, content={"detail": "Not implemented — Phase 1"}
)


@router.get("")
async def list_audit() -> JSONResponse:
    return _NOT_IMPLEMENTED
