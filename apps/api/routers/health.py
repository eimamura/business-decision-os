from __future__ import annotations

import os

from fastapi import APIRouter
from fastapi import status as http_status
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class AppStatus(BaseModel):
    mock_mode: bool
    version: str
    environment: str


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
async def readyz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/api/v1/status", response_model=AppStatus, status_code=http_status.HTTP_200_OK)
async def get_status() -> AppStatus:
    return AppStatus(
        mock_mode=os.environ.get("MOCK_LLM", "").lower() == "true",
        version="0.1.0",
        environment=os.environ.get("ENV", "production"),
    )
