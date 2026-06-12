from __future__ import annotations

import datetime
from typing import Any

from fastapi import APIRouter
from fastapi import status as http_status
from pydantic import BaseModel, ConfigDict

from apps.api.screening import run_screening
from packages.persistence.screening_runs_repo import ScreeningRunsRepository

router = APIRouter(prefix="/api/v1/screenings", tags=["screenings"])


class ScreeningRunOut(BaseModel):
    """Pydantic v2 response model for a single screening run row."""

    model_config = ConfigDict(from_attributes=True)

    id: str | None
    run_date: str
    triggered_by: str
    status: str
    exception_count: int | None
    severity_counts: dict[str, Any] | None
    payload: dict[str, Any] | None
    error: str | None
    created_at: str


class TodayResponse(BaseModel):
    """Response shape for GET /today — run is None when no run exists yet."""

    model_config = ConfigDict()

    run: ScreeningRunOut | None


class RunResponse(BaseModel):
    """Response shape for POST /run."""

    model_config = ConfigDict()

    run: ScreeningRunOut


_repo = ScreeningRunsRepository()


@router.get(
    "/today",
    response_model=TodayResponse,
    status_code=http_status.HTTP_200_OK,
)
async def get_today_screening() -> TodayResponse:
    """Return the latest screening run for today UTC.

    Always returns HTTP 200.  ``run`` is ``null`` when no run has been
    persisted yet for today.
    """
    today = datetime.date.today()
    row = await _repo.latest_for_date(today)
    if row is None:
        return TodayResponse(run=None)
    return TodayResponse(run=ScreeningRunOut(**row))


@router.post(
    "/run",
    response_model=RunResponse,
    status_code=http_status.HTTP_201_CREATED,
)
async def trigger_screening_run() -> RunResponse:
    """Execute a manual screening run immediately and return the created run."""
    row = await run_screening(triggered_by="manual")
    return RunResponse(run=ScreeningRunOut(**row))
