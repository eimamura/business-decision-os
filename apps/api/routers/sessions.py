from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])

_NOT_IMPLEMENTED = JSONResponse(
    status_code=501, content={"detail": "Not implemented — Phase 1"}
)


@router.post("")
async def create_session() -> JSONResponse:
    return _NOT_IMPLEMENTED


@router.get("")
async def list_sessions() -> JSONResponse:
    return _NOT_IMPLEMENTED


@router.get("/{session_id}")
async def get_session(session_id: str) -> JSONResponse:
    return _NOT_IMPLEMENTED


@router.post("/{session_id}/messages")
async def post_message(session_id: str) -> JSONResponse:
    return _NOT_IMPLEMENTED


@router.get("/{session_id}/stream")
async def stream_session(session_id: str) -> JSONResponse:
    return _NOT_IMPLEMENTED
