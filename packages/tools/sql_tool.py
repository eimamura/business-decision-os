from __future__ import annotations

from typing import Any

from packages.persistence import execute_read_query
from packages.tools.base import ToolContext, ToolResult
from packages.tools.sql_guardrail import SQLGuardrailError, validate_read_sql


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
        query: str = input.get("query", "")

        try:
            validate_read_sql(query)
        except SQLGuardrailError as exc:
            error = str(exc)
            return ToolResult(
                output={"error": error, "rows": [], "column_names": [], "row_count": 0},
                audit_payload={"query": query, "error": error, "row_count": 0},
            )

        try:
            result = await execute_read_query(query)
            return ToolResult(
                output={
                    "rows": result["rows"],
                    "column_names": result["column_names"],
                    "row_count": result["row_count"],
                    "executed_query": query,
                },
                audit_payload={"query": query, "row_count": result["row_count"]},
            )
        except Exception as exc:
            output: dict[str, Any] = {
                "rows": [],
                "column_names": [],
                "row_count": 0,
            }
            if _is_connection_error(exc):
                output["note"] = "no database connection"
            else:
                output["error"] = str(exc)
            return ToolResult(
                output=output,
                audit_payload={"query": query, "row_count": 0},
            )


def _is_connection_error(exc: Exception) -> bool:
    message = str(exc).lower()
    class_name = exc.__class__.__name__.lower()
    module_name = exc.__class__.__module__.lower()
    if isinstance(exc, RuntimeError) and "database_url" in message:
        return True
    return (
        "asyncpg" in module_name
        and (
            "connection" in class_name
            or "connection" in message
            or "connect call failed" in message
            or "connection refused" in message
        )
    )
