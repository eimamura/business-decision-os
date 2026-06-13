from __future__ import annotations

"""Unit tests for DecisionMemoryStore (P120 — T-687/T-688).

All tests inject a mock asyncpg pool — no real DB is touched.
Mock target: packages.persistence.db.get_pool (imported lazily inside _get_pool()).
"""

import json
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from packages.memory.decision import DecisionMemoryStore


# ---------------------------------------------------------------------------
# Helpers — same pattern as tests/unit/test_long_term_memory_store.py
# ---------------------------------------------------------------------------


def _make_fake_pool(
    fetch_return: list[Any] | None = None,
) -> tuple[MagicMock, MagicMock]:
    """Return (pool, conn) where conn has mocked execute and fetch.

    *fetch_return* — rows returned by conn.fetch (default: empty list)
    """
    mock_conn = MagicMock()
    mock_conn.execute = AsyncMock(return_value=None)
    mock_conn.fetch = AsyncMock(return_value=fetch_return if fetch_return is not None else [])

    @asynccontextmanager
    async def _fake_acquire():  # type: ignore[return]
        yield mock_conn

    mock_pool = MagicMock()
    mock_pool.acquire = _fake_acquire
    return mock_pool, mock_conn


def _fake_row(
    record_type: str = "decision",
    content_json: str = '{"decision": "sample"}',
    agent_role: str = "control",
) -> MagicMock:
    """Return a dict-like object that mimics an asyncpg Record row for decision_log."""
    row: dict[str, Any] = {
        "id": uuid.uuid4(),
        "session_id": uuid.uuid4(),
        "record_type": record_type,
        "content_json": content_json,
        "agent_role": agent_role,
        "created_at": datetime.now(timezone.utc),
        "outcome": None,
    }
    record = MagicMock()
    record.__iter__ = lambda _: iter(row.items())
    record.keys = lambda: row.keys()
    record.items = lambda: row.items()
    record.values = lambda: row.values()
    record.__getitem__ = lambda _, k: row[k]
    # dict(row) compatibility — asyncpg Record supports dict() via mapping protocol
    record.__class__ = MagicMock
    # Make dict(record) work by delegating to the underlying dict
    record.__dict_copy__ = row
    return record


def _fake_asyncpg_row(
    record_type: str = "decision",
    content_json: str = '{"decision": "sample"}',
    agent_role: str = "control",
) -> dict[str, Any]:
    """Return a plain dict that mimics what dict(asyncpg_record) produces."""
    return {
        "id": uuid.uuid4(),
        "session_id": uuid.uuid4(),
        "record_type": record_type,
        "content_json": content_json,
        "agent_role": agent_role,
        "created_at": datetime.now(timezone.utc),
        "outcome": None,
    }


# ---------------------------------------------------------------------------
# search() — bare-string path (T-688)
# ---------------------------------------------------------------------------


async def test_decision_memory_search_bare_string_returns_recent_records() -> None:
    """search() with a natural-language string (not JSON) calls conn.fetch and returns rows."""
    fake_rows = [_fake_asyncpg_row()]
    pool, conn = _make_fake_pool(fetch_return=fake_rows)

    with patch("packages.persistence.db.get_pool", AsyncMock(return_value=pool)):
        store = DecisionMemoryStore()
        results = await store.search("What are today's supply chain exceptions?", k=3)

    conn.fetch.assert_called_once()
    assert len(results) == 1
    # Verify the returned dict has the expected keys
    assert "record_type" in results[0]
    assert "content_json" in results[0]


async def test_decision_memory_search_json_without_session_id_returns_empty() -> None:
    """search() with valid JSON that has no 'session_id' key returns [] and does NOT call fetch."""
    pool, conn = _make_fake_pool(fetch_return=[_fake_asyncpg_row()])

    with patch("packages.persistence.db.get_pool", AsyncMock(return_value=pool)):
        store = DecisionMemoryStore()
        results = await store.search(json.dumps({"foo": "bar"}), k=5)

    assert results == []
    conn.fetch.assert_not_called()


async def test_decision_memory_search_empty_string_returns_recent_records() -> None:
    """search() with an empty string takes the bare-string path and calls conn.fetch."""
    fake_rows = [_fake_asyncpg_row(), _fake_asyncpg_row()]
    pool, conn = _make_fake_pool(fetch_return=fake_rows)

    with patch("packages.persistence.db.get_pool", AsyncMock(return_value=pool)):
        store = DecisionMemoryStore()
        results = await store.search("", k=5)

    conn.fetch.assert_called_once()
    assert len(results) == 2
