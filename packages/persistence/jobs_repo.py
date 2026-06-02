from __future__ import annotations

from typing import Any
from uuid import UUID

from packages.persistence.db import get_pool


class JobsRepository:
    """Repository for jobs and job_files tables."""

    async def list_jobs(
        self,
        cursor: UUID | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Return up to *limit* jobs after *cursor* (cursor-based pagination).

        Pagination uses ``id > cursor ORDER BY id`` so the cursor is the id of
        the last item on the previous page.
        """
        pool = await get_pool()
        async with pool.acquire() as conn:
            if cursor is None:
                rows = await conn.fetch(
                    "SELECT * FROM jobs ORDER BY id LIMIT $1",
                    limit,
                )
            else:
                rows = await conn.fetch(
                    "SELECT * FROM jobs WHERE id > $1 ORDER BY id LIMIT $2",
                    cursor,
                    limit,
                )
        return [dict(r) for r in rows]

    async def get_job(self, job_id: UUID) -> dict[str, Any] | None:
        """Return the job with *job_id*, or ``None`` if not found."""
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM jobs WHERE id = $1", job_id)
        return dict(row) if row else None

    async def list_files(self, job_id: UUID) -> list[dict[str, Any]]:
        """Return all files attached to *job_id*."""
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM job_files WHERE job_id = $1 ORDER BY created_at",
                job_id,
            )
        return [dict(r) for r in rows]

    async def list_all_files(
        self,
        cursor: UUID | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Return up to *limit* files across all jobs after *cursor*."""
        pool = await get_pool()
        async with pool.acquire() as conn:
            if cursor is None:
                rows = await conn.fetch(
                    "SELECT * FROM job_files ORDER BY id LIMIT $1",
                    limit,
                )
            else:
                rows = await conn.fetch(
                    "SELECT * FROM job_files WHERE id > $1 ORDER BY id LIMIT $2",
                    cursor,
                    limit,
                )
        return [dict(r) for r in rows]
