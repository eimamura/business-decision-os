"""Physical async implementation of the LongTermMemory store.

T-332 — LongTermMemoryStore backed by the long_term_memory table.

LongTermMemoryStore is a standalone async class that does NOT inherit from LongTermMemory.
The abstract typed bases have sync signatures (locked per AGENTS.md); all physical DB
operations are async. Use a stub or unittest.mock for unit tests.

MVP note: search() uses recency-ordered fallback (no pgvector). Real pgvector similarity
search is deferred to Post-MVP once the pgvector extension is enabled in production.
"""

from __future__ import annotations

import json
import logging
from typing import Any

_log = logging.getLogger(__name__)


class LongTermMemoryStore:
    """Async physical implementation of LongTermMemory backed by the long_term_memory table."""

    def __init__(self, pool: Any | None = None) -> None:
        # asyncpg.Pool | None — typed as Any to avoid a hard import at module level
        self._pool = pool

    async def _get_pool(self) -> Any:
        if self._pool is None:
            from packages.persistence.db import get_pool

            self._pool = await get_pool()
        return self._pool

    async def write(self, record: dict[str, Any]) -> None:
        """Insert a row into long_term_memory.

        Required keys:
          memory_type (str) — e.g. "long_term", "user", "domain"
          content     (str) — text content of the memory

        Optional keys:
          scope    (str,  default "")  — namespace for the memory
          metadata (dict, default {})  — arbitrary JSON metadata
        """
        memory_type: str = record["memory_type"]
        content: str = record["content"]
        scope: str = record.get("scope", "")
        metadata_json: str = json.dumps(record.get("metadata") or {})

        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO long_term_memory (memory_type, scope, content, metadata_json)
                VALUES ($1, $2, $3, $4)
                """,
                memory_type,
                scope,
                content,
                metadata_json,
            )

        _log.debug(
            "LongTermMemoryStore.write: memory_type=%s scope=%s",
            memory_type,
            scope,
        )

    async def search(self, query: str, k: int = 5) -> list[dict[str, Any]]:
        """Return the k most recent long_term_memory rows matching the query.

        Query parsing:
          "type:<value>"  → WHERE memory_type = <value>
          "scope:<value>" → WHERE scope = <value>
          Any other string (including empty) → no WHERE filter

        Returned dicts contain: id (str), memory_type, scope, content,
        metadata_json, created_at (str).
        """
        memory_type_filter: str | None = None
        scope_filter: str | None = None

        stripped = query.strip()
        if stripped.startswith("type:"):
            memory_type_filter = stripped[len("type:"):]
        elif stripped.startswith("scope:"):
            scope_filter = stripped[len("scope:"):]

        pool = await self._get_pool()
        async with pool.acquire() as conn:
            if memory_type_filter is not None:
                rows = await conn.fetch(
                    """
                    SELECT id, memory_type, scope, content, metadata_json, created_at
                    FROM long_term_memory
                    WHERE memory_type = $1
                    ORDER BY created_at DESC
                    LIMIT $2
                    """,
                    memory_type_filter,
                    k,
                )
            elif scope_filter is not None:
                rows = await conn.fetch(
                    """
                    SELECT id, memory_type, scope, content, metadata_json, created_at
                    FROM long_term_memory
                    WHERE scope = $1
                    ORDER BY created_at DESC
                    LIMIT $2
                    """,
                    scope_filter,
                    k,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT id, memory_type, scope, content, metadata_json, created_at
                    FROM long_term_memory
                    ORDER BY created_at DESC
                    LIMIT $1
                    """,
                    k,
                )

        results: list[dict[str, Any]] = [
            {
                "id": str(row["id"]),
                "memory_type": row["memory_type"],
                "scope": row["scope"],
                "content": row["content"],
                "metadata_json": row["metadata_json"],
                "created_at": str(row["created_at"]),
            }
            for row in rows
        ]

        _log.debug(
            "LongTermMemoryStore.search: query=%r type_filter=%s scope_filter=%s returned %d rows",
            query,
            memory_type_filter,
            scope_filter,
            len(results),
        )
        return results
