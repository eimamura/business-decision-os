from __future__ import annotations

import json
import logging
from typing import Any

import asyncpg

from packages.schemas.context_packs import ContextLogRead

_log = logging.getLogger(__name__)


def _load_json_field(raw: Any) -> Any:
    """Coerce an asyncpg JSONB result to a Python object.

    asyncpg may return JSONB columns as a JSON string or a pre-decoded Python object,
    depending on the codec registration.  This helper normalises both cases.
    """
    if isinstance(raw, str):
        return json.loads(raw)
    # Already decoded by asyncpg (list, dict, etc.)
    return raw


class ContextLogRepository:
    """Repository for context_log table."""

    async def create(
        self,
        *,
        session_id: str,
        use_case_id: str,
        intent: str,
        required_tools: list[str],
        prohibited_tools: list[str],
        context_pack_json: dict[str, Any],
        conn: asyncpg.Connection,
    ) -> ContextLogRead:
        row = await conn.fetchrow(
            """
            INSERT INTO context_log
                (session_id, use_case_id, intent,
                 required_tools, prohibited_tools, context_pack_json)
            VALUES ($1, $2, $3, $4::jsonb, $5::jsonb, $6::jsonb)
            RETURNING id, session_id, use_case_id, intent, required_tools, prohibited_tools,
                      context_pack_json, created_at
            """,
            session_id,
            use_case_id,
            intent,
            json.dumps(required_tools),
            json.dumps(prohibited_tools),
            json.dumps(context_pack_json),
        )
        if row is None:
            raise RuntimeError("INSERT INTO context_log returned no row")
        return ContextLogRead(
            id=row["id"],
            session_id=row["session_id"],
            use_case_id=row["use_case_id"],
            intent=row["intent"],
            required_tools=_load_json_field(row["required_tools"]),
            prohibited_tools=_load_json_field(row["prohibited_tools"]),
            context_pack_json=_load_json_field(row["context_pack_json"]),
            created_at=row["created_at"],
        )

    async def list_by_session(
        self,
        session_id: str,
        *,
        limit: int = 50,
        conn: asyncpg.Connection,
    ) -> list[ContextLogRead]:
        rows = await conn.fetch(
            """
            SELECT id, session_id, use_case_id, intent, required_tools, prohibited_tools,
                   context_pack_json, created_at
            FROM context_log
            WHERE session_id = $1
            ORDER BY created_at DESC
            LIMIT $2
            """,
            session_id,
            limit,
        )
        return [
            ContextLogRead(
                id=r["id"],
                session_id=r["session_id"],
                use_case_id=r["use_case_id"],
                intent=r["intent"],
                required_tools=_load_json_field(r["required_tools"]),
                prohibited_tools=_load_json_field(r["prohibited_tools"]),
                context_pack_json=_load_json_field(r["context_pack_json"]),
                created_at=r["created_at"],
            )
            for r in rows
        ]

    async def list_by_use_case(
        self,
        use_case_id: str,
        *,
        limit: int = 50,
        conn: asyncpg.Connection,
    ) -> list[ContextLogRead]:
        rows = await conn.fetch(
            """
            SELECT id, session_id, use_case_id, intent, required_tools, prohibited_tools,
                   context_pack_json, created_at
            FROM context_log
            WHERE use_case_id = $1
            ORDER BY created_at DESC
            LIMIT $2
            """,
            use_case_id,
            limit,
        )
        return [
            ContextLogRead(
                id=r["id"],
                session_id=r["session_id"],
                use_case_id=r["use_case_id"],
                intent=r["intent"],
                required_tools=_load_json_field(r["required_tools"]),
                prohibited_tools=_load_json_field(r["prohibited_tools"]),
                context_pack_json=_load_json_field(r["context_pack_json"]),
                created_at=r["created_at"],
            )
            for r in rows
        ]

    async def list_recent(
        self,
        *,
        limit: int = 50,
        conn: asyncpg.Connection,
    ) -> list[ContextLogRead]:
        rows = await conn.fetch(
            """
            SELECT id, session_id, use_case_id, intent, required_tools, prohibited_tools,
                   context_pack_json, created_at
            FROM context_log
            ORDER BY created_at DESC
            LIMIT $1
            """,
            limit,
        )
        return [
            ContextLogRead(
                id=r["id"],
                session_id=r["session_id"],
                use_case_id=r["use_case_id"],
                intent=r["intent"],
                required_tools=_load_json_field(r["required_tools"]),
                prohibited_tools=_load_json_field(r["prohibited_tools"]),
                context_pack_json=_load_json_field(r["context_pack_json"]),
                created_at=r["created_at"],
            )
            for r in rows
        ]
