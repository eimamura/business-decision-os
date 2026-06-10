"""Integration tests for P73 — Feedback Learning Loop (T-468).

ADR: docs/adr/2026-06-10-autonomy-loops.md §3

Requires a real Postgres database with migration 0018 applied:
  docker compose -f infra/compose/compose.yaml up -d db

Scenarios covered:
  - write a decision record via DecisionMemoryStore.write
  - call set_latest_outcome(session_id, -1)
  - assert decision_log.outcome == -1 in the DB
  - assert search() returns the record with outcome=-1
"""
from __future__ import annotations

import json
import os
import uuid

import pytest

from packages.memory.decision import DecisionMemoryStore

_HAS_DB = bool(os.environ.get("DATABASE_URL"))
_SKIP_NO_DB = pytest.mark.skipif(not _HAS_DB, reason="DATABASE_URL not set")


async def _outcome_column_exists() -> bool:
    """Return True if decision_log.outcome column is present (migration 0018 applied)."""
    try:
        from packages.persistence.db import get_pool

        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'decision_log'
                  AND column_name = 'outcome'
                """
            )
        return row is not None
    except Exception:
        return False


@_SKIP_NO_DB
async def test_set_latest_outcome_updates_decision_log_outcome() -> None:
    """Full round-trip: write a decision record, call set_latest_outcome(-1),
    assert the outcome column is -1 and search() returns the record with outcome=-1."""
    if not await _outcome_column_exists():
        pytest.skip(
            "decision_log.outcome column not found — migration 0018 not applied"
        )

    session_id = str(uuid.uuid4())
    store = DecisionMemoryStore()

    # 1. Write a decision record
    await store.write(
        {
            "session_id": session_id,
            "record_type": "decision",
            "content_json": {"decision": "order 500 units of SKU-001"},
        }
    )

    # 2. Apply negative outcome feedback
    updated = await store.set_latest_outcome(session_id, -1)
    assert updated is True, (
        "set_latest_outcome must return True when a decision record exists"
    )

    # 3. Verify via search() that the record has outcome=-1
    results = await store.search(json.dumps({"session_id": session_id}), k=5)
    assert len(results) >= 1, (
        "search() must return at least one record for the session"
    )
    # The most recent decision record (first result, recency-ordered) must have outcome=-1
    latest = results[0]
    assert latest["record_type"] == "decision", (
        "Returned record must have record_type='decision'"
    )
    assert latest["outcome"] == -1, (
        f"Expected outcome=-1, got outcome={latest['outcome']!r}"
    )


@_SKIP_NO_DB
async def test_set_latest_outcome_only_updates_latest_record() -> None:
    """When multiple decision records exist for a session, set_latest_outcome only
    updates the most recent one (ORDER BY created_at DESC LIMIT 1)."""
    if not await _outcome_column_exists():
        pytest.skip(
            "decision_log.outcome column not found — migration 0018 not applied"
        )

    session_id = str(uuid.uuid4())
    store = DecisionMemoryStore()

    # Write two decision records (first = older, second = newer)
    await store.write(
        {
            "session_id": session_id,
            "record_type": "decision",
            "content_json": {"decision": "first decision — hold stock"},
        }
    )
    await store.write(
        {
            "session_id": session_id,
            "record_type": "decision",
            "content_json": {"decision": "second decision — order more"},
        }
    )

    # Apply positive outcome — should update only the latest
    updated = await store.set_latest_outcome(session_id, 1)
    assert updated is True

    results = await store.search(json.dumps({"session_id": session_id}), k=5)
    assert len(results) >= 2

    # Results are recency-ordered; the first (latest) must have outcome=1
    assert results[0]["outcome"] == 1, (
        "Latest record must have outcome=1 after set_latest_outcome"
    )
    # The older record must still have NULL outcome
    assert results[1]["outcome"] is None, (
        "Older record must remain unmodified (outcome=NULL)"
    )


@_SKIP_NO_DB
async def test_set_latest_outcome_returns_false_when_no_decision_record() -> None:
    """set_latest_outcome returns False when no decision record exists for the session."""
    if not await _outcome_column_exists():
        pytest.skip(
            "decision_log.outcome column not found — migration 0018 not applied"
        )

    session_id = str(uuid.uuid4())  # fresh session — no records
    store = DecisionMemoryStore()

    updated = await store.set_latest_outcome(session_id, 1)
    assert updated is False, (
        "set_latest_outcome must return False when no decision record exists"
    )
