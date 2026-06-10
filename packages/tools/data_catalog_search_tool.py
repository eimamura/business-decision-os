from __future__ import annotations

from typing import Any, Literal

from packages.persistence.catalog_repo import list_tables_with_counts
from packages.tools._shared import db_error_message
from packages.tools.base import ToolContext, ToolResult
from packages.tools.sql_allowlist import ALLOWED_READ_TABLES


class DataCatalogSearchTool:
    name = "data_catalog_search"
    description = "List available operational tables and their row counts"
    safety_level: Literal["read_only", "write", "hitl"] = "read_only"
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "keyword": {
                "type": "string",
                "description": "Optional partial match filter on table name",
            },
        },
    }
    output_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "tables": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "table_name": {"type": "string"},
                        "row_count": {"type": ["integer", "null"]},
                    },
                },
            },
            "count": {"type": "integer"},
            "error": {"type": "string"},
            "missing_data": {"type": "array", "items": {"type": "string"}},
        },
    }

    async def handle(self, input: dict[str, Any], ctx: ToolContext) -> ToolResult:
        keyword = input.get("keyword", "").lower()
        tables = sorted(t for t in ALLOWED_READ_TABLES if not keyword or keyword in t)

        try:
            result = await list_tables_with_counts(tables)
            return ToolResult(
                output={
                    "tables": result,
                    "count": len(result),
                    "missing_data": [],
                },
                audit_payload={"keyword": keyword, "table_count": len(result)},
            )
        except Exception as exc:
            degraded = [{"table_name": t, "row_count": None} for t in tables]
            return ToolResult(
                output={
                    "tables": degraded,
                    "count": len(degraded),
                    "error": db_error_message(exc),
                    "missing_data": [],
                },
                audit_payload={"keyword": keyword, "table_count": len(degraded)},
            )
