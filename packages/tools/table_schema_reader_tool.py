from __future__ import annotations

from typing import Any

from packages.tools.base import ToolContext, ToolResult
from packages.tools.sql_allowlist import ALLOWED_READ_TABLES


class TableSchemaReaderTool:
    name = "table_schema_reader"
    description = "Read column names and types for an operational table"
    requires_approval = False
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "table_name": {"type": "string"},
        },
        "required": ["table_name"],
    }
    output_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "table_name": {"type": "string"},
            "columns": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "column_name": {"type": "string"},
                        "data_type": {"type": "string"},
                        "is_nullable": {"type": "boolean"},
                        "column_default": {"type": ["string", "null"]},
                    },
                },
            },
            "column_count": {"type": "integer"},
        },
    }

    async def handle(self, input: dict[str, Any], ctx: ToolContext) -> ToolResult:
        table_name = input.get("table_name", "").lower()

        if table_name not in ALLOWED_READ_TABLES:
            return ToolResult(
                output={
                    "error": f"Table '{table_name}' is not available",
                    "columns": [],
                    "column_count": 0,
                },
                audit_payload={"table_name": table_name, "error": "not_in_allowlist"},
            )

        try:
            from packages.persistence.db import get_pool

            pool = await get_pool()
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT column_name, data_type, is_nullable, column_default
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = $1
                    ORDER BY ordinal_position
                    """,
                    table_name,
                )
                columns = [
                    {
                        "column_name": r["column_name"],
                        "data_type": r["data_type"],
                        "is_nullable": r["is_nullable"] == "YES",
                        "column_default": r["column_default"],
                    }
                    for r in rows
                ]
            return ToolResult(
                output={
                    "table_name": table_name,
                    "columns": columns,
                    "column_count": len(columns),
                },
                audit_payload={"table_name": table_name, "column_count": len(columns)},
            )
        except Exception:
            return ToolResult(
                output={
                    "table_name": table_name,
                    "columns": [],
                    "column_count": 0,
                    "note": "no database connection",
                },
                audit_payload={"table_name": table_name, "column_count": 0},
            )
