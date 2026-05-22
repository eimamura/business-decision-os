from __future__ import annotations

import uuid
from typing import Any

from packages.persistence.db import get_pool


class DecisionSessionRepository:
    async def create(self, session_id: str, user_id: str | None, goal: str) -> str:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO decision_sessions (id, user_id, goal, status)
                VALUES ($1, $2, $3, 'pending')
                """,
                uuid.UUID(session_id),
                uuid.UUID(user_id) if user_id else None,
                goal,
            )
        return session_id

    async def get(self, session_id: str) -> dict[str, Any] | None:
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, user_id, goal, title, status, created_at, updated_at"
                " FROM decision_sessions WHERE id = $1",
                uuid.UUID(session_id),
            )
        if row is None:
            return None
        return dict(row)

    async def update(self, session_id: str, **kwargs: Any) -> None:
        if not kwargs:
            return
        pool = await get_pool()
        allowed = {"status", "updated_at"}
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return
        set_clauses = ", ".join(
            f"{col} = ${i + 2}" for i, col in enumerate(fields)
        )
        values = list(fields.values())
        async with pool.acquire() as conn:
            await conn.execute(
                f"UPDATE decision_sessions SET {set_clauses} WHERE id = $1",
                uuid.UUID(session_id),
                *values,
            )

    async def list_sessions(self, user_id: str | None = None) -> list[dict[str, Any]]:
        pool = await get_pool()
        async with pool.acquire() as conn:
            if user_id is not None:
                rows = await conn.fetch(
                    "SELECT id, user_id, goal, title, status, created_at, updated_at"
                    " FROM decision_sessions WHERE user_id = $1"
                    " ORDER BY created_at DESC",
                    uuid.UUID(user_id),
                )
            else:
                rows = await conn.fetch(
                    "SELECT id, user_id, goal, title, status, created_at, updated_at"
                    " FROM decision_sessions ORDER BY created_at DESC"
                )
        return [dict(r) for r in rows]

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
    ) -> str:
        message_id = str(uuid.uuid4())
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO session_messages
                    (id, session_id, role, content, input_tokens, output_tokens)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                uuid.UUID(message_id),
                uuid.UUID(session_id),
                role,
                content,
                input_tokens,
                output_tokens,
            )
        return message_id

    async def get_messages(
        self, session_id: str, limit: int = 40
    ) -> list[dict[str, Any]]:
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, role, content, feedback, created_at
                FROM session_messages
                WHERE session_id = $1
                ORDER BY created_at ASC
                LIMIT $2
                """,
                uuid.UUID(session_id),
                limit,
            )
        return [dict(r) for r in rows]

    async def delete_session(self, session_id: str) -> bool:
        pool = await get_pool()
        async with pool.acquire() as conn:
            deleted = await conn.fetchval(
                "DELETE FROM decision_sessions WHERE id = $1 RETURNING id",
                uuid.UUID(session_id),
            )
        return deleted is not None

    async def set_title(self, session_id: str, title: str) -> None:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE decision_sessions SET title = $2, updated_at = now() WHERE id = $1",
                uuid.UUID(session_id),
                title,
            )

    async def set_message_feedback(
        self, message_id: str, feedback: int, session_id: str
    ) -> bool:
        pool = await get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE session_messages
                SET feedback = $3
                WHERE id = $1 AND session_id = $2
                """,
                uuid.UUID(message_id),
                uuid.UUID(session_id),
                feedback,
            )
        return bool(result == "UPDATE 1")
