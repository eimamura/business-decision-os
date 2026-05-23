from __future__ import annotations

from typing import Any

from packages.persistence.catalog_repo import get_null_profile
from packages.tools.base import ToolContext, ToolResult
from packages.tools.sql_allowlist import ALLOWED_READ_TABLES


class DataQualityCheckerTool:
    name = "data_quality_checker"
    description = "Check for missing values and data quality issues in an operational table"
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
            "total_rows": {"type": "integer"},
            "columns": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "column_name": {"type": "string"},
                        "null_count": {"type": "integer"},
                        "null_pct": {"type": "number"},
                    },
                },
            },
            "has_issues": {"type": "boolean"},
        },
    }

    async def handle(self, input: dict[str, Any], ctx: ToolContext) -> ToolResult:
        table_name = input.get("table_name", "").lower()

        if table_name not in ALLOWED_READ_TABLES:
            return ToolResult(
                output={"error": f"Table '{table_name}' is not available"},
                audit_payload={"table_name": table_name, "error": "not_in_allowlist"},
            )

        try:
            profile = await get_null_profile(table_name)
            has_issues = any(column["null_count"] > 0 for column in profile["columns"])
            return ToolResult(
                output={
                    "table_name": table_name,
                    "total_rows": profile["total_rows"],
                    "columns": profile["columns"],
                    "has_issues": has_issues,
                },
                audit_payload={
                    "table_name": table_name,
                    "total_rows": profile["total_rows"],
                },
            )
        except Exception:
            return ToolResult(
                output={
                    "table_name": table_name,
                    "total_rows": 0,
                    "columns": [],
                    "has_issues": False,
                    "note": "no database connection",
                },
                audit_payload={"table_name": table_name},
            )
