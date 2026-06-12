"""Unit tests for the screenings router (T-575 router tier).

Tests:
  - GET /api/v1/screenings/today → 200 with run when a row exists
  - GET /api/v1/screenings/today → 200 with {"run": null} when no row for today
  - POST /api/v1/screenings/run → 201 with the created run

All DB and service calls are replaced with mocks (zero-network rule).
"""
from __future__ import annotations

import datetime
import uuid
from unittest.mock import AsyncMock, patch

from httpx import ASGITransport, AsyncClient

from apps.api.main import app

_RUN_DATE = "2026-06-12"
_CREATED_AT = "2026-06-12T06:00:00+00:00"


def _make_run_row(
    status: str = "completed",
    exception_count: int = 5,
    triggered_by: str = "startup",
) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "run_date": _RUN_DATE,
        "triggered_by": triggered_by,
        "status": status,
        "exception_count": exception_count,
        "severity_counts": {"critical": 2, "high": 3},
        "payload": {"exceptions": [], "counts": {}, "truncated": False, "missing_data": []},
        "error": None,
        "created_at": _CREATED_AT,
    }


async def test_get_today_returns_200_with_run_when_exists() -> None:
    """GET /today returns 200 with the run row when one exists for today."""
    row = _make_run_row()
    mock_repo = AsyncMock()
    mock_repo.latest_for_date = AsyncMock(return_value=row)

    with patch(
        "apps.api.routers.screenings._repo",
        mock_repo,
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/screenings/today")

    assert resp.status_code == 200
    data = resp.json()
    assert data["run"]["status"] == "completed"
    assert data["run"]["exception_count"] == 5
    assert data["run"]["severity_counts"] == {"critical": 2, "high": 3}


async def test_get_today_returns_200_null_when_no_row() -> None:
    """GET /today returns 200 with {\"run\": null} when no row exists for today."""
    mock_repo = AsyncMock()
    mock_repo.latest_for_date = AsyncMock(return_value=None)

    with patch(
        "apps.api.routers.screenings._repo",
        mock_repo,
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/screenings/today")

    assert resp.status_code == 200
    data = resp.json()
    assert data["run"] is None


async def test_post_run_returns_201_with_created_row() -> None:
    """POST /run returns 201 with the created screening run."""
    row = _make_run_row(triggered_by="manual")

    with patch("apps.api.routers.screenings.run_screening", AsyncMock(return_value=row)):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post("/api/v1/screenings/run")

    assert resp.status_code == 201
    data = resp.json()
    assert data["run"]["triggered_by"] == "manual"
    assert data["run"]["status"] == "completed"
    assert data["run"]["exception_count"] == 5


async def test_post_run_calls_run_screening_with_manual() -> None:
    """POST /run passes triggered_by='manual' to run_screening."""
    row = _make_run_row(triggered_by="manual")
    mock_run = AsyncMock(return_value=row)

    with patch("apps.api.routers.screenings.run_screening", mock_run):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            await client.post("/api/v1/screenings/run")

    mock_run.assert_called_once_with(triggered_by="manual")
