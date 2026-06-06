from __future__ import annotations

"""Integration tests for P41-B-04 — WorkingMemoryStore and DecisionMemoryStore.

T-297: write + search round-trips against a real Postgres database.

Prerequisites:
  - DATABASE_URL env var is set
  - Migrations 0015 (agent_steps) and 0016 (decision_log) have been applied
  - docker compose up -d db
"""

import json
import os
import uuid

import pytest

from packages.memory.decision import DecisionMemoryStore
from packages.memory.working import WorkingMemoryStore

_HAS_DB = bool(os.environ.get("DATABASE_URL"))
_SKIP_NO_DB = pytest.mark.skipif(not _HAS_DB, reason="DATABASE_URL not set")


# ---------------------------------------------------------------------------
# WorkingMemoryStore
# ---------------------------------------------------------------------------


@_SKIP_NO_DB
async def test_working_memory_store_write_and_search() -> None:
    """write() inserts an agent_steps row; search('session:<id>') returns it."""
    session_id = str(uuid.uuid4())
    store = WorkingMemoryStore()

    await store.write({"session_id": session_id, "content": "test tool result"})
    results = await store.search(f"session:{session_id}", k=5)

    assert len(results) >= 1
    assert results[0]["content"] == "test tool result"


@_SKIP_NO_DB
async def test_working_memory_store_search_wrong_prefix_returns_empty() -> None:
    """search() with a query that does not start with 'session:' returns []."""
    store = WorkingMemoryStore()
    results = await store.search("not_a_session_prefix", k=5)
    assert results == []


# ---------------------------------------------------------------------------
# DecisionMemoryStore
# ---------------------------------------------------------------------------


async def _decision_log_exists() -> bool:
    """Return True if the decision_log table is present in the database."""
    try:
        from packages.persistence.db import get_pool

        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name = 'decision_log'
                """
            )
        return row is not None
    except Exception:
        return False


@_SKIP_NO_DB
async def test_decision_memory_store_write_and_search_by_session() -> None:
    """write() inserts a decision record; search() returns it filtered by session_id."""
    if not await _decision_log_exists():
        pytest.skip("decision_log table not found — migration 0016 not applied")

    session_id = str(uuid.uuid4())
    store = DecisionMemoryStore()

    await store.write(
        {
            "session_id": session_id,
            "record_type": "decision",
            "content_json": {"decision": "test decision"},
        }
    )

    results = await store.search(json.dumps({"session_id": session_id}), k=5)

    assert len(results) >= 1
    assert results[0]["record_type"] == "decision"


@_SKIP_NO_DB
async def test_decision_memory_store_write_failure_record() -> None:
    """write() with record_type='failure' is retrievable with a record_type filter."""
    if not await _decision_log_exists():
        pytest.skip("decision_log table not found — migration 0016 not applied")

    session_id = str(uuid.uuid4())
    store = DecisionMemoryStore()

    await store.write(
        {
            "session_id": session_id,
            "record_type": "failure",
            "content_json": {"error": "something went wrong"},
        }
    )

    results = await store.search(
        json.dumps({"session_id": session_id, "record_type": "failure"}),
        k=5,
    )

    assert len(results) >= 1
    assert results[0]["record_type"] == "failure"


@_SKIP_NO_DB
async def test_decision_memory_store_search_no_session_id_returns_empty() -> None:
    """search() with a JSON query that has no session_id key returns []."""
    if not await _decision_log_exists():
        pytest.skip("decision_log table not found — migration 0016 not applied")

    store = DecisionMemoryStore()
    results = await store.search(json.dumps({"foo": "bar"}), k=5)
    assert results == []
