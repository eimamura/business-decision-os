from __future__ import annotations

import re
from typing import Any, TypedDict

from packages.persistence.db import get_pool

QueryRow = dict[str, Any]

MAX_ROWS = 1000

_LIMIT_RE = re.compile(r"\bLIMIT\b", re.IGNORECASE)


def _inject_limit(sql: str, max_rows: int) -> str:
    """Append LIMIT to sql if none is present, so the DB generates at most max_rows rows."""
    stripped = sql.rstrip().rstrip(";")
    if _LIMIT_RE.search(stripped):
        return stripped
    return f"{stripped} LIMIT {max_rows}"


class QueryResult(TypedDict):
    rows: list[QueryRow]
    column_names: list[str]
    row_count: int


async def execute_read_query(query: str) -> QueryResult:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(_inject_limit(query, MAX_ROWS), timeout=30.0)
        row_dicts = [dict(row) for row in rows]
        row_dicts = row_dicts[:MAX_ROWS]
        column_names = list(row_dicts[0].keys()) if row_dicts else []
        return {
            "rows": row_dicts,
            "column_names": column_names,
            "row_count": len(row_dicts),
        }
