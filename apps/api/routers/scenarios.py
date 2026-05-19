from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/v1", tags=["scenarios"])

_NOT_IMPLEMENTED = JSONResponse(
    status_code=501, content={"detail": "Not implemented — Phase 1"}
)


@router.get("/sessions/{session_id}/scenarios")
async def list_session_scenarios(session_id: str) -> JSONResponse:
    return _NOT_IMPLEMENTED


@router.get("/scenarios/{scenario_id}")
async def get_scenario(scenario_id: str) -> JSONResponse:
    return _NOT_IMPLEMENTED
