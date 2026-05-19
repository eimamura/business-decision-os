from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from packages.memory import Memory, MemoryQuery, StubMemoryStore


def _make_memory() -> Memory:
    return Memory(
        id=uuid4(),
        scope="global",
        type="decision",
        content="test content",
        metadata={},
        created_at="2026-01-01T00:00:00Z",
    )


@pytest.mark.asyncio
async def test_stub_write_and_get():
    store = StubMemoryStore()
    mem = _make_memory()
    returned_id = await store.write(mem)
    assert returned_id == mem.id
    fetched = await store.get(mem.id)
    assert fetched is not None
    assert fetched.content == "test content"


@pytest.mark.asyncio
async def test_stub_search_returns_empty():
    store = StubMemoryStore()
    mem = _make_memory()
    await store.write(mem)
    results = await store.search(MemoryQuery())
    assert results == []


@pytest.mark.asyncio
async def test_stub_get_missing_returns_none():
    store = StubMemoryStore()
    result = await store.get(uuid4())
    assert result is None
