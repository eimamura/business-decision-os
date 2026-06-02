from __future__ import annotations


class UserRepository:
    """Repository for user role lookups.

    Currently returns "analyst" for all users because no ``users`` table exists
    yet in the database schema.  When a ``users`` table is added (with at least
    ``id`` and ``role`` columns), replace the body of ``get_role`` with an
    asyncpg query such as:

        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT role FROM users WHERE id = $1", user_id
            )
        return str(row["role"]) if row else "analyst"
    """

    async def get_role(self, user_id: str) -> str:
        """Return the role for *user_id*, defaulting to ``"analyst"``."""
        return "analyst"
