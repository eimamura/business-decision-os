# Execution State

Orchestrator-only write. Specialists do not write to this file.
TASKS.md holds task definitions. This file holds runtime execution state.

---

## Current Phase

M13 Done — Phase 13 SQL Intelligence Tools

## Active Lease

None

## Last Completed Batch

Phase 13 — M13 B1 (T-13001 through T-13006) — 2026-05-21

## Last Validation

command: `uv run mypy packages/tools/ --ignore-missing-imports && uv run ruff check packages/tools/ && uv run pytest tests/unit/ -q`
exit code: 0 (all pass)
timestamp: 2026-05-21
note: T-13001 — NlQueryTool (text-to-SQL, Haiku, prompt caching, 60s cache, MAX_RETRIES=2, sqlparse guardrail); T-13002 — SqlQueryTool uses get_pool(); T-13003 — validate_query() implemented; T-13004 — nl_query added to role allowlist; T-13005 — NlQueryTool registered in create_tool_registry(); T-13006 — sqlparse>=0.5 added to api deps. 206 unit tests pass.

## Blockers

None

## Scope Violations

None

---

## Field Definitions

| Field | Purpose |
|---|---|
| **Active Lease** | Batch ID currently being executed (e.g. `B01`). Set at turn start, cleared at turn end. Prevents concurrent writes if harness is re-entered mid-batch. |
| **Last Completed Batch** | Most recently finished batch ID + name. Used as re-entry point when `/goal` resumes. |
| **Last Validation** | Command run, exit code, and timestamp from the most recent Test/Review check. |
| **Blockers** | Structured blocker entries. Format: `B<batch>: <description>`. Cleared when resolved. |
| **Scope Violations** | Any out-of-scope action detected by Test/Review (e.g. specialist touching Phase 2 tasks). |

## Update Protocol

Orchestrator updates this file at the **end of every turn**, in this order:

1. Clear `Active Lease`
2. Set `Last Completed Batch`
3. Set `Last Validation` (from Test/Review output)
4. Update `Blockers` (add or remove)
5. Update `Scope Violations` if any

Orchestrator sets `Active Lease` at the **start of every turn** before spawning a specialist.
