from __future__ import annotations

import json
import os
from types import SimpleNamespace
from uuid import uuid4

import pytest

from packages.memory import Memory, MemoryQuery, PgVectorMemoryStore
from packages.agent.orchestrator.decision import _resolve_weights_with_memory
from packages.agent.orchestrator.models import SessionGoal


# Synthetic unit vector — all dims except [0] are 0; both write and search
# get the same embedding so cosine similarity == 1.0.
_UNIT_VEC: list[float] = [1.0] + [0.0] * 1535


skipif_no_db = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="requires DATABASE_URL — run with Docker Compose",
)


@skipif_no_db
@pytest.mark.asyncio
async def test_memory_write_and_search(monkeypatch: pytest.MonkeyPatch) -> None:
    """Write a Memory to the real DB and retrieve it via vector search."""
    import packages.memory as mem_module

    async def _stub_embed(text: str) -> list[float]:
        return _UNIT_VEC

    monkeypatch.setattr(mem_module, "_get_embedding", _stub_embed)

    database_url = os.environ["DATABASE_URL"]
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


@skipif_no_db
@pytest.mark.asyncio
async def test_resolve_weights_with_memory_takes_memory_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When a relevant memory exists, _resolve_weights_with_memory returns weight_source='user_policy'."""
    import packages.memory as mem_module

    async def _stub_embed(text: str) -> list[float]:
        return _UNIT_VEC

    monkeypatch.setattr(mem_module, "_get_embedding", _stub_embed)

    database_url = os.environ["DATABASE_URL"]
    store = PgVectorMemoryStore(database_url)

    weights_data = {
        "service_level": 0.5,
        "total_supply_chain_cost": 0.3,
        "stockout_rate": 0.2,
    }
    mem = Memory(
        id=uuid4(),
        scope="global",
        type="user_policy",
        content=json.dumps({"weights": weights_data}),
        metadata={},
        created_at="2026-06-02T00:00:00+00:00",
    )
    await store.write(mem)

    goal = SessionGoal(text="reduce safety stock")
    mock_orchestrator = SimpleNamespace(_memory_store=store)
    weights, weight_source = await _resolve_weights_with_memory(mock_orchestrator, goal)
    assert weight_source == "user_policy"
    assert isinstance(weights, dict)
