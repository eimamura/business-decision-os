from __future__ import annotations

import json
import uuid
from typing import Any

from packages.persistence.db import get_pool


class SessionEventRepository:
    async def create(
        self,
        session_id: str,
        event_type: str,
        payload: dict[str, Any],
        event_id: str | None = None,
    ) -> str:
        row_id = str(uuid.uuid4())
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO session_events (id, session_id, event_type, payload, event_id)
                VALUES ($1, $2, $3, $4, $5)
                """,
                uuid.UUID(row_id),
                uuid.UUID(session_id),
                event_type,
                json.dumps(payload),
                event_id,
            )
        return row_id

    async def list_for_session(
        self, session_id: str, limit: int = 200
    ) -> list[dict[str, Any]]:
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT event_type, payload, created_at
                FROM session_events
                WHERE session_id = $1
                ORDER BY created_at ASC
                LIMIT $2
                """,
                uuid.UUID(session_id),
                limit,
            )
        return [
            {
                "event_type": row["event_type"],
                "payload": (
                    json.loads(row["payload"])
                    if isinstance(row["payload"], str)
                    else dict(row["payload"])
                ),
                "created_at": (
                    row["created_at"].isoformat()
                    if hasattr(row["created_at"], "isoformat")
                    else str(row["created_at"])
                ),
            }
            for row in rows
        ]
