from __future__ import annotations

import os
from uuid import uuid4

import pytest

from packages.memory import Memory, MemoryQuery, PgVectorMemoryStore


# Synthetic unit vector — all dims except [0] are 0; both write and search
# get the same embedding so cosine similarity == 1.0.
_UNIT_VEC: list[float] = [1.0] + [0.0] * 1535


skipif_no_db = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="requires DATABASE_URL — run with Docker Compose",
)


@skipif_no_db
async def test_memory_write_and_search(monkeypatch: pytest.MonkeyPatch) -> None:
    """Write a Memory to the real DB and retrieve it via vector search."""
    import packages.memory as mem_module

    async def _stub_embed(text: str) -> list[float]:
        return _UNIT_VEC

    monkeypatch.setattr(mem_module, "_get_embedding", _stub_embed)

    raw_url = os.environ["DATABASE_URL"]
    # asyncpg does not accept SQLAlchemy's `postgresql+asyncpg://` prefix;
    # normalize it here the same way packages/persistence/db.py does.
    database_url = raw_url.replace("postgresql+asyncpg://", "postgresql://")
    store = PgVectorMemoryStore(database_url)

    mem = Memory(
        id=uuid4(),
        scope="global",
        type="decision",
        content="reduce safety stock for SKU-001",
        metadata={},
        created_at="2026-06-02T00:00:00+00:00",
    )
    await store.write(mem)
    results = await store.search(MemoryQuery(query_text="safety stock reduction", k=1))
    assert len(results) >= 1
    _, similarity = results[0]
    assert similarity > 0.7


