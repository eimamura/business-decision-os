from __future__ import annotations

import logging
import os

import asyncpg

from packages.persistence.db import get_pool

logger = logging.getLogger(__name__)

PER_USER_LIMIT = int(os.environ.get("RATE_LIMIT_PER_USER_PER_MIN", "10"))
GLOBAL_LIMIT = int(os.environ.get("RATE_LIMIT_GLOBAL_PER_MIN", "100"))


class RateLimitExceeded(Exception):
    pass


async def check_rate_limit(user_id: str) -> None:
    try:
        pool = await get_pool()
    except RuntimeError:
        logger.warning("DATABASE_URL not set; skipping rate limit check")
        return

    async with pool.acquire() as conn:
        await _increment_and_check(conn, f"user:{user_id}", PER_USER_LIMIT)
        await _increment_and_check(conn, "global", GLOBAL_LIMIT)
        await _cleanup_old_windows(conn)


async def _increment_and_check(conn: asyncpg.Connection, key: str, limit: int) -> None:
    count = await conn.fetchval(
        """
        INSERT INTO rate_limit_counters (key, window_start, count)
        VALUES ($1, date_trunc('minute', now()), 1)
        ON CONFLICT (key, window_start) DO UPDATE
          SET count = rate_limit_counters.count + 1
        RETURNING count
        """,
        key,
    )
    if count > limit:
        raise RateLimitExceeded(f"Rate limit exceeded for {key}")


async def _cleanup_old_windows(conn: asyncpg.Connection) -> None:
    await conn.execute(
        "DELETE FROM rate_limit_counters WHERE window_start < now() - interval '2 minutes'"
    )
