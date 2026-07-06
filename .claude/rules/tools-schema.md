---
paths:
  - "packages/tools/**/*.py"
---
# Tools — Schema Context Rules

- Never hardcode table names, column names, or schema descriptions as string literals
  in tool code or LLM prompts. Use `get_schema_context()` from
  `packages/tools/schema_context.py` for any schema information passed to an LLM.
- Static `FEW_SHOT_EXAMPLES` strings that reference table or column names are prohibited.
  Generate examples dynamically from `get_schema_context()` output instead.
- All tables referenced in tool SQL queries must appear in `ALLOWED_READ_TABLES`
  in `packages/tools/sql_allowlist.py`. If a migration renames a table, update
  `ALLOWED_READ_TABLES` and any hardcoded SQL in `packages/tools/` in the same task.

See `AGENTS.md §Prohibitions` (schema-hardcoding items) for the project-wide prohibition.
