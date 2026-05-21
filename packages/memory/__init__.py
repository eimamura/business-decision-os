from __future__ import annotations

import hashlib
import json
import math
import struct
from datetime import datetime, timezone
from typing import Any, Literal, Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class Memory(BaseModel):
    id: UUID
    scope: str
    type: Literal["decision", "forecast_error", "user_policy", "failure_case"]
    content: str
    embedding: list[float] | None = None
    metadata: dict[str, Any]
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


def _make_embedding(text: str) -> list[float]:
    vec: list[float] = []
    seed = text.encode()
    for i in range(192):
        h = hashlib.sha256(seed + i.to_bytes(2, "big")).digest()
        for j in range(0, 32, 4):
            val = struct.unpack_from(">f", h, j)[0]
            vec.append(0.0 if not math.isfinite(val) else val)
    mag = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / mag for v in vec]


class PgVectorMemoryStore:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._pool: Any = None

    async def _get_pool(self) -> Any:
        if self._pool is None:
            import asyncpg

            self._pool = await asyncpg.create_pool(self._database_url)
        return self._pool

    async def write(self, memory: Memory) -> UUID:
        pool = await self._get_pool()
        embedding = (
            memory.embedding if memory.embedding is not None else _make_embedding(memory.content)
        )
        embedding_str = "[" + ",".join(str(v) for v in embedding) + "]"
        record_id = memory.id if memory.id else uuid4()
        created_at = (
            datetime.fromisoformat(memory.created_at)
            if isinstance(memory.created_at, str)
            else memory.created_at
        )
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)

        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO memories
                    (id, scope, type, content, embedding, metadata_json, created_at)
                VALUES ($1, $2, $3, $4, $5::vector, $6, $7)
                """,
                record_id,
                memory.scope,
                memory.type,
                memory.content,
                embedding_str,
                json.dumps(memory.metadata),
                created_at,
            )
        return record_id

    async def search(self, query: MemoryQuery) -> list[tuple[Memory, float]]:
        pool = await self._get_pool()
        query_text = query.query_text or ""
        query_embedding = _make_embedding(query_text)
        embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

        conditions: list[str] = []
        params: list[Any] = [embedding_str, query.k]
        param_idx = 3

        if query.scope is not None:
            conditions.append(f"scope = ${param_idx}")
            params.append(query.scope)
            param_idx += 1

        if query.type is not None:
            conditions.append(f"type = ${param_idx}")
            params.append(query.type)
            param_idx += 1

        where_clause = ""
        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)

        sql = f"""
            SELECT id, scope, type, content, metadata_json, created_at,
                   1 - (embedding <=> $1::vector) AS similarity
            FROM memories
            {where_clause}
            ORDER BY embedding <=> $1::vector
            LIMIT $2
        """

        results: list[tuple[Memory, float]] = []
        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)
            for row in rows:
                similarity = float(row["similarity"])
                if similarity < query.min_similarity:
                    continue
                mem = Memory(
                    id=row["id"],
                    scope=row["scope"],
                    type=row["type"],
                    content=row["content"],
                    embedding=None,
                    metadata=(
                        json.loads(row["metadata_json"])
                        if isinstance(row["metadata_json"], str)
                        else dict(row["metadata_json"])
                    ),
                    created_at=str(row["created_at"]),
                )
                results.append((mem, similarity))
        return results

    async def get(self, id: UUID) -> Memory | None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, scope, type, content, metadata_json, created_at"
                " FROM memories WHERE id = $1",
                id,
            )
        if row is None:
            return None
        return Memory(
            id=row["id"],
            scope=row["scope"],
            type=row["type"],
            content=row["content"],
            embedding=None,
            metadata=(
                json.loads(row["metadata_json"])
                if isinstance(row["metadata_json"], str)
                else dict(row["metadata_json"])
            ),
            created_at=str(row["created_at"]),
        )


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


class ShortTermMemory(BaseModel):
    """Temporary information needed only during the current interaction."""

    id: UUID = Field(default_factory=uuid4)
    session_id: UUID | None = None
    role: Literal["user", "assistant", "system"]
    content: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class WorkingMemory(BaseModel):
    """Intermediate state, in-progress calculations, and shared state between agents."""

    id: UUID = Field(default_factory=uuid4)
    session_id: UUID | None = None
    key: str
    value: str
    agent: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class LongTermMemory(BaseModel):
    """Knowledge and context to be reused in future decisions."""

    id: UUID = Field(default_factory=uuid4)
    scope: str = "global"
    summary: str
    source: str
    embedding: list[float] | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DecisionMemory(BaseModel):
    """Decision rationale, alternatives, rejection reasons, preconditions, and past decisions."""

    id: UUID = Field(default_factory=uuid4)
    session_id: UUID | None = None
    goal: str
    chosen_action: str
    rationale: str
    alternatives: list[str] = Field(default_factory=list)
    rejection_reasons: list[str] = Field(default_factory=list)
    preconditions: list[str] = Field(default_factory=list)
    risk_level: Literal["low", "medium", "high"] = "medium"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class UserMemory(BaseModel):
    """User goals, preferences, decision tendencies, and usage context."""

    id: UUID = Field(default_factory=uuid4)
    user_id: str
    preference_key: str
    preference_value: str
    context: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DomainMemory(BaseModel):
    """Business rules, KPI definitions, domain knowledge, and historical cases."""

    id: UUID = Field(default_factory=uuid4)
    domain: str
    rule_key: str
    rule_value: str
    description: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
