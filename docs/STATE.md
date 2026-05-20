# Execution State

Orchestrator-only write. Specialists do not write to this file.
TASKS.md holds task definitions. This file holds runtime execution state.

---

## Current Phase

M3 Complete — Ready for Phase 4 (M4: Approval Workflow Expansion + LLM budget enforcement)

## Active Lease

None

## Last Completed Batch

Fail-loud + SSE Chat wiring — 2026-05-19

## Last Validation

command: `uv run pytest tests/unit/ -x -q`
exit code: 0 (all pass)
timestamp: 2026-05-19
note: 128 unit tests PASS. Fail-silent fallbacks eliminated: ANTHROPIC_API_KEY missing → RuntimeError; anthropic package missing → ImportError propagated; ACA config missing → RuntimeError; decisions.py bare except replaced with logging + SSE error event; evaluator_tool.py missing thresholds → WARNING log. Chat UI (page.tsx) now subscribes to SSE stream after POST /messages: reply displayed in chat bubble on `done`, red error bubble on `error`.

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
