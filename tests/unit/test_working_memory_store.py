from __future__ import annotations

"""Unit tests for WorkingMemoryStore (P41-B-02, T-292).

All tests inject a stub AgentStepsRepository — no real DB is touched.
"""

import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.memory import WorkingMemoryStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_stub_repo(
    created_rows: list[dict[str, Any]] | None = None,
) -> MagicMock:
    """Return a mock AgentStepsRepository with controllable return values."""
    repo = MagicMock()
    repo.create = AsyncMock(return_value=None)
    repo.list_recent_by_session = AsyncMock(return_value=created_rows or [])
    return repo


def _sample_session_id() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def test_working_memory_store_instantiates_without_repo() -> None:
    # Verify the default constructor path does not raise.
    # (The default repo would need a DB; this just checks the object is created.)
    store = WorkingMemoryStore(repo=_make_stub_repo())
    assert store is not None


# ---------------------------------------------------------------------------
# write()
# ---------------------------------------------------------------------------


async def test_write_calls_repo_create_with_required_fields() -> None:
    repo = _make_stub_repo()
    store = WorkingMemoryStore(repo=repo)
    session_id = _sample_session_id()

    await store.write({"session_id": session_id, "content": "tool result payload"})

    repo.create.assert_called_once()
    call_kwargs = repo.create.call_args.kwargs
    assert call_kwargs["session_id"] == session_id
    assert call_kwargs["input_json"] == {"content": "tool result payload"}


async def test_write_defaults_step_type_to_tool_result() -> None:
    repo = _make_stub_repo()
    store = WorkingMemoryStore(repo=repo)

    await store.write({"session_id": _sample_session_id(), "content": "x"})

    call_kwargs = repo.create.call_args.kwargs
    assert call_kwargs["step_type"] == "tool_result"


async def test_write_defaults_specialist_role_to_control() -> None:
    repo = _make_stub_repo()
    store = WorkingMemoryStore(repo=repo)

    await store.write({"session_id": _sample_session_id(), "content": "x"})

    call_kwargs = repo.create.call_args.kwargs
    assert call_kwargs["specialist_role"] == "control"


async def test_write_respects_custom_step_type() -> None:
    repo = _make_stub_repo()
    store = WorkingMemoryStore(repo=repo)

    await store.write(
        {"session_id": _sample_session_id(), "content": "x", "step_type": "llm_call"}
    )

    call_kwargs = repo.create.call_args.kwargs
    assert call_kwargs["step_type"] == "llm_call"


async def test_write_respects_custom_specialist_role() -> None:
    repo = _make_stub_repo()
    store = WorkingMemoryStore(repo=repo)

    await store.write(
        {"session_id": _sample_session_id(), "content": "x", "specialist_role": "supply_chain"}
    )

    call_kwargs = repo.create.call_args.kwargs
    assert call_kwargs["specialist_role"] == "supply_chain"


async def test_write_passes_started_at_as_datetime() -> None:
    repo = _make_stub_repo()
    store = WorkingMemoryStore(repo=repo)

    await store.write({"session_id": _sample_session_id(), "content": "x"})

    call_kwargs = repo.create.call_args.kwargs
    assert isinstance(call_kwargs["started_at"], datetime)


# ---------------------------------------------------------------------------
# search()
# ---------------------------------------------------------------------------


async def test_search_returns_empty_list_for_non_session_prefix() -> None:
    repo = _make_stub_repo()
    store = WorkingMemoryStore(repo=repo)

    result = await store.search("some arbitrary query")

    assert result == []
    repo.list_recent_by_session.assert_not_called()


async def test_search_returns_empty_list_for_bare_session_word() -> None:
    repo = _make_stub_repo()
    store = WorkingMemoryStore(repo=repo)

    result = await store.search("session")

    assert result == []


async def test_search_calls_repo_with_parsed_session_id() -> None:
    session_id = _sample_session_id()
    repo = _make_stub_repo()
    store = WorkingMemoryStore(repo=repo)

    await store.search(f"session:{session_id}", k=3)

    repo.list_recent_by_session.assert_called_once_with(session_id=session_id, limit=3)


async def test_search_forwards_k_to_repo_as_limit() -> None:
    session_id = _sample_session_id()
    repo = _make_stub_repo()
    store = WorkingMemoryStore(repo=repo)

    await store.search(f"session:{session_id}", k=7)

    call_kwargs = repo.list_recent_by_session.call_args.kwargs
    assert call_kwargs["limit"] == 7


async def test_search_default_k_is_five() -> None:
    session_id = _sample_session_id()
    repo = _make_stub_repo()
    store = WorkingMemoryStore(repo=repo)

    await store.search(f"session:{session_id}")

    call_kwargs = repo.list_recent_by_session.call_args.kwargs
    assert call_kwargs["limit"] == 5


async def test_search_returns_rows_from_repo() -> None:
    session_id = _sample_session_id()
    fake_rows = [
        {
            "step_id": str(uuid.uuid4()),
            "session_id": session_id,
            "step_type": "tool_result",
            "content": "artifact A",
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
        {
            "step_id": str(uuid.uuid4()),
            "session_id": session_id,
            "step_type": "tool_result",
            "content": "artifact B",
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    ]
    repo = _make_stub_repo(created_rows=fake_rows)
    store = WorkingMemoryStore(repo=repo)

    result = await store.search(f"session:{session_id}", k=5)

    assert result == fake_rows


async def test_search_empty_session_id_portion_still_calls_repo() -> None:
    """Query 'session:' (empty id) is forwarded as-is; repo decides validity."""
    repo = _make_stub_repo()
    store = WorkingMemoryStore(repo=repo)

    await store.search("session:", k=2)

    repo.list_recent_by_session.assert_called_once_with(session_id="", limit=2)
