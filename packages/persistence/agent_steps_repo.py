from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from packages.persistence.db import get_pool

_log = logging.getLogger(__name__)


async def make_step(
    session_id: str, step_type: str, specialist_role: str = "orchestrator"
) -> uuid.UUID | None:
    """Create an agent_steps row for any LLM call. Returns the step UUID, or None on failure."""
    step_id = uuid.uuid4()
    try:
        await AgentStepsRepository().create(
            step_id=str(step_id),
            session_id=session_id,
            specialist_role=specialist_role,
            step_type=step_type,
            started_at=datetime.now(timezone.utc),
        )
        return step_id
    except Exception as exc:
        _log.warning("agent_steps create for %s failed: %s", step_type, exc)
        return None


class AgentStepsRepository:
    async def create(
        self,
        step_id: str,
        session_id: str,
        specialist_role: str,
        step_type: str,
        input_json: dict[str, Any] | None = None,
        started_at: datetime | None = None,
    ) -> None:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO agent_steps
                    (id, session_id, specialist_role, step_type, input_json, started_at)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                uuid.UUID(step_id),
                uuid.UUID(session_id),
                specialist_role,
                step_type,
                json.dumps(input_json) if input_json is not None else None,
                started_at,
            )

    async def update_ended(
        self,
        step_id: str,
        ended_at: datetime,
        output_json: dict[str, Any] | None = None,
    ) -> None:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE agent_steps
                SET ended_at = $2, output_json = $3
                WHERE id = $1
                """,
                uuid.UUID(step_id),
                ended_at,
                json.dumps(output_json) if output_json is not None else None,
            )

    async def list_recent_by_session(
        self,
        session_id: str,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Return the *limit* most recent agent_steps rows for a session.

        Each returned dict contains: step_id, session_id, step_type, content, created_at.
        ``content`` is extracted from ``input_json->>'content'`` when present.
        """
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, session_id, step_type, input_json, started_at
                FROM agent_steps
                WHERE session_id = $1
                ORDER BY started_at DESC
                LIMIT $2
                """,
                uuid.UUID(session_id),
                limit,
            )
        results: list[dict[str, Any]] = []
        for row in rows:
            raw_input = row["input_json"]
            if isinstance(raw_input, str):
                input_data: dict[str, Any] = json.loads(raw_input)
            elif raw_input is None:
                input_data = {}
            else:
                input_data = dict(raw_input)
            results.append(
                {
                    "step_id": str(row["id"]),
                    "session_id": str(row["session_id"]),
                    "step_type": row["step_type"],
                    "content": input_data.get("content", ""),
                    "created_at": row["started_at"].isoformat() if row["started_at"] else None,
                }
            )
        return results
