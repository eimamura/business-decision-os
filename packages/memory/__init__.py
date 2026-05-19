from __future__ import annotations

from typing import Literal, Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel


class Memory(BaseModel):
    id: UUID
    scope: str
    type: Literal["decision", "forecast_error", "user_policy", "failure_case"]
    content: str
    embedding: list[float] | None = None
    metadata: dict
    created_at: str


class MemoryQuery(BaseModel):
    scope: str | None = None
    type: Literal["decision", "forecast_error", "user_policy", "failure_case"] | None = None
    query_text: str | None = None
    k: int = 5
    min_similarity: float = 0.0


class MemoryStore(Protocol):
    async def write(self, memory: Memory) -> UUID: ...
    async def search(self, query: MemoryQuery) -> list[tuple[Memory, float]]: ...
    async def get(self, id: UUID) -> Memory | None: ...


class StubMemoryStore:
    def __init__(self) -> None:
        self._store: dict[UUID, Memory] = {}

    async def write(self, memory: Memory) -> UUID:
        stored_id = memory.id if memory.id else uuid4()
        record = memory.model_copy(update={"id": stored_id})
        self._store[record.id] = record
        return record.id

    async def search(self, query: MemoryQuery) -> list[tuple[Memory, float]]:
        return []

    async def get(self, id: UUID) -> Memory | None:
        return self._store.get(id)
