from __future__ import annotations

import re
from typing import TypedDict

from packages.persistence.db import get_pool

_IDENTIFIER_RE = re.compile(r"^[a-z0-9_]+$")


class CatalogTableRow(TypedDict):
    table_name: str
    row_count: int | None


class TableSchemaColumn(TypedDict):
    column_name: str
    data_type: str
    is_nullable: bool
    column_default: str | None


class SchemaContextColumn(TypedDict):
    column_name: str
    data_type: str


class NullProfileColumn(TypedDict):
    column_name: str
    null_count: int
    null_pct: float


class NullProfile(TypedDict):
    total_rows: int
    columns: list[NullProfileColumn]


def _validate_identifier(identifier: str) -> None:
    if not _IDENTIFIER_RE.fullmatch(identifier):
        raise ValueError(f"Invalid SQL identifier: {identifier}")


def _quote_identifier(identifier: str) -> str:
    _validate_identifier(identifier)
    return f'"{identifier}"'


async def list_tables_with_counts(tables: list[str]) -> list[CatalogTableRow]:
    pool = await get_pool()
    result: list[CatalogTableRow] = []
    async with pool.acquire() as conn:
        for table in tables:
            quoted_table = _quote_identifier(table)
            row_count = await conn.fetchval(f"SELECT COUNT(*) FROM {quoted_table}")
            result.append({"table_name": table, "row_count": row_count})
    return result


async def get_table_schema(table_name: str) -> list[TableSchemaColumn]:
    _validate_identifier(table_name)
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = $1 AND table_name = $2
            ORDER BY ordinal_position
            """,
            "public",
            table_name,
        )
        return [
            {
                "column_name": row["column_name"],
                "data_type": row["data_type"],
                "is_nullable": row["is_nullable"] == "YES",
                "column_default": row["column_default"],
            }
            for row in rows
        ]


async def get_schema_context_columns(
    tables: list[str],
) -> dict[str, list[SchemaContextColumn]]:
    for table in tables:
        _validate_identifier(table)

    pool = await get_pool()
    result: dict[str, list[SchemaContextColumn]] = {table: [] for table in tables}
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT table_name, column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = $1 AND table_name = ANY($2::text[])
            ORDER BY table_name, ordinal_position
            """,
            "public",
            tables,
        )
        for row in rows:
            table_name = row["table_name"]
            result[table_name].append(
                {
                    "column_name": row["column_name"],
                    "data_type": row["data_type"],
                }
            )
    return result


async def get_null_profile(table_name: str) -> NullProfile:
    quoted_table = _quote_identifier(table_name)
    pool = await get_pool()
    async with pool.acquire() as conn:
        col_rows = await conn.fetch(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = $1 AND table_name = $2
            ORDER BY ordinal_position
            """,
            "public",
            table_name,
        )
        col_names = [row["column_name"] for row in col_rows]

        if not col_names:
            return {"total_rows": 0, "columns": []}

        null_exprs = ", ".join(
            (
                f"COUNT(*) FILTER (WHERE {_quote_identifier(column)} IS NULL) "
                f"AS {_quote_identifier(f'{column}_nulls')}"
            )
            for column in col_names
        )
        row = await conn.fetchrow(
            f"SELECT COUNT(*) AS total, {null_exprs} FROM {quoted_table}"
        )
        if row is None:
            raise RuntimeError("fetchrow returned None")

        total = int(row["total"])
        columns: list[NullProfileColumn] = []
        for column in col_names:
            null_count = int(row[f"{column}_nulls"])
            null_pct = round(null_count / total * 100, 2) if total > 0 else 0.0
            columns.append(
                {
                    "column_name": column,
                    "null_count": null_count,
                    "null_pct": null_pct,
                }
            )

        return {"total_rows": total, "columns": columns}
