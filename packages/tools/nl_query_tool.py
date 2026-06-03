from __future__ import annotations

import hashlib
import logging
import time
from typing import Any, Literal

from packages.agent.context_sanitizer import sanitize_sql_results
from packages.agent.llm import LLMClient, LLMMessage
from packages.persistence import execute_read_query
from packages.tools.base import ToolContext, ToolResult
from packages.tools.schema_context import get_schema_context
from packages.tools.sql_guardrail import SQLGuardrailError, validate_read_sql

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 60
MAX_RETRIES = 2

_SQL_RULES = (
    "Rules:\n"
    "- Write a single SELECT statement only.\n"
    "- Do not reference any table not listed above.\n"
    "- Use standard SQL compatible with PostgreSQL 16.\n"
    "- Return only the SQL query, no explanation.\n"
    "- Always include LIMIT 100 or less at the end of every query.\n"
)

FEW_SHOT_EXAMPLES = """
Examples:
Q: Which SKUs have the highest inventory?
A: SELECT s.sku_id, s.name, SUM(i.on_hand) AS total_on_hand
   FROM inventory i JOIN sku_master s ON i.sku_id = s.sku_id
   GROUP BY s.sku_id, s.name ORDER BY total_on_hand DESC LIMIT 10;

Q: What is the demand trend for the last 6 months?
A: SELECT date, SUM(quantity) AS total_demand
   FROM demand_history
   WHERE date >= CURRENT_DATE - INTERVAL '6 months'
   GROUP BY date ORDER BY date LIMIT 90;

Q: Which suppliers have pending supply orders?
A: SELECT supplier_id, COUNT(*) AS orders, SUM(quantity) AS total_qty
   FROM supply WHERE expected_arrival >= CURRENT_DATE
   GROUP BY supplier_id ORDER BY total_qty DESC LIMIT 90;
"""


def _build_system_text() -> str:
    schema = get_schema_context()
    schema_section = (
        f"Tables available for querying:\n{schema}\n\n{_SQL_RULES}"
        if schema
        else _SQL_RULES
    )
    return (
        "You are a SQL expert. Generate a PostgreSQL SELECT query.\n\n"
        f"{schema_section}{FEW_SHOT_EXAMPLES}"
    )

_result_cache: dict[str, tuple[list[dict[str, Any]], str, float]] = {}

validate_sql = validate_read_sql


async def _load_positive_examples() -> str:
    return ""


async def _generate_sql(
    question: str,
    llm_client: LLMClient,
    error_context: str = "",
    dynamic_examples: str = "",
) -> str:
    user_content = question + error_context
    system_parts = _build_system_text()
    if dynamic_examples:
        system_parts = system_parts + "\n\n" + dynamic_examples

    llm_messages: list[LLMMessage] = [
        LLMMessage(role="system", content=system_parts),
        LLMMessage(role="user", content=user_content),
    ]
    response = await llm_client.complete(llm_messages, max_tokens=512)
    sql = response.text.strip()
    if sql.startswith("```"):
        lines = sql.split("\n")
        sql = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
    return str(sql.strip())


async def generate_and_run(
    question: str,
    llm_client: LLMClient,
) -> tuple[list[dict[str, Any]], str]:
    cache_key = hashlib.sha256(question.encode()).hexdigest()
    cached = _result_cache.get(cache_key)
    if cached and time.time() - cached[2] < CACHE_TTL_SECONDS:
        logger.debug("Cache hit for question hash %s", cache_key[:8])
        return cached[0], cached[1]

    dynamic_examples = await _load_positive_examples()
    error_context = ""
    for attempt in range(MAX_RETRIES + 1):
        sql = await _generate_sql(question, llm_client, error_context, dynamic_examples)
        try:
            validate_sql(sql)
            query_result = await execute_read_query(sql)
            result = query_result["rows"]
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
    safety_level: Literal["read_only", "write", "hitl"] = "read_only"
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {"question": {"type": "string"}},
        "required": ["question"],
    }
    output_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "rows": {"type": "array"},
            "row_count": {"type": "integer"},
            "truncated": {"type": "boolean"},
            "columns": {"type": "array"},
            "sql": {"type": "string"},
        },
    }

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self._llm_client = llm_client

    async def handle(self, input: dict[str, Any], ctx: ToolContext) -> ToolResult:
        if self._llm_client is None:
            raise RuntimeError(
                "NlQueryTool requires an LLMClient — pass llm_client to create_tool_registry()"
            )

        question: str = input.get("question", "")

        try:
            results, sql = await generate_and_run(question, self._llm_client)
            real_count = len(results)
            sanitized = sanitize_sql_results(results, max_rows=100)
            return ToolResult(
                output={**sanitized, "sql": sql, "executed_query": sql},
                audit_payload={"question": question, "sql": sql, "count": real_count},
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
