from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/v1/kpi", tags=["kpi"])

_NOT_IMPLEMENTED = JSONResponse(
    status_code=501, content={"detail": "Not implemented — Phase 1"}
)


@router.get("/trends")
async def kpi_trends() -> JSONResponse:
    return _NOT_IMPLEMENTED


@router.get("/llm-cost")
async def llm_cost() -> JSONResponse:
    return _NOT_IMPLEMENTED
