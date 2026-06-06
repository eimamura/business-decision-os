from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID, uuid4

import openai
from pydantic import BaseModel, Field

from packages.memory.decision import DecisionMemoryStore
from packages.memory.working import WorkingMemoryStore

# ---------------------------------------------------------------------------
# Legacy record models — used by PgVectorMemoryStore and existing API code
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Legacy conversation-turn record model
# (formerly named ShortTermMemory before P41 typed-store redesign)
# ---------------------------------------------------------------------------


class ConversationTurn(BaseModel):
    """A single conversation message stored as a short-term memory record."""

    id: UUID = Field(default_factory=uuid4)
    session_id: UUID | None = None
    role: Literal["user", "assistant", "system"]
    content: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Typed Memory Store — abstract base classes (P41, public interface)
#
# Signatures are LOCKED. Any change requires an ADR.
#   write(record: dict) -> None
#   search(query: str, k: int = 5) -> list[dict]
# ---------------------------------------------------------------------------


class MemoryStore(ABC):
    """Base protocol for all typed memory stores."""

    @abstractmethod
    def write(self, record: dict[str, Any]) -> None: ...

    @abstractmethod
    def search(self, query: str, k: int = 5) -> list[dict[str, Any]]: ...


class ShortTermMemory(MemoryStore):
    """Recent conversation turns and in-flight context."""


class WorkingMemory(MemoryStore):
    """Session task runs, tool results, intermediate artifacts."""


class LongTermMemory(MemoryStore):
    """Aggregated historical patterns and domain knowledge."""


class DecisionMemory(MemoryStore):
    """Past decisions and failure records with record_type field."""


class UserMemory(MemoryStore):
    """User preferences and interaction history."""


class DomainMemory(MemoryStore):
    """Business rules and domain knowledge (e.g. KPI thresholds)."""


# ---------------------------------------------------------------------------
# PgVector-backed store (legacy async interface — used by existing API code)
# ---------------------------------------------------------------------------


async def _get_embedding(text: str) -> list[float]:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY environment variable is not set. "
            "Set it to use PgVectorMemoryStore."
        )
    client = openai.AsyncOpenAI(api_key=api_key)
    response = await client.embeddings.create(
        model="text-embedding-3-small",
        input=text,
    )
    embedding: list[float] = response.data[0].embedding
    return embedding


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
            memory.embedding
            if memory.embedding is not None
            else await _get_embedding(memory.content)
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
        query_embedding = await _get_embedding(query_text)
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


# ---------------------------------------------------------------------------
# Legacy in-memory stub (async interface — used by existing API + test code)
# ---------------------------------------------------------------------------


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


__all__ = [
    # Legacy record models
    "Memory",
    "MemoryQuery",
    "ConversationTurn",
    # Typed store base classes (P41 public interface)
    "MemoryStore",
    "ShortTermMemory",
    "WorkingMemory",
    "LongTermMemory",
    "DecisionMemory",
    "UserMemory",
    "DomainMemory",
    # Physical async implementations (P41-B-02+)
    "WorkingMemoryStore",
    "DecisionMemoryStore",
    # Concrete implementations
    "PgVectorMemoryStore",
    "StubMemoryStore",
    # Internal helpers (exported for test patching)
    "_get_embedding",
]
