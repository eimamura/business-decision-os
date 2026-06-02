from __future__ import annotations

from typing import Any
from uuid import UUID

from packages.persistence.db import get_pool


class ApprovalsRepository:
    async def get(self, id: UUID) -> dict[str, Any] | None:
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM approvals WHERE id = $1", id)
        return dict(row) if row else None

    async def create(self, record: dict[str, Any]) -> dict[str, Any]:
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """INSERT INTO approvals (session_id, recommendation_id, status, reason, actor)
                   VALUES ($1, $2, $3, $4, $5) RETURNING *""",
                record.get("session_id"),
                record.get("recommendation_id"),
                record.get("status", "pending"),
                record.get("reason"),
                record.get("actor"),
            )
        if row is None:
            raise RuntimeError("INSERT INTO approvals returned no row")
        return dict(row)

    async def update(self, id: UUID, **kwargs: Any) -> dict[str, Any]:
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """UPDATE approvals SET status = $2, reason = $3, actor = $4, updated_at = now()
                   WHERE id = $1 RETURNING *""",
                id,
                kwargs.get("status"),
                kwargs.get("reason"),
                kwargs.get("actor"),
            )
        if row is None:
            raise ValueError(f"Approval {id} not found")
        return dict(row)

    async def list(self, **filters: Any) -> list[dict[str, Any]]:
        pool = await get_pool()
        async with pool.acquire() as conn:
            if "status" in filters:
                rows = await conn.fetch(
                    "SELECT * FROM approvals WHERE status = $1 ORDER BY created_at DESC",
                    filters["status"],
                )
            else:
                rows = await conn.fetch("SELECT * FROM approvals ORDER BY created_at DESC")
        return [dict(r) for r in rows]

    async def get_pending_approval_for_session(
        self, session_id: UUID
    ) -> dict[str, Any] | None:
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM approvals WHERE session_id = $1 AND status = 'pending' LIMIT 1",
                session_id,
            )
        return dict(row) if row else None
