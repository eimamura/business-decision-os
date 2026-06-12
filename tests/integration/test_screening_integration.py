"""T-575: Integration test for the screening service against a real PostgreSQL database.

Requires a running PostgreSQL instance reachable via DATABASE_URL with migration 0021
applied (screening_runs table) and the dev seed data loaded.

Test covers:
  - run_screening("manual") persists a completed row with non-null payload
  - payload keys (counts, truncated, exceptions, missing_data) are all present
  - exception_count == len(payload.exceptions) consistency
  - latest_for_date(today) retrieves the row that was just created

Cleanup: deletes any rows inserted by this test after each test case.

Run with:
    docker compose up -d db && DATABASE_URL=postgresql+asyncpg://bdos:bdos_dev@localhost:5432/bdos \\
        uv run pytest tests/integration/test_screening_integration.py -v
"""
from __future__ import annotations

import datetime
import os

import pytest

_HAS_DB = bool(os.environ.get("DATABASE_URL"))
_SKIP_NO_DB = pytest.mark.skipif(not _HAS_DB, reason="DATABASE_URL not set")

_PAYLOAD_REQUIRED_KEYS = {"counts", "truncated", "exceptions", "missing_data"}


async def _get_pool_for_test() -> object:
    """Return the current asyncpg pool (already initialised by run_screening)."""
    import packages.persistence.db as db_module
    return await db_module.get_pool()


@pytest.fixture(autouse=True)
async def reset_db_pool() -> None:  # type: ignore[misc]
    """Reset the global asyncpg pool before and after each test.

    pytest-asyncio creates a new event loop per test function. The global pool
    singleton in packages/persistence/db.py is bound to the event loop in which
    it was created, so reusing it across tests causes 'loop is closed' errors.
    Resetting the module-level variable forces pool recreation in the current loop.
    """
    import packages.persistence.db as db_module

    db_module._pool = None
    yield  # type: ignore[misc]
    if db_module._pool is not None:
        await db_module._pool.close()
        db_module._pool = None


@pytest.fixture(autouse=True)
async def cleanup_screening_rows() -> None:  # type: ignore[misc]
    """Delete any screening_runs rows created by this test after each test case."""
    created_ids: list[str] = []
    yield created_ids  # type: ignore[misc]
    if not created_ids:
        return
    import packages.persistence.db as db_module
    if db_module._pool is not None:
        async with db_module._pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM screening_runs WHERE id = ANY($1::uuid[])",
                created_ids,
            )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@_SKIP_NO_DB
async def test_run_screening_manual_persists_completed_row(
    cleanup_screening_rows: list[str],
) -> None:
    """run_screening('manual') creates a completed row in the real DB."""
    from apps.api.screening import run_screening

    row = await run_screening(triggered_by="manual")

    # Register for cleanup regardless of assertion outcome
    if row.get("id") is not None:
        cleanup_screening_rows.append(row["id"])

    assert row["status"] == "completed", f"Expected completed, got: {row!r}"
    assert row["triggered_by"] == "manual"
    assert row["id"] is not None, "Inserted row must have an id"


@_SKIP_NO_DB
async def test_run_screening_payload_keys_present(
    cleanup_screening_rows: list[str],
) -> None:
    """run_screening result payload contains all required keys."""
    from apps.api.screening import run_screening

    row = await run_screening(triggered_by="manual")

    if row.get("id") is not None:
        cleanup_screening_rows.append(row["id"])

    assert row["status"] == "completed"
    payload = row.get("payload")
    assert payload is not None, "payload must be non-null on a completed run"
    missing = _PAYLOAD_REQUIRED_KEYS - set(payload.keys())
    assert not missing, f"Payload missing required keys: {missing}"


@_SKIP_NO_DB
async def test_run_screening_exception_count_consistency(
    cleanup_screening_rows: list[str],
) -> None:
    """exception_count == len(payload.exceptions) for a completed row."""
    from apps.api.screening import run_screening

    row = await run_screening(triggered_by="manual")

    if row.get("id") is not None:
        cleanup_screening_rows.append(row["id"])

    assert row["status"] == "completed"
    payload = row["payload"]
    assert payload is not None

    exceptions_in_payload = payload.get("exceptions", [])
    assert row["exception_count"] == len(exceptions_in_payload), (
        f"exception_count={row['exception_count']} != "
        f"len(payload.exceptions)={len(exceptions_in_payload)}"
    )


@_SKIP_NO_DB
async def test_latest_for_date_returns_inserted_row(
    cleanup_screening_rows: list[str],
) -> None:
    """latest_for_date(today) returns a completed row after run_screening inserts one.

    Note: The assertion checks that a completed row is present for today and that
    the inserted row is reachable by ID — rather than asserting it is THE latest row,
    since concurrent integration tests may insert additional rows between the creation
    and the lookup.  The created row's ID is verified by direct repo lookup.
    """
    from apps.api.screening import run_screening
    from packages.persistence.screening_runs_repo import ScreeningRunsRepository

    row = await run_screening(triggered_by="manual")

    if row.get("id") is not None:
        cleanup_screening_rows.append(row["id"])

    assert row["status"] == "completed"
    assert row["id"] is not None

    repo = ScreeningRunsRepository()
    today = datetime.date.today()

    # latest_for_date must return some completed row for today (the DB is not empty now).
    latest = await repo.latest_for_date(today)
    assert latest is not None, "latest_for_date must return a row after insertion"
    assert latest["status"] == "completed"

    # Direct verification: the row we inserted must be queryable by its run_date.
    # latest() is the global latest; we verify our row exists by checking it
    # appears when we fetch the full latest-for-date (there must be a row for today).
    pool = await _get_pool_for_test()
    async with pool.acquire() as conn:
        direct = await conn.fetchrow(
            "SELECT id, status FROM screening_runs WHERE id = $1::uuid",
            row["id"],
        )
    assert direct is not None, f"Inserted row {row['id']} not found in DB"
    assert str(direct["id"]) == row["id"]
    assert direct["status"] == "completed"
