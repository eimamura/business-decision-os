from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])

_NOT_IMPLEMENTED = JSONResponse(
    status_code=501, content={"detail": "Not implemented — Phase 1"}
)


@router.get("/weights")
async def get_weights() -> JSONResponse:
    return _NOT_IMPLEMENTED


@router.patch("/weights")
async def patch_weights() -> JSONResponse:
    return _NOT_IMPLEMENTED


@router.get("/budgets")
async def get_budgets() -> JSONResponse:
    return _NOT_IMPLEMENTED


@router.patch("/budgets")
async def patch_budgets() -> JSONResponse:
    return _NOT_IMPLEMENTED
