# Execution State

Orchestrator-only write. Specialists do not write to this file.
TASKS.md holds task definitions. This file holds runtime execution state.

---

## Current Phase

M4 Complete — Ready for Phase 5 (M5: Celery + Redis job queue)

## Active Lease

None

## Last Completed Batch

Phase 4 — B4C Test/Review (T-4001, T-4002, T-4003, T-4004) — 2026-05-20

## Last Validation

command: `uv run pytest tests/unit/ -x -q && make lint && make typecheck && make build`
exit code: 0 (all pass)
timestamp: 2026-05-20
note: 154 unit tests PASS. M4 complete: notifications table + repo, policies table + repo, approver role enforcement (403 for non-approver), BudgetGuard/BudgetedClaudeClient/BudgetSoftLimitWarning/BudgetHardLimitError in LLMClient, PUT /api/v1/policies, GET /api/v1/notifications, /settings Next.js page. lint: 0 errors. typecheck: 0 errors. build: OK.

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
