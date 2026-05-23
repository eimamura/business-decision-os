from __future__ import annotations

from typing import Any, TypedDict

from packages.persistence.db import get_pool

QueryRow = dict[str, Any]


class QueryResult(TypedDict):
    rows: list[QueryRow]
    column_names: list[str]
    row_count: int


async def execute_read_query(query: str) -> QueryResult:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(query)
        row_dicts = [dict(row) for row in rows]
        column_names = list(row_dicts[0].keys()) if row_dicts else []
        return {
            "rows": row_dicts,
            "column_names": column_names,
            "row_count": len(row_dicts),
        }
