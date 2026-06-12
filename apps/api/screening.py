"""Daily screening runner service + lifespan-managed asyncio scheduler.

Design basis: docs/adr/2026-06-12-daily-screening-scheduler.md
Hardening:    T-596 — Postgres advisory lock + double-checked idempotency

The transport-agnostic service function ``run_screening`` invokes the
``list_today_exceptions`` tool's ``handle()`` directly (deterministic SQL, no LLM),
derives per-severity counts, and persists the result via ScreeningRunsRepository.

The scheduler is a background asyncio task managed by the FastAPI lifespan:
  - On startup: if no completed row exists for today → run with triggered_by="startup".
  - Daily loop: sleep until the next SCREENING_HOUR_UTC tick, then run with
    triggered_by="schedule".
  - Disabled entirely when SCREENING_SCHEDULER_ENABLED=false (default true).

Advisory lock (T-596):
  ``_run_scheduled_tick`` is the hardened entry point for "schedule" and "startup"
  triggered_by values.  It acquires ``pg_try_advisory_lock(_SCREENING_ADVISORY_LOCK_KEY)``
  on a single dedicated connection before running, skips with INFO if the lock is held by
  another process, and releases the lock in a finally block on the *same* connection
  (Postgres advisory locks are connection-scoped).  Inside the lock it re-checks whether a
  completed run already exists for today (double-checked idempotency guard) and skips if so.
  Manual ``POST /run`` calls bypass this wrapper — explicit user intent is never blocked.

Lock key derivation:
  _SCREENING_ADVISORY_LOCK_KEY = 0x73637265656E (int64 = 31077564654702)
  Derived from the ASCII bytes of "screen" packed into a big-endian int48 then zero-padded
  to int64.  The value is stable; it is not dynamically computed at runtime.

Environment variables (document in .env.example):
  SCREENING_SCHEDULER_ENABLED   true (default) | false — set false in tests/CI
  SCREENING_HOUR_UTC            integer hour 0-23 (default 6) — daily run time
"""
from __future__ import annotations

import asyncio
import datetime
import logging
import os
from typing import Any
from uuid import uuid4

from packages.persistence.db import get_pool
from packages.persistence.screening_runs_repo import ScreeningRunsRepository
from packages.tools.base import ToolContext
from packages.tools.list_today_exceptions_tool import ListTodayExceptionsTool

_log = logging.getLogger(__name__)

_SCHEDULER_ENABLED_ENV = "SCREENING_SCHEDULER_ENABLED"
_HOUR_ENV = "SCREENING_HOUR_UTC"
_DEFAULT_HOUR = 6

# Advisory lock key for Postgres pg_try_advisory_lock / pg_advisory_unlock.
# Derived from ASCII("screen") = 0x73 0x63 0x72 0x65 0x65 0x6E packed big-endian → int64.
# This is a module-level constant; its value must never change once written to any DB.
_SCREENING_ADVISORY_LOCK_KEY: int = 0x73637265656E  # 31077564654702


def _scheduler_enabled() -> bool:
    return os.environ.get(_SCHEDULER_ENABLED_ENV, "true").lower() not in ("false", "0", "no")


def _screening_hour() -> int:
    raw = os.environ.get(_HOUR_ENV, str(_DEFAULT_HOUR))
    try:
        hour = int(raw)
    except ValueError:
        _log.warning(
            "Invalid %s=%r — falling back to %d", _HOUR_ENV, raw, _DEFAULT_HOUR
        )
        hour = _DEFAULT_HOUR
    return max(0, min(23, hour))


def _make_tool_context() -> ToolContext:
    """Build a minimal ToolContext for the screening service (no LLM, no session)."""
    fixed_id = uuid4()
    return ToolContext(
        session_id=fixed_id,
        agent_step_id=fixed_id,
        specialist_role="control",
        actor="scheduler",
        correlation_id=fixed_id,
        user_role="admin",
    )


async def run_screening(triggered_by: str) -> dict[str, Any]:
    """Invoke list_today_exceptions, derive counts, and persist the result.

    Always returns the persisted row dict.  On exception, persists a ``failed``
    row with a generic error message (full error logged server-side) and returns
    that row — never raises to the caller.

    This function is the *pure executor* — it performs no lock or idempotency check.
    Scheduled / startup callers MUST go through ``_run_scheduled_tick`` instead.
    Manual ``POST /run`` may call this directly (explicit user intent, no gating).

    Args:
        triggered_by: one of "schedule", "startup", or "manual".
    """
    repo = ScreeningRunsRepository()
    run_date = datetime.date.today()

    try:
        tool = ListTodayExceptionsTool()
        ctx = _make_tool_context()
        result = await tool.handle({}, ctx)

        exceptions: list[dict[str, Any]] = result.output.get("exceptions", [])
        exception_count = len(exceptions)

        # Derive per-severity counts from the full exception list (before cap)
        # Use the counts dict from the tool output (pre-cap totals per domain),
        # then separately compute per-severity totals from the capped list.
        # The tool output `counts` is per-domain; we need per-severity here.
        severity_counts: dict[str, int] = {}
        for exc_item in exceptions:
            sev: str = exc_item.get("severity", "info")
            severity_counts[sev] = severity_counts.get(sev, 0) + 1

        row = await repo.create(
            run_date=run_date,
            triggered_by=triggered_by,
            status="completed",
            exception_count=exception_count,
            severity_counts=severity_counts,
            payload=result.output,
        )
        _log.info(
            "screening run completed: triggered_by=%s exception_count=%d severity=%s",
            triggered_by,
            exception_count,
            severity_counts,
        )
        return row

    except Exception as exc:
        # Log full error server-side; persist a generic message to the DB.
        _log.error(
            "screening run failed: triggered_by=%s error=%s",
            triggered_by,
            exc,
            exc_info=True,
        )
        try:
            row = await repo.create(
                run_date=run_date,
                triggered_by=triggered_by,
                status="failed",
                error="Screening run failed; see server logs for details.",
            )
            return row
        except Exception as persist_exc:
            # Persist itself failed — construct a minimal in-memory response.
            _log.error("screening failed-row persist failed: %s", persist_exc, exc_info=True)
            return {
                "id": None,
                "run_date": run_date.isoformat(),
                "triggered_by": triggered_by,
                "status": "failed",
                "exception_count": None,
                "severity_counts": None,
                "payload": None,
                "error": "Screening run failed; see server logs for details.",
                "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            }


async def _run_scheduled_tick(triggered_by: str) -> None:
    """Hardened entry point for scheduled/startup ticks.

    Applies two guards before invoking ``run_screening``:

    1. Postgres advisory lock (``pg_try_advisory_lock``): a single connection is
       acquired from the pool and held for the duration of this function.  If the lock
       is already held by another process the tick is skipped with an INFO log.  The
       lock is released in a finally block on the *same* connection — Postgres advisory
       locks are connection-scoped, so both acquire and release MUST use the same
       connection object.

    2. Double-checked idempotency: *inside* the lock, re-fetch
       ``ScreeningRunsRepository.latest_for_date(today)`` and skip if a completed row
       already exists for today.  This closes the race where two processes both pass the
       pre-lock check (the lightweight check in ``_screening_loop``) before either
       acquires the lock.

    Manual ``POST /run`` calls (triggered_by="manual") MUST NOT use this function;
    they call ``run_screening`` directly.

    Args:
        triggered_by: "schedule" or "startup".
    """
    pool = await get_pool()
    lock_key = _SCREENING_ADVISORY_LOCK_KEY
    today = datetime.date.today()

    # Hold a dedicated connection for the advisory lock lifetime.
    async with pool.acquire() as conn:
        # Attempt a non-blocking advisory lock.
        acquired: bool = await conn.fetchval(
            "SELECT pg_try_advisory_lock($1)", lock_key
        )
        if not acquired:
            _log.info(
                "screening tick skipped: lock held elsewhere (triggered_by=%s)", triggered_by
            )
            return

        try:
            # Double-check idempotency inside the lock.
            repo = ScreeningRunsRepository()
            existing = await repo.latest_for_date(today)
            if existing is not None and existing.get("status") == "completed":
                _log.info(
                    "screening tick skipped: completed run already exists for %s "
                    "(id=%s, triggered_by=%s)",
                    today.isoformat(),
                    existing.get("id"),
                    triggered_by,
                )
                return

            # Lock acquired + no completed row for today → execute the screening.
            await run_screening(triggered_by=triggered_by)

        finally:
            # Always release the advisory lock on the same connection.
            await conn.execute("SELECT pg_advisory_unlock($1)", lock_key)


def _seconds_until_next_hour_utc(target_hour: int) -> float:
    """Return seconds until the next occurrence of *target_hour* (UTC)."""
    now = datetime.datetime.now(datetime.timezone.utc)
    today_target = now.replace(
        hour=target_hour, minute=0, second=0, microsecond=0
    )
    if now >= today_target:
        # Today's window has passed; target is tomorrow.
        next_target = today_target + datetime.timedelta(days=1)
    else:
        next_target = today_target
    return (next_target - now).total_seconds()


async def _screening_loop() -> None:
    """Background loop: startup check → daily tick at SCREENING_HOUR_UTC.

    Designed to run as a long-lived asyncio task inside the FastAPI lifespan.
    Handles asyncio.CancelledError cleanly (re-raises after logging).
    All other exceptions are caught, logged, and the loop continues.

    Uses ``_run_scheduled_tick`` for both the startup run and the daily tick so
    that advisory-lock + idempotency guards apply in all scheduled paths.
    """
    _log.info("screening scheduler started")

    # --- Startup run (hardened via advisory lock + double-check) ---
    try:
        await _run_scheduled_tick(triggered_by="startup")
    except asyncio.CancelledError:
        _log.info("screening scheduler cancelled during startup check")
        raise
    except Exception as exc:
        _log.error("screening startup check error: %s", exc, exc_info=True)

    # --- Daily loop ---
    hour = _screening_hour()
    while True:
        sleep_secs = _seconds_until_next_hour_utc(hour)
        _log.info(
            "screening scheduler: next run in %.0f seconds (UTC %02d:00)",
            sleep_secs,
            hour,
        )
        try:
            await asyncio.sleep(sleep_secs)
        except asyncio.CancelledError:
            _log.info("screening scheduler cancelled during sleep")
            raise

        try:
            await _run_scheduled_tick(triggered_by="schedule")
        except asyncio.CancelledError:
            _log.info("screening scheduler cancelled during scheduled run")
            raise
        except Exception as exc:
            # _run_scheduled_tick itself should not raise, but guard here for safety.
            _log.error("screening scheduler loop error: %s", exc, exc_info=True)


def start_screening_scheduler() -> asyncio.Task[None] | None:
    """Create and return the screening loop task, or None when disabled.

    Called from the FastAPI lifespan after pool initialisation.
    """
    if not _scheduler_enabled():
        _log.info("screening scheduler disabled (SCREENING_SCHEDULER_ENABLED=false)")
        return None

    task: asyncio.Task[None] = asyncio.create_task(_screening_loop(), name="screening_scheduler")

    def _on_done(t: asyncio.Task[None]) -> None:
        if t.cancelled():
            return
        exc = t.exception()
        if exc is not None:
            _log.error("screening scheduler task exited unexpectedly: %s", exc, exc_info=exc)

    task.add_done_callback(_on_done)
    return task
