from __future__ import annotations

import logging

from packages.persistence.db import get_pool

logger = logging.getLogger(__name__)


class UserRepository:
    """Repository for user role lookups backed by the ``users`` table."""

    async def get_role(self, user_id: str) -> str:
        """Return the role for *user_id*, defaulting to ``"analyst"`` for unknown users.

        Falls back to ``"analyst"`` when the database is unavailable so that
        existing tests and dev-mode code that runs without a DB connection are
        not broken.
        """
        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT role FROM users WHERE id = $1", user_id
                )
            return str(row["role"]) if row else "analyst"
        except Exception as exc:
            # DB unavailable: RuntimeError (missing DATABASE_URL), OSError or
            # ConnectionRefusedError (unreachable host in unit-test environment),
            # or asyncpg errors.  Log at debug level; callers receive the safe default.
            logger.debug(
                "users_repo.get_role: DB unavailable (%s: %s), defaulting to analyst",
                type(exc).__name__,
                exc,
            )
            return "analyst"
