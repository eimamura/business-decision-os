from __future__ import annotations

import datetime
import json
import uuid
from typing import Any

from packages.persistence.db import get_pool


def _serialize_row(row: Any) -> dict[str, Any]:
    """Convert an asyncpg Record to a JSON-safe dict.

    Converts UUID → str, date/datetime → ISO str, and JSONB objects to plain
    Python dicts so callers (including routers that hand the result to
    JSONResponse) never encounter non-serializable types (D-004 prevention).
    """
    result: dict[str, Any] = {}
    for key in row.keys():
        value = row[key]
        if isinstance(value, uuid.UUID):
            result[key] = str(value)
        elif isinstance(value, (datetime.datetime, datetime.date)):
            result[key] = value.isoformat()
        elif isinstance(value, str):
            # JSONB columns arrive as raw JSON strings from asyncpg in some
            # configurations — parse them so callers receive dicts/lists.
            # If parsing fails (plain text field), keep as-is.
            try:
                parsed = json.loads(value)
                result[key] = parsed if isinstance(parsed, (dict, list)) else value
            except (json.JSONDecodeError, TypeError):
                result[key] = value
        else:
            result[key] = value
    return result


class ScreeningRunsRepository:
    """Persist and retrieve daily screening run records from ``screening_runs``."""

    async def create(
        self,
        run_date: datetime.date,
        triggered_by: str,
        status: str,
        exception_count: int | None = None,
        severity_counts: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        """Insert a new screening run row and return the inserted row as a JSON-safe dict."""
        row_id = uuid.uuid4()
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO screening_runs
                    (id, run_date, triggered_by, status,
                     exception_count, severity_counts, payload, error)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING *
                """,
                row_id,
                run_date,
                triggered_by,
                status,
                exception_count,
                json.dumps(severity_counts) if severity_counts is not None else None,
                json.dumps(payload) if payload is not None else None,
                error,
            )
        if row is None:
            raise RuntimeError("INSERT INTO screening_runs returned no row")
        return _serialize_row(row)

    async def latest_for_date(self, run_date: datetime.date) -> dict[str, Any] | None:
        """Return the best run for *run_date*: latest completed row, else latest row.

        "Best" is defined as:
        1. The most-recent completed row for the date (by created_at DESC).
        2. If no completed row exists, the most-recent row regardless of status.

        Returns ``None`` when no row exists for the given date.
        """
        pool = await get_pool()
        async with pool.acquire() as conn:
            # Try latest completed first.
            row = await conn.fetchrow(
                """
                SELECT *
                FROM screening_runs
                WHERE run_date = $1
                  AND status = 'completed'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                run_date,
            )
            if row is None:
                # Fall back to latest row regardless of status.
                row = await conn.fetchrow(
                    """
                    SELECT *
                    FROM screening_runs
                    WHERE run_date = $1
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    run_date,
                )
        if row is None:
            return None
        return _serialize_row(row)

    async def latest(self) -> dict[str, Any] | None:
        """Return the single most-recently created run across all dates."""
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT *
                FROM screening_runs
                ORDER BY created_at DESC
                LIMIT 1
                """
            )
        if row is None:
            return None
        return _serialize_row(row)
