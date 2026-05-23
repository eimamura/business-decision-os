from __future__ import annotations

import logging

from packages.tools.sql_allowlist import ALLOWED_READ_TABLES

logger = logging.getLogger(__name__)

_schema_context: str = ""


async def load_schema_context() -> str:
    """Read all allowed tables from information_schema and cache the result.

    Called once at API startup. Subsequent calls to get_schema_context() are free.
    """
    global _schema_context
    try:
        from packages.persistence.db import get_pool

        pool = await get_pool()
        async with pool.acquire() as conn:
            lines: list[str] = []
            for table in sorted(ALLOWED_READ_TABLES):
                rows = await conn.fetch(
                    """
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = $1
                    ORDER BY ordinal_position
                    """,
                    table,
                )
                if rows:
                    cols = ", ".join(
                        f"{r['column_name']} {r['data_type'].upper()}" for r in rows
                    )
                    lines.append(f"{table}({cols})")
            lines.append(
                "Join rule: all sku_id columns are TEXT; "
                "join with ON table.sku_id = sku_master.sku_id (not UUID)."
            )
            _schema_context = "\n".join(lines)
            logger.info("Schema context loaded: %d tables", len(sorted(ALLOWED_READ_TABLES)))
    except Exception as exc:
        logger.warning("Could not load schema context from DB: %s", exc)
    return _schema_context


def get_schema_context() -> str:
    return _schema_context
