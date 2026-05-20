from __future__ import annotations

import math
from uuid import uuid4

import pytest

from packages.memory import Memory, MemoryQuery, PgVectorMemoryStore, StubMemoryStore
from packages.memory import _make_embedding


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


def test_make_embedding_length():
    vec = _make_embedding("hello world")
    assert len(vec) == 1536


def test_make_embedding_unit_length():
    vec = _make_embedding("some text for embedding")
    magnitude = math.sqrt(sum(v * v for v in vec))
    assert abs(magnitude - 1.0) < 1e-5


def test_make_embedding_deterministic():
    vec1 = _make_embedding("deterministic test")
    vec2 = _make_embedding("deterministic test")
    assert vec1 == vec2


def test_make_embedding_different_texts_differ():
    vec1 = _make_embedding("text one")
    vec2 = _make_embedding("text two")
    assert vec1 != vec2


def test_pgvector_memory_store_instantiation():
    store = PgVectorMemoryStore("postgresql://user:pass@localhost/db")
    assert store._database_url == "postgresql://user:pass@localhost/db"
    assert store._pool is None
