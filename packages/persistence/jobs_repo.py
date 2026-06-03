from __future__ import annotations

import json
from typing import Any
from uuid import UUID, uuid4

from packages.persistence.db import get_pool


class JobsRepository:
    """Repository for jobs and job_files tables."""

    async def list_jobs(
        self,
        cursor: UUID | None = None,
        limit: int = 20,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return up to *limit* jobs ordered by created_at DESC, id DESC.

        *cursor* is the id of the last item on the previous page.
        *status* optionally filters rows to a single status value.
        """
        pool = await get_pool()
        async with pool.acquire() as conn:
            if cursor is None and status is None:
                rows = await conn.fetch(
                    "SELECT * FROM jobs ORDER BY created_at DESC, id DESC LIMIT $1",
                    limit,
                )
            elif cursor is None and status is not None:
                rows = await conn.fetch(
                    "SELECT * FROM jobs WHERE status = $1"
                    " ORDER BY created_at DESC, id DESC LIMIT $2",
                    status,
                    limit,
                )
            elif cursor is not None and status is None:
                rows = await conn.fetch(
                    "SELECT * FROM jobs WHERE id < $1"
                    " ORDER BY created_at DESC, id DESC LIMIT $2",
                    cursor,
                    limit,
                )
            else:
                # cursor is not None and status is not None
                rows = await conn.fetch(
                    "SELECT * FROM jobs WHERE id < $1 AND status = $2"
                    " ORDER BY created_at DESC, id DESC LIMIT $3",
                    cursor,
                    status,
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

    async def create(
        self,
        session_id: UUID | None,
        job_type: str,
        params: dict[str, Any],
        approval_id: UUID | None = None,
    ) -> dict[str, Any]:
        """INSERT a new jobs row with status='pending_approval'. Returns the full row as dict."""
        new_id = uuid4()
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO jobs
                    (id, session_id, status, job_type, params_json, approval_id, created_at)
                VALUES ($1, $2, 'pending_approval', $3, $4::jsonb, $5, now())
                RETURNING *
                """,
                new_id,
                session_id,
                job_type,
                json.dumps(params),
                approval_id,
            )
        return dict(row)

    async def update_status(
        self,
        job_id: UUID,
        status: str,
        result: dict[str, Any] | None = None,
        error: str | None = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost_usd: float = 0.0,
    ) -> dict[str, Any]:
        """UPDATE status, result_json, error, token counts.

        When status is 'completed', 'failed', or 'cancelled', also sets
        completed_at = now(). Returns the updated row as dict.
        """
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE jobs
                SET
                    status        = $2,
                    result_json   = $3::jsonb,
                    error         = $4,
                    input_tokens  = $5,
                    output_tokens = $6,
                    cost_usd      = $7,
                    completed_at  = CASE
                        WHEN $2 = ANY('{completed,failed,cancelled}'::text[])
                        THEN now()
                        ELSE completed_at
                    END
                WHERE id = $1
                RETURNING *
                """,
                job_id,
                status,
                json.dumps(result) if result is not None else None,
                error,
                input_tokens,
                output_tokens,
                cost_usd,
            )
        return dict(row)

    async def add_file(
        self,
        job_id: UUID,
        file_name: str,
        file_size_bytes: int,
        mime_type: str,
        download_url: str,
    ) -> dict[str, Any]:
        """INSERT a row into job_files. Returns the new row as dict."""
        new_id = uuid4()
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO job_files
                    (id, job_id, file_name, file_size_bytes, mime_type, download_url, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, now())
                RETURNING *
                """,
                new_id,
                job_id,
                file_name,
                file_size_bytes,
                mime_type,
                download_url,
            )
        return dict(row)

    async def get_by_approval_id(self, approval_id: UUID) -> dict[str, Any] | None:
        """SELECT the jobs row where approval_id = $1. Returns None if not found."""
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM jobs WHERE approval_id = $1",
                approval_id,
            )
        return dict(row) if row else None
