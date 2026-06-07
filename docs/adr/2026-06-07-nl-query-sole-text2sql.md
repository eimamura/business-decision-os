# ADR: nl_query as Sole Text2SQL Tool — Removal of sql_query

**Date:** 2026-06-07
**Status:** Accepted
**Deciders:** Erielcio Imamura

## Context

Two tools existed for database queries:

- `sql_query` (`SqlQueryTool`) — accepts a raw SQL string written by the calling LLM. The LLM must know the schema precisely.
- `nl_query` (`NlQueryTool`) — accepts a plain-English question; internally generates SQL using `get_schema_context()` which reads the actual schema from `information_schema` at startup.

After the P54 LangChain migration and the switch to local Ollama models (`qwen3.5:2b`, `qwen3.5:9b`), `sql_query` caused systematic hallucination: small models wrote SQL with columns that do not exist (e.g. `days_of_supply` from `inventory_snapshot`) because they relied on training-data knowledge rather than the actual DB schema. The guardrail passed (table name was valid) but DB execution failed, and the model then fabricated an explanation.

## Decision

**Remove `SqlQueryTool` entirely. `nl_query` becomes the sole Text2SQL tool for all roles.**

Supporting changes:
- `canonicalize_table_names()` added to `sql_allowlist.py`: rewrites legacy table names (`inventory` → `inventory_snapshot`, etc.) before guardrail validation, preventing blocks from schema-renamed tables.
- `_build_few_shot_examples()` in `nl_query_tool.py`: generates SQL examples dynamically from `get_schema_context()` instead of a static `FEW_SHOT_EXAMPLES` constant (which violated AGENTS.md §73-74 and used stale table names).
- `_INTENT_TOOL_SUBSET` in `control_agent.py`: replaced `sql_query` with `nl_query` in all intent subsets (`supply_chain`, `inventory`, `demand`, `finance`).
- System prompt updated with explicit tool priority: specialized tools first, then `nl_query` for bulk questions.

## Consequences

**Positive:**
- Eliminates an entire class of hallucination: the model cannot fabricate SQL column names because SQL generation is internal to `nl_query` and is grounded in `get_schema_context()`.
- Single code path for all data queries; guardrail (`validate_read_sql`) is applied consistently.
- Small local models can pass a natural-language question instead of writing SQL.

**Negative:**
- Agents can no longer pass raw SQL. If a future use case requires raw SQL (e.g., a developer-mode tool), a new tool must be added explicitly.
- `nl_query` adds one LLM call per data question (for SQL generation). For Claude (large model), this is a minor cost; for Ollama (local), latency impact is minimal.

## Rejected Alternatives

- **Keep both tools, add priority guidance** — Tested with `qwen3.5:9b`: even with explicit system prompt instructions, small models chose `sql_query` and hallucinated column names. Structural removal is more reliable than prompt-level guidance.
- **Fix `sql_query` to use schema context** — Would duplicate the schema injection logic already in `nl_query`. Unnecessary complexity.
