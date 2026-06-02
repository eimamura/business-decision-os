from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest


# ---------------------------------------------------------------------------
# Helpers — fake asyncpg record and pool
# ---------------------------------------------------------------------------


def _fake_record(data: dict[str, Any]) -> MagicMock:
    """Return a MagicMock that behaves like an asyncpg Record for dict()."""
    record = MagicMock()
    record.keys.return_value = list(data.keys())
    record.__iter__ = MagicMock(return_value=iter(data.items()))
    # Make dict(record) work by forwarding to a real dict
    record.__class__ = type("FakeRecord", (dict,), {})(data).__class__
    # Simplest approach: use a real dict subclass
    class _Row(dict):  # noqa: N801
        pass
    row = _Row(data)
    return row  # type: ignore[return-value]


def _make_fake_pool(fetchrow_return: Any = None) -> MagicMock:
    """Return a mock asyncpg pool whose acquire() context manager exposes a
    connection with a mocked fetchrow / execute / fetch."""
    mock_conn = MagicMock()
    mock_conn.fetchrow = AsyncMock(return_value=fetchrow_return)
    mock_conn.fetch = AsyncMock(return_value=[])
    mock_conn.execute = AsyncMock(return_value=None)

    @asynccontextmanager
    async def _fake_acquire():  # type: ignore[return]
        yield mock_conn

    mock_pool = MagicMock()
    mock_pool.acquire = _fake_acquire
    return mock_pool


# ---------------------------------------------------------------------------
# create()
# ---------------------------------------------------------------------------


async def test_create_returns_dict_with_id() -> None:
    """JobsRepository.create must return a dict that contains an 'id' key."""
    from packages.persistence.jobs_repo import JobsRepository

    expected_id = uuid4()
    fake_row = {
        "id": expected_id,
        "session_id": uuid4(),
        "status": "pending_approval",
        "job_type": "simulate",
        "params_json": "{}",
        "approval_id": None,
        "created_at": None,
    }
    mock_pool = _make_fake_pool(fetchrow_return=fake_row)

    with patch("packages.persistence.jobs_repo.get_pool", AsyncMock(return_value=mock_pool)):
        repo = JobsRepository()
        result = await repo.create(
            session_id=uuid4(),
            job_type="simulate",
            params={"horizon": 30},
        )

    assert isinstance(result, dict)
    assert "id" in result
    assert result["id"] == expected_id


# ---------------------------------------------------------------------------
# update_status()
# ---------------------------------------------------------------------------


async def test_update_status_terminal_includes_completed_at_in_query() -> None:
    """The SQL used by update_status must include 'CASE WHEN' and 'now()' for terminal states."""
    from packages.persistence.jobs_repo import JobsRepository

    job_id = uuid4()
    fake_row = {
        "id": job_id,
        "status": "completed",
        "result_json": None,
        "error": None,
        "input_tokens": 0,
        "output_tokens": 0,
        "cost_usd": 0.0,
        "completed_at": None,
    }

    captured_sql: list[str] = []
    mock_conn = MagicMock()

    async def _capturing_fetchrow(sql: str, *args: Any) -> Any:
        captured_sql.append(sql)
        return fake_row

    mock_conn.fetchrow = _capturing_fetchrow

    @asynccontextmanager
    async def _fake_acquire():  # type: ignore[return]
        yield mock_conn

    mock_pool = MagicMock()
    mock_pool.acquire = _fake_acquire

    with patch("packages.persistence.jobs_repo.get_pool", AsyncMock(return_value=mock_pool)):
        repo = JobsRepository()
        await repo.update_status(job_id=job_id, status="completed", result={"ok": True})

    assert captured_sql, "fetchrow was never called"
    # Normalize whitespace so multi-line formatting doesn't affect substring matching
    sql_normalized = " ".join(captured_sql[0].split())
    assert "CASE WHEN" in sql_normalized
    assert "now()" in sql_normalized


# ---------------------------------------------------------------------------
# get_by_approval_id()
# ---------------------------------------------------------------------------


async def test_get_by_approval_id_returns_none_when_not_found() -> None:
    """get_by_approval_id must return None when fetchrow returns None."""
    from packages.persistence.jobs_repo import JobsRepository

    mock_pool = _make_fake_pool(fetchrow_return=None)

    with patch("packages.persistence.jobs_repo.get_pool", AsyncMock(return_value=mock_pool)):
        repo = JobsRepository()
        result = await repo.get_by_approval_id(uuid4())

    assert result is None
