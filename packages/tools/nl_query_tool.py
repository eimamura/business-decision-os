from __future__ import annotations

import hashlib
import logging
import os
import time
from typing import Any

import sqlparse
import sqlparse.sql
import sqlparse.tokens as T

from packages.tools.base import ToolContext, ToolResult
from packages.tools.sql_allowlist import ALLOWED_READ_TABLES

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 60
MAX_RETRIES = 2

DB_SCHEMA = """
Tables available for querying:

sku_master(id UUID, sku_code TEXT, name TEXT, category TEXT, unit_cost NUMERIC, lead_time_days INT)

inventory(id UUID, sku_id UUID FK->sku_master.id, warehouse TEXT,
          quantity INT, updated_at TIMESTAMPTZ)

demand_history(id UUID, sku_id UUID FK->sku_master.id, period DATE,
               quantity INT, created_at TIMESTAMPTZ)

supply(id UUID, sku_id UUID FK->sku_master.id, supplier TEXT,
       quantity INT, eta DATE, created_at TIMESTAMPTZ)

cost(id UUID, sku_id UUID FK->sku_master.id, cost_type TEXT, amount NUMERIC, period DATE)

customers(id UUID, email TEXT, name TEXT, created_at TIMESTAMPTZ)

Rules:
- Write a single SELECT statement only.
- Do not reference any table not listed above.
- Use standard SQL compatible with PostgreSQL 16.
- Return only the SQL query, no explanation.
"""

FEW_SHOT_EXAMPLES = """
Examples:
Q: Which SKUs have the highest inventory?
A: SELECT s.sku_code, s.name, SUM(i.quantity) AS total_qty
   FROM inventory i JOIN sku_master s ON i.sku_id = s.id
   GROUP BY s.id, s.sku_code, s.name ORDER BY total_qty DESC LIMIT 10;

Q: What is the demand trend for the last 6 months?
A: SELECT period, SUM(quantity) AS total_demand
   FROM demand_history
   WHERE period >= CURRENT_DATE - INTERVAL '6 months'
   GROUP BY period ORDER BY period;

Q: Which suppliers have pending supply orders?
A: SELECT supplier, COUNT(*) AS orders, SUM(quantity) AS total_qty
   FROM supply WHERE eta >= CURRENT_DATE
   GROUP BY supplier ORDER BY total_qty DESC;
"""

_STATIC_SYSTEM_TEXT = (
    f"You are a SQL expert. Generate a PostgreSQL SELECT query.\n\n{DB_SCHEMA}{FEW_SHOT_EXAMPLES}"
)

_result_cache: dict[str, tuple[list[dict[str, Any]], str, float]] = {}


class SQLGuardrailError(Exception):
    pass


def _extract_tables(stmt: sqlparse.sql.Statement) -> set[str]:
    tables: set[str] = set()
    from_seen = False

    for token in stmt.flatten():  # type: ignore[no-untyped-call]
        if token.ttype in (T.Keyword, T.Keyword.DML):
            val = token.normalized.upper()
            if val in ("FROM", "JOIN", "INNER JOIN", "LEFT JOIN", "RIGHT JOIN", "FULL JOIN"):
                from_seen = True
                continue
            elif val in ("WHERE", "ON", "SET", "GROUP", "HAVING", "ORDER", "LIMIT", "UNION"):
                from_seen = False
        elif from_seen and token.ttype in (T.Name, T.Literal.String.Single):
            tables.add(token.normalized.lower().strip('"').strip("'"))
            from_seen = False

    return tables


def validate_sql(sql: str) -> None:
    parsed = sqlparse.parse(sql)
    if not parsed:
        raise SQLGuardrailError("Empty SQL statement")

    stmt = parsed[0]
    stmt_type: str = stmt.get_type()  # type: ignore[no-untyped-call]
    if stmt_type != "SELECT":
        raise SQLGuardrailError(f"Only SELECT statements are allowed, got: {stmt_type}")

    tables = _extract_tables(stmt)
    disallowed = tables - ALLOWED_READ_TABLES
    if disallowed:
        raise SQLGuardrailError(f"Table(s) not allowed: {disallowed}")


async def _load_positive_examples(conn: Any) -> str:
    return ""


async def _generate_sql(
    question: str,
    anthropic_client: Any,
    error_context: str = "",
    dynamic_examples: str = "",
) -> str:
    user_content = question + error_context
    system_blocks: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": _STATIC_SYSTEM_TEXT,
            "cache_control": {"type": "ephemeral"},
        }
    ]
    if dynamic_examples:
        system_blocks.append({"type": "text", "text": dynamic_examples})

    message = await anthropic_client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        system=system_blocks,
        messages=[{"role": "user", "content": user_content}],
    )
    sql = message.content[0].text.strip()
    if sql.startswith("```"):
        lines = sql.split("\n")
        sql = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
    return str(sql.strip())


async def generate_and_run(
    conn: Any,
    question: str,
    anthropic_client: Any,
) -> tuple[list[dict[str, Any]], str]:
    cache_key = hashlib.sha256(question.encode()).hexdigest()
    cached = _result_cache.get(cache_key)
    if cached and time.time() - cached[2] < CACHE_TTL_SECONDS:
        logger.debug("Cache hit for question hash %s", cache_key[:8])
        return cached[0], cached[1]

    dynamic_examples = await _load_positive_examples(conn)
    error_context = ""
    for attempt in range(MAX_RETRIES + 1):
        sql = await _generate_sql(question, anthropic_client, error_context, dynamic_examples)
        try:
            validate_sql(sql)
            rows = await conn.fetch(sql)
            result = [dict(r) for r in rows]
            _result_cache[cache_key] = (result, sql, time.time())
            return result, sql
        except SQLGuardrailError:
            raise
        except Exception as exc:
            if attempt == MAX_RETRIES:
                raise
            logger.warning("SQL attempt %d failed: %s", attempt + 1, exc)
            error_context = (
                f"\n\nPrevious attempt failed with error: {exc}\n"
                f"Bad SQL was:\n{sql}\nGenerate a corrected query."
            )

    raise RuntimeError("Unreachable")


class NlQueryTool:
    name = "nl_query"
    description = (
        "Answer a question about operational data in natural language. "
        "Generates and executes a read-only SQL query."
    )
    requires_approval = False
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {"question": {"type": "string"}},
        "required": ["question"],
    }
    output_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "results": {"type": "array"},
            "count": {"type": "integer"},
            "sql": {"type": "string"},
        },
    }

    async def handle(self, input: dict[str, Any], ctx: ToolContext) -> ToolResult:
        import anthropic

        from packages.state.db import get_pool

        question: str = input.get("question", "")
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        anthropic_client = anthropic.AsyncAnthropic(api_key=api_key)

        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                results, sql = await generate_and_run(conn, question, anthropic_client)
                return ToolResult(
                    output={"results": results, "count": len(results), "sql": sql},
                    audit_payload={"question": question, "sql": sql, "count": len(results)},
                )
        except SQLGuardrailError as exc:
            return ToolResult(
                output={"results": [], "count": 0, "sql": "", "error": str(exc)},
                audit_payload={"question": question, "sql": "", "count": 0, "error": str(exc)},
            )
        except RuntimeError as exc:
            return ToolResult(
                output={"results": [], "count": 0, "sql": "", "note": str(exc)},
                audit_payload={"question": question, "sql": "", "count": 0},
            )
        except Exception as exc:
            return ToolResult(
                output={"results": [], "count": 0, "sql": "", "error": str(exc)},
                audit_payload={"question": question, "sql": "", "count": 0, "error": str(exc)},
            )
