from __future__ import annotations

"""Unit tests for LongTermMemoryStore (P47-B-03, T-334).

All tests inject a mock asyncpg pool — no real DB is touched.
Mock target: packages.persistence.db.get_pool (imported lazily inside _get_pool()).
"""

from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.memory.long_term import LongTermMemoryStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_fake_pool(
    fetch_return: list[Any] | None = None,
    execute_side_effect: Exception | None = None,
) -> tuple[MagicMock, MagicMock]:
    """Return (pool, conn) where conn has mocked execute and fetch.

    *fetch_return*  — rows returned by conn.fetch (default: empty list)
    *execute_side_effect* — if set, conn.execute raises this exception
    """
    mock_conn = MagicMock()
    if execute_side_effect is not None:
        mock_conn.execute = AsyncMock(side_effect=execute_side_effect)
    else:
        mock_conn.execute = AsyncMock(return_value=None)

    mock_conn.fetch = AsyncMock(return_value=fetch_return if fetch_return is not None else [])

    @asynccontextmanager
    async def _fake_acquire():  # type: ignore[return]
        yield mock_conn

    mock_pool = MagicMock()
    mock_pool.acquire = _fake_acquire
    return mock_pool, mock_conn


def _fake_row(
    memory_type: str = "long_term",
    scope: str = "",
    content: str = "sample content",
) -> MagicMock:
    """Return a dict-like object that mimics an asyncpg Record row."""
    import uuid
    from datetime import datetime, timezone

    row: dict[str, Any] = {
        "id": uuid.uuid4(),
        "memory_type": memory_type,
        "scope": scope,
        "content": content,
        "metadata_json": "{}",
        "created_at": datetime.now(timezone.utc),
    }
    record = MagicMock()
    record.__getitem__ = lambda _, k: row[k]
    return record


# ---------------------------------------------------------------------------
# write() tests
# ---------------------------------------------------------------------------


async def test_write_inserts_memory_type_content_scope() -> None:
    """write() passes memory_type, content, and scope to conn.execute."""
    pool, conn = _make_fake_pool()
    with patch("packages.persistence.db.get_pool", AsyncMock(return_value=pool)):
        store = LongTermMemoryStore()
        await store.write(
            {"memory_type": "long_term", "content": "pattern A", "scope": "sku-001"}
        )

    conn.execute.assert_called_once()
    call_args = conn.execute.call_args.args
    # call_args: (sql, memory_type, scope, content, metadata_json)
    assert "long_term" in call_args
    assert "pattern A" in call_args
    assert "sku-001" in call_args


async def test_write_uses_empty_string_scope_by_default() -> None:
    """write() defaults scope to '' when not provided."""
    pool, conn = _make_fake_pool()
    with patch("packages.persistence.db.get_pool", AsyncMock(return_value=pool)):
        store = LongTermMemoryStore()
        await store.write({"memory_type": "user", "content": "pref X"})

    call_args = conn.execute.call_args.args
    # Positional args: sql, memory_type, scope, content, metadata_json
    # scope is the 3rd positional argument (index 2 after the SQL string)
    assert call_args[2] == ""


async def test_write_db_error_propagates() -> None:
    """A RuntimeError raised by conn.execute propagates out of write()."""
    pool, _conn = _make_fake_pool(execute_side_effect=RuntimeError("db error"))
    with patch("packages.persistence.db.get_pool", AsyncMock(return_value=pool)):
        store = LongTermMemoryStore()
        with pytest.raises(RuntimeError, match="db error"):
            await store.write({"memory_type": "long_term", "content": "x"})


# ---------------------------------------------------------------------------
# search() tests
# ---------------------------------------------------------------------------


async def test_search_type_prefix_filters_by_memory_type() -> None:
    """search('type:long_term') passes 'long_term' as a filter to conn.fetch."""
    pool, conn = _make_fake_pool(fetch_return=[_fake_row()])
    with patch("packages.persistence.db.get_pool", AsyncMock(return_value=pool)):
        store = LongTermMemoryStore()
        await store.search("type:long_term", k=5)

    conn.fetch.assert_called_once()
    fetch_args = conn.fetch.call_args.args
    # fetch_args: (sql, filter_value, k)
    assert "long_term" in fetch_args


async def test_search_scope_prefix_filters_by_scope() -> None:
    """search('scope:sku-001') passes 'sku-001' as a filter to conn.fetch."""
    pool, conn = _make_fake_pool(fetch_return=[_fake_row(scope="sku-001")])
    with patch("packages.persistence.db.get_pool", AsyncMock(return_value=pool)):
        store = LongTermMemoryStore()
        await store.search("scope:sku-001", k=3)

    conn.fetch.assert_called_once()
    fetch_args = conn.fetch.call_args.args
    assert "sku-001" in fetch_args


async def test_search_bare_query_returns_records_without_filter() -> None:
    """A bare text query returns rows without raising and without a WHERE filter."""
    fake_rows = [_fake_row(content="result 1"), _fake_row(content="result 2")]
    pool, conn = _make_fake_pool(fetch_return=fake_rows)
    with patch("packages.persistence.db.get_pool", AsyncMock(return_value=pool)):
        store = LongTermMemoryStore()
        results = await store.search("some text", k=2)

    assert len(results) == 2
    conn.fetch.assert_called_once()


async def test_search_empty_query_returns_records_without_error() -> None:
    """An empty query string does not raise and conn.fetch is still called."""
    pool, conn = _make_fake_pool(fetch_return=[])
    with patch("packages.persistence.db.get_pool", AsyncMock(return_value=pool)):
        store = LongTermMemoryStore()
        results = await store.search("", k=5)

    conn.fetch.assert_called_once()
    assert isinstance(results, list)
