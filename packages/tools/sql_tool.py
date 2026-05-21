from __future__ import annotations

import re
from typing import Any

from packages.tools.base import ToolContext, ToolResult
from packages.tools.sql_allowlist import ALLOWED_READ_TABLES

_WRITE_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE)\b", re.IGNORECASE
)
_TABLE_PATTERN = re.compile(r"\bFROM\s+(\w+)|\bJOIN\s+(\w+)", re.IGNORECASE)


def _extract_tables(sql: str) -> list[str]:
    tables = []
    for match in _TABLE_PATTERN.finditer(sql):
        table = match.group(1) or match.group(2)
        if table:
            tables.append(table.lower())
    return tables


def _validate_sql(sql: str) -> str | None:
    if _WRITE_KEYWORDS.search(sql):
        return "Write statements are not allowed"
    for table in _extract_tables(sql):
        if table not in ALLOWED_READ_TABLES:
            return f"Table '{table}' is not in the allowlist"
    return None


class SqlQueryTool:
    name = "sql_query"
    description = "Execute read-only SQL against operational tables"
    requires_approval = False
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Read-only SQL query"},
        },
        "required": ["query"],
    }
    output_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "rows": {"type": "array"},
            "column_names": {"type": "array"},
            "row_count": {"type": "integer"},
        },
    }

    def __init__(self, db_session: Any | None = None) -> None:
        pass

    async def handle(self, input: dict[str, Any], ctx: ToolContext) -> ToolResult:
        from packages.persistence.db import get_pool

        query: str = input.get("query", "")

        error = _validate_sql(query)
        if error:
            return ToolResult(
                output={"error": error, "rows": [], "column_names": [], "row_count": 0},
                audit_payload={"query": query, "error": error, "row_count": 0},
            )

        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                rows = await conn.fetch(query)
                columns = list(rows[0].keys()) if rows else []
                row_dicts = [dict(r) for r in rows]
                return ToolResult(
                    output={
                        "rows": row_dicts,
                        "column_names": columns,
                        "row_count": len(row_dicts),
                        "executed_query": query,
                    },
                    audit_payload={"query": query, "row_count": len(row_dicts)},
                )
        except Exception:
            return ToolResult(
                output={
                    "rows": [],
                    "column_names": [],
                    "row_count": 0,
                    "note": "no database connection",
                },
                audit_payload={"query": query, "row_count": 0},
            )
