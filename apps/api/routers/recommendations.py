from __future__ import annotations

from typing import Any

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1", tags=["recommendations"])


@router.get("/recommendations/{recommendation_id}")
async def get_recommendation(recommendation_id: str) -> dict[str, Any]:
    return {
        "recommendation_id": recommendation_id,
        "status": "stub",
        "primary": None,
        "alternatives": [],
    }


@router.get("/sessions/{session_id}/recommendations")
async def list_session_recommendations(session_id: str) -> list[dict[str, Any]]:
    return []
