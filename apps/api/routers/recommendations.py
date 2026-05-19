from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/v1", tags=["recommendations"])

_NOT_IMPLEMENTED = JSONResponse(
    status_code=501, content={"detail": "Not implemented — Phase 1"}
)


@router.get("/recommendations/{recommendation_id}")
async def get_recommendation(recommendation_id: str) -> JSONResponse:
    return _NOT_IMPLEMENTED


@router.get("/sessions/{session_id}/recommendations")
async def list_session_recommendations(session_id: str) -> JSONResponse:
    return _NOT_IMPLEMENTED
