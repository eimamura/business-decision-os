"""Physical async implementation of the DecisionMemory store.

T-294/T-295 — DecisionMemoryStore backed by the decision_log table.

DecisionMemoryStore is a standalone async class that does NOT inherit from DecisionMemory.
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

_VALID_RECORD_TYPES = frozenset({"decision", "failure"})


class DecisionMemoryStore:
    """Async physical implementation of DecisionMemory backed by the decision_log table."""

    def __init__(self, pool: Any | None = None) -> None:
        # asyncpg.Pool | None — typed as Any to avoid a hard import at module level
        self._pool = pool

    async def _get_pool(self) -> Any:
        if self._pool is None:
            from packages.persistence.db import get_pool

            self._pool = await get_pool()
        return self._pool

    async def write(self, record: dict[str, Any]) -> None:
        """Insert a row into decision_log.

        Required keys:
          session_id  (str)                  — UUID of the owning session
          content_json (dict | str)          — JSON blob of the decision/failure record
          record_type  ("decision"|"failure") — discriminator column

        Optional keys:
          agent_role (str, default "control")
        """
        session_id: str = record["session_id"]
        raw_content = record["content_json"]
        record_type: str = record["record_type"]
        agent_role: str = record.get("agent_role", "control")

        if record_type not in _VALID_RECORD_TYPES:
            raise ValueError(
                f"record_type must be one of {sorted(_VALID_RECORD_TYPES)!r}; got {record_type!r}"
            )

        content_json_str: str
        if isinstance(raw_content, str):
            content_json_str = raw_content
        else:
            content_json_str = json.dumps(raw_content)

        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO decision_log (session_id, record_type, content_json, agent_role)
                VALUES ($1::uuid, $2, $3, $4)
                """,
                session_id,
                record_type,
                content_json_str,
                agent_role,
            )

        _log.debug(
            "DecisionMemoryStore.write: session_id=%s record_type=%s agent_role=%s",
            session_id,
            record_type,
            agent_role,
        )

    async def set_latest_outcome(self, session_id: str, outcome: int) -> bool:
        """Set the outcome column on the most recent decision record for the session.

        Parameters
        ----------
        session_id:
            UUID string of the owning session.
        outcome:
            Must be 1 (positive) or -1 (negative). Raises ValueError otherwise.

        Returns
        -------
        True if a row was updated, False if no decision record exists for the session.
        """
        if outcome not in (1, -1):
            raise ValueError(f"outcome must be 1 or -1; got {outcome!r}")

        pool = await self._get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE decision_log
                SET outcome = $1
                WHERE id = (
                    SELECT id
                    FROM decision_log
                    WHERE session_id = $2::uuid
                      AND record_type = 'decision'
                    ORDER BY created_at DESC
                    LIMIT 1
                )
                """,
                outcome,
                session_id,
            )

        # asyncpg returns a string like "UPDATE 1" or "UPDATE 0"
        updated: bool = str(result).endswith("1")
        _log.debug(
            "DecisionMemoryStore.set_latest_outcome: session_id=%s outcome=%s updated=%s",
            session_id,
            outcome,
            updated,
        )
        return updated

    async def search(self, query: str, k: int = 5) -> list[dict[str, Any]]:
        """Return the k most recent decision_log rows matching the query.

        Query format: a JSON string (or plain string) with at least a "session_id" key.
        Optionally a "record_type" key to filter by "decision" or "failure".

        Bare-string fallback (P120/T-687): when the query is not valid JSON (e.g. a
        natural-language instruction passed by _inject_past_decisions()), session_id
        cannot be extracted. In that case we return the k most recent records across
        all sessions (recency fallback). This matches the MVP note in the module
        docstring: search() uses recency-ordered fallback without pgvector.

        If session_id cannot be parsed from a *valid-JSON* query, returns [] without
        error (malformed-JSON guard unchanged).

        Returned dicts contain all column values:
          id, session_id, record_type, content_json, agent_role, created_at, outcome.
        """
        session_id: str | None = None
        record_type_filter: str | None = None
        bare_string: bool = False

        try:
            parsed = json.loads(query)
            if isinstance(parsed, dict):
                session_id = parsed.get("session_id")
                record_type_filter = parsed.get("record_type")
        except (json.JSONDecodeError, ValueError):
            bare_string = True

        if not session_id:
            if bare_string:
                # Natural-language query (e.g. task.instruction) — use recency fallback
                _log.debug(
                    "DecisionMemoryStore.search: bare-string query %r"
                    " — returning %d recent records",
                    query,
                    k,
                )
                pool = await self._get_pool()
                async with pool.acquire() as conn:
                    rows = await conn.fetch(
                        """
                        SELECT id, session_id, record_type, content_json, agent_role,
                               created_at, outcome
                        FROM decision_log
                        ORDER BY created_at DESC
                        LIMIT $1
                        """,
                        k,
                    )
                return [dict(row) for row in rows]
            # JSON parsed but no session_id — malformed query; return empty
            _log.debug(
                "DecisionMemoryStore.search: no session_id found in query %r — returning []",
                query,
            )
            return []

        pool = await self._get_pool()
        async with pool.acquire() as conn:
            if record_type_filter is not None:
                rows = await conn.fetch(
                    """
                    SELECT id, session_id, record_type, content_json, agent_role, created_at,
                           outcome
                    FROM decision_log
                    WHERE session_id = $1::uuid
                      AND record_type = $2
                    ORDER BY created_at DESC
                    LIMIT $3
                    """,
                    session_id,
                    record_type_filter,
                    k,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT id, session_id, record_type, content_json, agent_role, created_at,
                           outcome
                    FROM decision_log
                    WHERE session_id = $1::uuid
                    ORDER BY created_at DESC
                    LIMIT $2
                    """,
                    session_id,
                    k,
                )

        results: list[dict[str, Any]] = [dict(row) for row in rows]
        _log.debug(
            "DecisionMemoryStore.search: session_id=%s record_type_filter=%s returned %d rows",
            session_id,
            record_type_filter,
            len(results),
        )
        return results
