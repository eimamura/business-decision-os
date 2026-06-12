"""Unit tests for apps/api/screening.py — T-575 (unit tier) + T-596 (advisory lock).

Coverage:
  - run_screening: counts derivation, completed-row persistence
  - run_screening: failed-row persistence when tool raises
  - _seconds_until_next_hour_utc: next-run computation with frozen clock
  - _scheduler_enabled: disabled flag via env var
  - _screening_hour: default and custom parsing
  - _run_scheduled_tick (T-596):
      lock-not-acquired → skip, no run_screening called
      lock acquired + today-row exists → skip (double-check), no run_screening called
      lock acquired + no today-row → run_screening called, unlock called
      unlock called even when run_screening raises
      manual path (run_screening directly) bypasses lock/idempotency entirely

Zero-network rule: asyncpg pool and the tool handle() are both mocked.
"""
from __future__ import annotations

import datetime
import uuid
from unittest.mock import AsyncMock, MagicMock, call, patch

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


def _make_stub_conn(lock_acquired: bool = True) -> AsyncMock:
    """Return an AsyncMock mimicking an asyncpg Connection.

    fetchval(...) returns *lock_acquired* (simulates pg_try_advisory_lock result).
    execute(...) is a no-op (simulates pg_advisory_unlock).
    """
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=lock_acquired)
    conn.execute = AsyncMock(return_value=None)
    # Support async context manager protocol (pool.acquire())
    conn.__aenter__ = AsyncMock(return_value=conn)
    conn.__aexit__ = AsyncMock(return_value=False)
    return conn


def _make_stub_pool(conn: AsyncMock) -> MagicMock:
    """Return a MagicMock pool whose acquire() returns *conn* as an async ctx manager."""
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=conn)
    return pool


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


async def test_run_screening_zero_exceptions_repo_called_with_empty_severity_counts() -> None:
    """When no exceptions exist, repo.create is called with severity_counts={} (not None)."""
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
        await run_screening(triggered_by="startup")

    call_kwargs = mock_repo.create.call_args.kwargs
    # severity_counts must be an empty dict, not None, for zero-exception payloads
    assert call_kwargs["severity_counts"] == {}
    assert call_kwargs["exception_count"] == 0


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


# ---------------------------------------------------------------------------
# T-596: _run_scheduled_tick — advisory lock + double-checked idempotency
# ---------------------------------------------------------------------------

async def test_run_scheduled_tick_lock_not_acquired_skips_run() -> None:
    """When pg_try_advisory_lock returns False, skip with INFO — do NOT call run_screening."""
    conn = _make_stub_conn(lock_acquired=False)
    pool = _make_stub_pool(conn)

    with (
        patch("apps.api.screening.get_pool", AsyncMock(return_value=pool)),
        patch("apps.api.screening.run_screening") as mock_run,
    ):
        from apps.api.screening import _run_scheduled_tick
        await _run_scheduled_tick(triggered_by="schedule")

    # run_screening must NOT have been called
    mock_run.assert_not_called()
    # pg_advisory_unlock must NOT be called when lock was not acquired
    conn.execute.assert_not_called()


async def test_run_scheduled_tick_lock_acquired_today_row_exists_skips_run() -> None:
    """When lock is acquired but a completed row exists for today, skip (double-check)."""
    today = datetime.date.today()
    existing_row = _stub_repo_create(
        run_date=today,
        triggered_by="startup",
        status="completed",
    )

    conn = _make_stub_conn(lock_acquired=True)
    pool = _make_stub_pool(conn)

    mock_repo = AsyncMock()
    mock_repo.latest_for_date = AsyncMock(return_value=existing_row)

    with (
        patch("apps.api.screening.get_pool", AsyncMock(return_value=pool)),
        patch("apps.api.screening.ScreeningRunsRepository", return_value=mock_repo),
        patch("apps.api.screening.run_screening") as mock_run,
    ):
        from apps.api.screening import _run_scheduled_tick
        await _run_scheduled_tick(triggered_by="schedule")

    # run_screening must NOT have been called
    mock_run.assert_not_called()
    # pg_advisory_unlock MUST have been called (in finally block)
    conn.execute.assert_called_once()
    assert "pg_advisory_unlock" in conn.execute.call_args.args[0]


async def test_run_scheduled_tick_lock_acquired_no_row_calls_run_screening() -> None:
    """When lock is acquired and no completed row exists, run_screening is called."""
    conn = _make_stub_conn(lock_acquired=True)
    pool = _make_stub_pool(conn)

    mock_repo = AsyncMock()
    mock_repo.latest_for_date = AsyncMock(return_value=None)

    with (
        patch("apps.api.screening.get_pool", AsyncMock(return_value=pool)),
        patch("apps.api.screening.ScreeningRunsRepository", return_value=mock_repo),
        patch("apps.api.screening.run_screening", AsyncMock(return_value={})) as mock_run,
    ):
        from apps.api.screening import _run_scheduled_tick
        await _run_scheduled_tick(triggered_by="startup")

    mock_run.assert_called_once_with(triggered_by="startup")
    # pg_advisory_unlock MUST have been called in the finally block
    conn.execute.assert_called_once()
    assert "pg_advisory_unlock" in conn.execute.call_args.args[0]


async def test_run_scheduled_tick_unlock_called_even_when_run_screening_raises() -> None:
    """pg_advisory_unlock is called in finally even when run_screening raises."""
    conn = _make_stub_conn(lock_acquired=True)
    pool = _make_stub_pool(conn)

    mock_repo = AsyncMock()
    mock_repo.latest_for_date = AsyncMock(return_value=None)

    with (
        patch("apps.api.screening.get_pool", AsyncMock(return_value=pool)),
        patch("apps.api.screening.ScreeningRunsRepository", return_value=mock_repo),
        patch(
            "apps.api.screening.run_screening",
            AsyncMock(side_effect=RuntimeError("unexpected boom")),
        ),
    ):
        from apps.api.screening import _run_scheduled_tick
        with pytest.raises(RuntimeError, match="unexpected boom"):
            await _run_scheduled_tick(triggered_by="schedule")

    # unlock must still have been called despite the exception
    conn.execute.assert_called_once()
    assert "pg_advisory_unlock" in conn.execute.call_args.args[0]


async def test_manual_run_screening_bypasses_lock_and_idempotency() -> None:
    """run_screening(triggered_by='manual') calls the tool directly, no advisory lock."""
    tool_result = _make_tool_result([])
    expected_row = _stub_repo_create(status="completed", exception_count=0, triggered_by="manual")

    mock_tool = AsyncMock()
    mock_tool.handle = AsyncMock(return_value=tool_result)
    mock_repo = AsyncMock()
    mock_repo.create = AsyncMock(return_value=expected_row)

    with (
        patch("apps.api.screening.ListTodayExceptionsTool", return_value=mock_tool),
        patch("apps.api.screening.ScreeningRunsRepository", return_value=mock_repo),
        patch("apps.api.screening.get_pool") as mock_get_pool,
    ):
        from apps.api.screening import run_screening
        row = await run_screening(triggered_by="manual")

    # get_pool must NOT have been called (no advisory lock for manual runs)
    mock_get_pool.assert_not_called()
    assert row["status"] == "completed"
    assert row["triggered_by"] == "manual"


async def test_run_scheduled_tick_lock_acquired_failed_row_skips_run() -> None:
    """When the latest row for today is failed (not completed), run_screening is called."""
    today = datetime.date.today()
    failed_row = _stub_repo_create(
        run_date=today,
        triggered_by="startup",
        status="failed",
    )

    conn = _make_stub_conn(lock_acquired=True)
    pool = _make_stub_pool(conn)

    mock_repo = AsyncMock()
    mock_repo.latest_for_date = AsyncMock(return_value=failed_row)

    with (
        patch("apps.api.screening.get_pool", AsyncMock(return_value=pool)),
        patch("apps.api.screening.ScreeningRunsRepository", return_value=mock_repo),
        patch("apps.api.screening.run_screening", AsyncMock(return_value={})) as mock_run,
    ):
        from apps.api.screening import _run_scheduled_tick
        await _run_scheduled_tick(triggered_by="schedule")

    # A failed previous row does NOT satisfy the idempotency check — must still run
    mock_run.assert_called_once_with(triggered_by="schedule")
    conn.execute.assert_called_once()
