"""P101-B-03 integration tests — T-605 (real-DB job lifecycle).

Tests the full job dispatch → execute_job → completed row + persisted report
message flow against a real PostgreSQL database.

Requires:
    DATABASE_URL set  (e.g. from .env)
    running PostgreSQL with the schema migrated

Run:
    DATABASE_URL=... uv run pytest tests/integration/test_p101_b03_job_lifecycle.py -v
"""

from __future__ import annotations

import os
from uuid import uuid4

import pytest

_HAS_DB = bool(os.environ.get("DATABASE_URL"))
_SKIP_NO_DB = pytest.mark.skipif(not _HAS_DB, reason="DATABASE_URL not set")


@pytest.fixture(autouse=True)
async def reset_db_pool() -> None:  # type: ignore[misc]
    """Reset the global asyncpg pool so each test gets a fresh event-loop bound pool."""
    import packages.persistence.db as db_module

    db_module._pool = None
    yield  # type: ignore[misc]
    if db_module._pool is not None:
        await db_module._pool.close()
        db_module._pool = None


# ---------------------------------------------------------------------------
# T-605 — Real-DB job lifecycle: dispatch → completed row + report message
# ---------------------------------------------------------------------------


@_SKIP_NO_DB
async def test_execute_job_simulate_completes_and_persists_row() -> None:
    """Full lifecycle: create job row → execute_job → completed row with result_json.

    Uses job_type='simulate' (not 'train_forecast') because the simulation path
    has no DB table dependencies beyond the jobs table itself; train_forecast
    requires a prediction_features table that may not be seeded in CI (noted
    in P101-B-01 context).
    """
    from packages.agent.job_executor import execute_job
    from packages.persistence.jobs_repo import JobsRepository
    from packages.persistence.sessions_repo import DecisionSessionRepository

    # --- Arrange: create a real session so the report message has a valid FK ---
    session_repo = DecisionSessionRepository()
    session_id = str(uuid4())
    await session_repo.create(
        session_id=session_id,
        user_id=None,
        goal="Integration test — P101-B-03 job lifecycle",
    )

    # Create job row with status pending_approval.
    jobs_repo = JobsRepository()
    job = await jobs_repo.create(
        session_id=None,  # pass None to avoid FK; report path handles gracefully
        job_type="simulate",
        params={"sku_id": "SKU-001", "order_qty": 100, "horizon_days": 30},
    )
    job_id = job["id"]

    # --- Act: execute the job (direct call, no background task scheduling) ---
    result = await execute_job(job_id)

    # --- Assert: job row is completed with non-null result_json ---
    assert result["status"] == "completed", (
        f"Job status must be 'completed'; got {result['status']!r}. "
        f"error field: {result.get('error')!r}"
    )
    assert result.get("result_json") is not None, (
        "completed job must have non-null result_json"
    )
    # asyncpg may return JSONB columns as a JSON string or as a dict depending on
    # driver version; normalise to dict before asserting content.
    import json as _json  # noqa: PLC0415

    raw_result_json = result["result_json"]
    if isinstance(raw_result_json, str):
        raw_result_json = _json.loads(raw_result_json)
    assert isinstance(raw_result_json, dict), (
        f"result_json must deserialise to a dict; got {type(raw_result_json)!r}"
    )
    # SimulationTool returns sku_id + simulation metrics.
    assert "sku_id" in raw_result_json or "stockout_days" in raw_result_json, (
        f"result_json must contain simulation output; got keys: {list(raw_result_json.keys())}"
    )


@_SKIP_NO_DB
async def test_execute_job_persists_report_message_in_session() -> None:
    """execute_job must persist an assistant report message into the session on completion.

    Creates a real session, creates a job row with session_id set, runs execute_job,
    then queries session messages to confirm the assistant report was inserted.
    """
    from packages.agent.job_executor import execute_job
    from packages.persistence.jobs_repo import JobsRepository
    from packages.persistence.sessions_repo import DecisionSessionRepository

    # --- Arrange ---
    session_repo = DecisionSessionRepository()
    session_id = str(uuid4())
    await session_repo.create(
        session_id=session_id,
        user_id=None,
        goal="Integration test — P101-B-03 report persistence",
    )

    jobs_repo = JobsRepository()
    job = await jobs_repo.create(
        session_id=None,  # session FK is UUID; pass None, then update via raw set
        job_type="simulate",
        params={"sku_id": "SKU-007", "order_qty": 50, "horizon_days": 14},
    )
    job_id = job["id"]

    # Manually link the session to the job by patching the session_id value
    # the executor reads from the job row.  Since create() inserts session_id as NULL
    # we update it directly so _persist_report_message receives a real session_id.
    from packages.persistence.db import get_pool  # noqa: PLC0415

    pool = await get_pool()
    import uuid  # noqa: PLC0415

    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE jobs SET session_id = $1 WHERE id = $2",
            uuid.UUID(session_id),
            job_id,
        )

    # --- Act ---
    result = await execute_job(job_id)

    assert result["status"] == "completed", (
        f"Job must complete; got {result['status']!r} / error: {result.get('error')!r}"
    )

    # --- Assert: assistant report message persisted ---
    from packages.persistence.db import get_pool as _gp  # noqa: PLC0415

    pool2 = await _gp()
    async with pool2.acquire() as conn:
        rows = await conn.fetch(
            "SELECT role, content FROM session_messages WHERE session_id = $1 ORDER BY created_at",
            uuid.UUID(session_id),
        )

    messages = [dict(r) for r in rows]
    assistant_msgs = [m for m in messages if m["role"] == "assistant"]

    assert len(assistant_msgs) >= 1, (
        f"At least one assistant message must be persisted in session {session_id}; "
        f"got messages: {messages}"
    )

    report_content = assistant_msgs[-1]["content"]
    assert "simulate" in report_content.lower() or "completed" in report_content.lower(), (
        f"Report message must reference 'simulate' or 'completed'; got: {report_content[:300]!r}"
    )


@_SKIP_NO_DB
async def test_execute_job_completed_at_set_on_terminal_status() -> None:
    """completed_at must be non-null when the job reaches 'completed' status."""
    from packages.agent.job_executor import execute_job
    from packages.persistence.db import get_pool  # noqa: PLC0415
    from packages.persistence.jobs_repo import JobsRepository

    import uuid  # noqa: PLC0415

    jobs_repo = JobsRepository()
    job = await jobs_repo.create(
        session_id=None,
        job_type="simulate",
        params={"sku_id": "SKU-002", "order_qty": 200, "horizon_days": 7},
    )
    job_id = job["id"]

    await execute_job(job_id)

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT status, completed_at, result_json FROM jobs WHERE id = $1",
            job_id,
        )

    assert row is not None
    assert row["status"] == "completed"
    assert row["completed_at"] is not None, (
        "completed_at must be set when job reaches terminal 'completed' status"
    )
    assert row["result_json"] is not None, (
        "result_json must be non-null after successful job completion"
    )
