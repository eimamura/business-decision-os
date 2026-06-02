from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

import pytest

from packages.memory import (
    Memory,
    MemoryQuery,
    PgVectorMemoryStore,
    StubMemoryStore,
    _get_embedding,
)


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
async def test_stub_write_and_get() -> None:
    store = StubMemoryStore()
    mem = _make_memory()
    returned_id = await store.write(mem)
    assert returned_id == mem.id
    fetched = await store.get(mem.id)
    assert fetched is not None
    assert fetched.content == "test content"


@pytest.mark.asyncio
async def test_stub_search_returns_empty() -> None:
    store = StubMemoryStore()
    mem = _make_memory()
    await store.write(mem)
    results = await store.search(MemoryQuery())
    assert results == []


@pytest.mark.asyncio
async def test_stub_get_missing_returns_none() -> None:
    store = StubMemoryStore()
    result = await store.get(uuid4())
    assert result is None


async def test_get_embedding_raises_when_api_key_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        await _get_embedding("some text")


async def test_get_embedding_calls_openai_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    fake_embedding = [0.1] * 1536
    with patch("packages.memory.openai.AsyncOpenAI") as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.embeddings.create.return_value.__class__ = type(
            "EmbeddingResponse",
            (),
            {"data": [type("Embedding", (), {"embedding": fake_embedding})()]},
        )

        async def _async_create(*args: object, **kwargs: object) -> object:
            return type(
                "EmbeddingResponse",
                (),
                {"data": [type("Embedding", (), {"embedding": fake_embedding})()]},
            )()

        mock_client.embeddings.create = _async_create
        result = await _get_embedding("hello world")
    assert result == fake_embedding
    assert len(result) == 1536


def test_pgvector_memory_store_instantiation() -> None:
    store = PgVectorMemoryStore("postgresql://user:pass@localhost/db")
    assert store._database_url == "postgresql://user:pass@localhost/db"
    assert store._pool is None
