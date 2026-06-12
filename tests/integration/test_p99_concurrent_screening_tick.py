"""T-597: Integration test for concurrent _run_scheduled_tick invocations.

Verifies that Postgres advisory lock + double-checked idempotency in
``_run_scheduled_tick`` prevents duplicate screening_runs rows when two
coroutines race to run the scheduled tick simultaneously.

Two test scenarios:
  1. No completed row for today before the race:
       asyncio.gather(tick, tick) → exactly ONE new completed row in the DB.
  2. A completed row already exists before the race:
       asyncio.gather(tick, tick) → ZERO new rows inserted (both skip).

Cleanup: deletes any screening_runs rows created by these tests.

Skip guard: DATABASE_URL not set → skip (same pattern as test_screening_integration.py).

Run targeted:
    DATABASE_URL=postgresql+asyncpg://bdos:bdos_dev@localhost:5432/bdos \\
        uv run pytest tests/integration/test_p99_concurrent_screening_tick.py -q
"""
from __future__ import annotations

import asyncio
import datetime
import os
from typing import Any, AsyncGenerator

import pytest

_HAS_DB = bool(os.environ.get("DATABASE_URL"))
_SKIP_NO_DB = pytest.mark.skipif(not _HAS_DB, reason="DATABASE_URL not set")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
async def reset_db_pool() -> AsyncGenerator[None, None]:
    """Reset the global asyncpg pool before and after each test.

    pytest-asyncio creates a new event loop per test function.  The global pool
    singleton in packages/persistence/db.py is bound to the event loop in which
    it was created, so reusing it across tests causes 'loop is closed' errors.
    Resetting the module-level variable forces pool recreation in the current loop.
    """
    import packages.persistence.db as db_module

    db_module._pool = None
    yield
    if db_module._pool is not None:
        await db_module._pool.close()
        db_module._pool = None


@pytest.fixture()
async def cleanup_today_test_rows() -> AsyncGenerator[list[str], None]:
    """Collect screening_runs IDs created during the test; delete them on teardown.

    Yields a mutable list to which test code must append created IDs.
    Rows with IDs NOT in the list (pre-existing seed rows) are never touched.
    """
    created_ids: list[str] = []
    yield created_ids
    if not created_ids:
        return
    import packages.persistence.db as db_module
    if db_module._pool is not None:
        async with db_module._pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM screening_runs WHERE id = ANY($1::uuid[])",
                created_ids,
            )


async def _count_completed_rows_for_today(pool: Any) -> int:
    """Return the number of completed screening_runs rows for today."""
    today = datetime.date.today()
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT COUNT(*) FROM screening_runs WHERE run_date = $1 AND status = 'completed'",
            today,
        )


async def _fetch_new_completed_rows(pool: Any, before_ids: set[str]) -> list[dict[str, Any]]:
    """Return completed rows for today whose IDs are not in *before_ids*."""
    today = datetime.date.today()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id::text, triggered_by, status, created_at
            FROM screening_runs
            WHERE run_date = $1
              AND status = 'completed'
            ORDER BY created_at DESC
            """,
            today,
        )
    return [dict(r) for r in rows if r["id"] not in before_ids]


# ---------------------------------------------------------------------------
# T-597(a): Two concurrent ticks with no pre-existing completed row →
#           exactly one new completed row is inserted.
# ---------------------------------------------------------------------------


@_SKIP_NO_DB
async def test_concurrent_ticks_with_no_prior_row_yield_exactly_one_completed(
    cleanup_today_test_rows: list[str],
) -> None:
    """Two concurrent _run_scheduled_tick calls produce exactly one completed row.

    Scenario: no completed row exists for today before the concurrent pair fires.
    Expected: the advisory lock ensures only one proceeds; the second either:
      (a) finds the lock held and skips immediately (lock path), or
      (b) acquires the lock after the first finishes but finds the now-existing
          completed row via the double-checked idempotency guard and skips.
    Either way: exactly one new completed row in the DB after the gather.
    """
    import packages.persistence.db as db_module
    from apps.api.screening import _run_scheduled_tick

    # Ensure pool is initialised before snapshot.
    pool = await db_module.get_pool()
    today = datetime.date.today()

    # --- Snapshot: record pre-existing completed row IDs for today ---
    async with pool.acquire() as conn:
        existing_rows = await conn.fetch(
            "SELECT id::text FROM screening_runs WHERE run_date = $1 AND status = 'completed'",
            today,
        )
    before_ids: set[str] = {r["id"] for r in existing_rows}

    # Delete any pre-existing completed row for today so we start clean.
    # We only delete rows that belong to *this* test invocation's slate —
    # but since we can't distinguish them, we track and delete ALL today's
    # completed rows inserted AFTER the snapshot.  Pre-existing rows are
    # recorded and excluded from cleanup assertions.
    # If pre-existing completed rows already exist we still need to delete
    # them temporarily so the test exercises the "no prior row" path.
    # To avoid destroying data permanently, re-insert them after the test.
    #
    # Simpler approach: isolate by deleting all today-rows before the test
    # and re-inserting the ones that were there before.  This is test-local
    # and the rows are fake seed data in a dev DB.
    async with pool.acquire() as conn:
        pre_existing = await conn.fetch(
            """
            SELECT id::text, run_date, triggered_by, status,
                   exception_count, severity_counts::text, payload::text, error, created_at
            FROM screening_runs
            WHERE run_date = $1
            """,
            today,
        )
        pre_existing_ids = [r["id"] for r in pre_existing]
        if pre_existing_ids:
            await conn.execute(
                "DELETE FROM screening_runs WHERE id = ANY($1::uuid[])",
                pre_existing_ids,
            )

    try:
        # --- Run two ticks concurrently ---
        await asyncio.gather(
            _run_scheduled_tick(triggered_by="startup"),
            _run_scheduled_tick(triggered_by="startup"),
        )

        # --- Assert: exactly one new completed row exists for today ---
        async with pool.acquire() as conn:
            new_rows = await conn.fetch(
                """
                SELECT id::text, triggered_by, status, created_at
                FROM screening_runs
                WHERE run_date = $1
                  AND status = 'completed'
                ORDER BY created_at
                """,
                today,
            )
        new_row_dicts = [dict(r) for r in new_rows]

        assert len(new_row_dicts) == 1, (
            f"Expected exactly 1 completed row after concurrent ticks, "
            f"got {len(new_row_dicts)}: {new_row_dicts}"
        )
        assert new_row_dicts[0]["status"] == "completed"
        assert new_row_dicts[0]["triggered_by"] == "startup"

        # Register the new row for cleanup.
        cleanup_today_test_rows.append(new_row_dicts[0]["id"])

    finally:
        # Restore pre-existing rows (if any) that were cleared for test isolation.
        if pre_existing:
            import json
            async with pool.acquire() as conn:
                for row in pre_existing:
                    await conn.execute(
                        """
                        INSERT INTO screening_runs
                            (id, run_date, triggered_by, status,
                             exception_count, severity_counts, payload, error, created_at)
                        VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7::jsonb, $8, $9)
                        ON CONFLICT (id) DO NOTHING
                        """,
                        row["id"],
                        today,
                        row["triggered_by"],
                        row["status"],
                        row["exception_count"],
                        row["severity_counts"],
                        row["payload"],
                        row["error"],
                        row["created_at"],
                    )


# ---------------------------------------------------------------------------
# T-597(b): Two concurrent ticks when a completed row already exists →
#           zero new rows are inserted.
# ---------------------------------------------------------------------------


@_SKIP_NO_DB
async def test_concurrent_ticks_when_completed_row_exists_yield_zero_new_rows(
    cleanup_today_test_rows: list[str],
) -> None:
    """Two concurrent _run_scheduled_tick calls skip when a completed row exists.

    Scenario: a completed row is already present for today (mimics the normal
    steady state — scheduler already ran once today).
    Expected: both ticks see the existing row in the double-check and skip;
    no additional rows are inserted.
    """
    import packages.persistence.db as db_module
    from apps.api.screening import run_screening, _run_scheduled_tick
    from packages.persistence.screening_runs_repo import ScreeningRunsRepository

    pool = await db_module.get_pool()
    today = datetime.date.today()

    # Ensure a completed row exists by running the screening directly (manual path —
    # no lock; deterministic).
    pre_row = await run_screening(triggered_by="manual")
    assert pre_row["status"] == "completed", (
        f"Setup failed: run_screening did not produce a completed row: {pre_row!r}"
    )
    cleanup_today_test_rows.append(pre_row["id"])

    # Snapshot: count completed rows before the concurrent pair.
    count_before = await _count_completed_rows_for_today(pool)
    assert count_before >= 1, "Expected at least one completed row after setup"

    # Snapshot IDs of completed rows before concurrent ticks.
    async with pool.acquire() as conn:
        before_ids_rows = await conn.fetch(
            "SELECT id::text FROM screening_runs WHERE run_date = $1 AND status = 'completed'",
            today,
        )
    before_ids: set[str] = {r["id"] for r in before_ids_rows}

    # --- Run two ticks concurrently — both should skip (double-check idempotency) ---
    await asyncio.gather(
        _run_scheduled_tick(triggered_by="schedule"),
        _run_scheduled_tick(triggered_by="schedule"),
    )

    # --- Assert: no new completed rows were inserted ---
    new_completed = await _fetch_new_completed_rows(pool, before_ids)

    assert len(new_completed) == 0, (
        f"Expected 0 new completed rows after concurrent ticks when one already exists, "
        f"got {len(new_completed)}: {new_completed}"
    )
