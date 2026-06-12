"""Unit tests for apps/api/screening.py — T-575 (unit tier).

Coverage:
  - run_screening: counts derivation, completed-row persistence
  - run_screening: failed-row persistence when tool raises
  - _seconds_until_next_hour_utc: next-run computation with frozen clock
  - _scheduler_enabled: disabled flag via env var
  - _screening_hour: default and custom parsing

Zero-network rule: asyncpg pool and the tool handle() are both mocked.
"""
from __future__ import annotations

import datetime
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tool_result(exceptions: list[dict]) -> MagicMock:  # type: ignore[type-arg]
    from packages.tools.base import ToolResult
    return ToolResult(
        output={
            "exceptions": exceptions,
            "counts": {},
            "truncated": False,
            "missing_data": [],
        },
        audit_payload={},
    )


def _stub_repo_create(
    run_date: datetime.date = datetime.date(2026, 6, 12),
    triggered_by: str = "manual",
    status: str = "completed",
    exception_count: int | None = 0,
    severity_counts: dict | None = None,
    payload: dict | None = None,
    error: str | None = None,
) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "run_date": run_date.isoformat(),
        "triggered_by": triggered_by,
        "status": status,
        "exception_count": exception_count,
        "severity_counts": severity_counts or {},
        "payload": payload or {},
        "error": error,
        "created_at": "2026-06-12T06:00:00+00:00",
    }


# ---------------------------------------------------------------------------
# run_screening: successful path
# ---------------------------------------------------------------------------

async def test_run_screening_completed_row_persisted_with_counts() -> None:
    """run_screening persists a completed row with correct exception_count and severity_counts."""
    exceptions = [
        {"domain": "stockout_risk", "severity": "critical", "headline_metric": "x", "detail": "d"},
        {"domain": "stockout_risk", "severity": "critical", "headline_metric": "x", "detail": "d"},
        {"domain": "supply_delays", "severity": "high", "headline_metric": "x", "detail": "d"},
    ]
    tool_result = _make_tool_result(exceptions)
    expected_row = _stub_repo_create(
        status="completed",
        exception_count=3,
        severity_counts={"critical": 2, "high": 1},
    )

    mock_tool = AsyncMock()
    mock_tool.handle = AsyncMock(return_value=tool_result)
    mock_repo = AsyncMock()
    mock_repo.create = AsyncMock(return_value=expected_row)

    with (
        patch("apps.api.screening.ListTodayExceptionsTool", return_value=mock_tool),
        patch("apps.api.screening.ScreeningRunsRepository", return_value=mock_repo),
    ):
        from apps.api.screening import run_screening
        row = await run_screening(triggered_by="manual")

    assert row["status"] == "completed"
    assert row["exception_count"] == 3
    assert row["severity_counts"] == {"critical": 2, "high": 1}

    # Verify the repo was called with correct arguments
    call_kwargs = mock_repo.create.call_args.kwargs
    assert call_kwargs["status"] == "completed"
    assert call_kwargs["exception_count"] == 3
    assert call_kwargs["severity_counts"] == {"critical": 2, "high": 1}
    assert call_kwargs["triggered_by"] == "manual"


async def test_run_screening_empty_exceptions_zero_count() -> None:
    """run_screening with no exceptions → exception_count=0, severity_counts={}."""
    tool_result = _make_tool_result([])
    expected_row = _stub_repo_create(status="completed", exception_count=0, severity_counts={})

    mock_tool = AsyncMock()
    mock_tool.handle = AsyncMock(return_value=tool_result)
    mock_repo = AsyncMock()
    mock_repo.create = AsyncMock(return_value=expected_row)

    with (
        patch("apps.api.screening.ListTodayExceptionsTool", return_value=mock_tool),
        patch("apps.api.screening.ScreeningRunsRepository", return_value=mock_repo),
    ):
        from apps.api.screening import run_screening
        row = await run_screening(triggered_by="startup")

    assert row["status"] == "completed"
    assert row["exception_count"] == 0


# ---------------------------------------------------------------------------
# run_screening: failure path
# ---------------------------------------------------------------------------

async def test_run_screening_persists_failed_row_when_tool_raises() -> None:
    """run_screening persists a failed row when the tool raises, never re-raises."""
    expected_row = _stub_repo_create(
        status="failed",
        exception_count=None,
        error="Screening run failed; see server logs for details.",
    )

    mock_tool = AsyncMock()
    mock_tool.handle = AsyncMock(side_effect=RuntimeError("DB connection refused"))
    mock_repo = AsyncMock()
    mock_repo.create = AsyncMock(return_value=expected_row)

    with (
        patch("apps.api.screening.ListTodayExceptionsTool", return_value=mock_tool),
        patch("apps.api.screening.ScreeningRunsRepository", return_value=mock_repo),
    ):
        from apps.api.screening import run_screening
        row = await run_screening(triggered_by="schedule")

    # Must not raise — returns the failed row
    assert row["status"] == "failed"
    assert "failed" in row.get("error", "").lower()

    call_kwargs = mock_repo.create.call_args.kwargs
    assert call_kwargs["status"] == "failed"
    assert call_kwargs["triggered_by"] == "schedule"
    assert "error" in call_kwargs


async def test_run_screening_returns_in_memory_dict_when_repo_also_fails() -> None:
    """When both the tool and the repo raise, run_screening returns a minimal in-memory dict."""
    mock_tool = AsyncMock()
    mock_tool.handle = AsyncMock(side_effect=RuntimeError("tool failed"))
    mock_repo = AsyncMock()
    mock_repo.create = AsyncMock(side_effect=RuntimeError("DB down"))

    with (
        patch("apps.api.screening.ListTodayExceptionsTool", return_value=mock_tool),
        patch("apps.api.screening.ScreeningRunsRepository", return_value=mock_repo),
    ):
        from apps.api.screening import run_screening
        row = await run_screening(triggered_by="manual")

    assert row["status"] == "failed"
    assert row["triggered_by"] == "manual"
    assert row["id"] is None


# ---------------------------------------------------------------------------
# _seconds_until_next_hour_utc — frozen clock
# ---------------------------------------------------------------------------

def test_seconds_until_next_hour_utc_before_target() -> None:
    """Returns ~23 hours when it is 07:00 UTC and target is 06:00 UTC."""
    from apps.api.screening import _seconds_until_next_hour_utc

    # 2026-06-12 07:00 UTC — target hour 6 has already passed today
    now_utc = datetime.datetime(2026, 6, 12, 7, 0, 0, tzinfo=datetime.timezone.utc)
    with patch("apps.api.screening.datetime") as mock_dt:
        mock_dt.datetime.now.return_value = now_utc
        mock_dt.datetime.side_effect = lambda *a, **kw: datetime.datetime(*a, **kw)
        mock_dt.timedelta = datetime.timedelta
        mock_dt.timezone = datetime.timezone
        secs = _seconds_until_next_hour_utc(6)

    # Next occurrence is 2026-06-13 06:00 UTC → ~23 hours from 07:00
    assert 22 * 3600 < secs < 24 * 3600


def test_seconds_until_next_hour_utc_after_midnight() -> None:
    """Returns ~5 hours when it is 01:00 UTC and target is 06:00 UTC."""
    from apps.api.screening import _seconds_until_next_hour_utc

    now_utc = datetime.datetime(2026, 6, 12, 1, 0, 0, tzinfo=datetime.timezone.utc)
    with patch("apps.api.screening.datetime") as mock_dt:
        mock_dt.datetime.now.return_value = now_utc
        mock_dt.datetime.side_effect = lambda *a, **kw: datetime.datetime(*a, **kw)
        mock_dt.timedelta = datetime.timedelta
        mock_dt.timezone = datetime.timezone
        secs = _seconds_until_next_hour_utc(6)

    # Next occurrence is today 06:00 → 5 hours = 18000 seconds
    assert abs(secs - 5 * 3600) < 10


# ---------------------------------------------------------------------------
# _scheduler_enabled — env var flag
# ---------------------------------------------------------------------------

def test_scheduler_enabled_default_true(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SCREENING_SCHEDULER_ENABLED", raising=False)
    from apps.api.screening import _scheduler_enabled
    assert _scheduler_enabled() is True


def test_scheduler_disabled_when_env_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCREENING_SCHEDULER_ENABLED", "false")
    from apps.api.screening import _scheduler_enabled
    assert _scheduler_enabled() is False


def test_scheduler_disabled_when_env_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCREENING_SCHEDULER_ENABLED", "0")
    from apps.api.screening import _scheduler_enabled
    assert _scheduler_enabled() is False


def test_scheduler_enabled_when_env_true(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCREENING_SCHEDULER_ENABLED", "true")
    from apps.api.screening import _scheduler_enabled
    assert _scheduler_enabled() is True


# ---------------------------------------------------------------------------
# _screening_hour — parsing
# ---------------------------------------------------------------------------

def test_screening_hour_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SCREENING_HOUR_UTC", raising=False)
    from apps.api.screening import _screening_hour
    assert _screening_hour() == 6


def test_screening_hour_custom(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCREENING_HOUR_UTC", "3")
    from apps.api.screening import _screening_hour
    assert _screening_hour() == 3


def test_screening_hour_clamps_to_valid_range(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCREENING_HOUR_UTC", "99")
    from apps.api.screening import _screening_hour
    assert _screening_hour() == 23


def test_screening_hour_invalid_falls_back_to_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCREENING_HOUR_UTC", "not-a-number")
    from apps.api.screening import _screening_hour
    assert _screening_hour() == 6
