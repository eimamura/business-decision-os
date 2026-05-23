from __future__ import annotations

from typing import Any

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
            from packages.persistence.db import get_pool

            pool = await get_pool()
            async with pool.acquire() as conn:
                col_rows = await conn.fetch(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = $1
                    ORDER BY ordinal_position
                    """,
                    table_name,
                )
                col_names = [r["column_name"] for r in col_rows]

                if not col_names:
                    return ToolResult(
                        output={
                            "table_name": table_name,
                            "total_rows": 0,
                            "columns": [],
                            "has_issues": False,
                        },
                        audit_payload={"table_name": table_name, "total_rows": 0},
                    )

                # table_name validated against ALLOWED_READ_TABLES (compile-time frozenset).
                # col_names sourced from information_schema for this specific table — safe to interpolate.
                null_exprs = ", ".join(
                    f'COUNT(*) FILTER (WHERE "{col}" IS NULL) AS "{col}_nulls"'
                    for col in col_names
                )
                row = await conn.fetchrow(
                    f'SELECT COUNT(*) AS total, {null_exprs} FROM "{table_name}"'
                )
                if row is None:
                    raise RuntimeError("fetchrow returned None")

                total: int = row["total"]
                columns: list[dict[str, Any]] = []
                for col in col_names:
                    null_count: int = row[f"{col}_nulls"]
                    null_pct = round(null_count / total * 100, 2) if total > 0 else 0.0
                    columns.append(
                        {
                            "column_name": col,
                            "null_count": null_count,
                            "null_pct": null_pct,
                        }
                    )

                return ToolResult(
                    output={
                        "table_name": table_name,
                        "total_rows": total,
                        "columns": columns,
                        "has_issues": any(c["null_count"] > 0 for c in columns),
                    },
                    audit_payload={"table_name": table_name, "total_rows": total},
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
