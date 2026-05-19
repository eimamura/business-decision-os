# Execution State

Orchestrator-only write. Specialists do not write to this file.
TASKS.md holds task definitions. This file holds runtime execution state.

---

## Current Phase

M0+1 Complete — Ready for Phase 2 (M2: Real Simulator on ACA Jobs)

## Active Lease

None

## Last Completed Batch

E2E Validation — M0+1 smoke tests + T-1042 Playwright suite — 2026-05-19

## Last Validation

command: `uv run pytest tests/e2e/ -v` + `npx playwright test --reporter=list`
exit code: 0 (all pass)
timestamp: 2026-05-19
note: 5 httpx E2E PASS; 6 Playwright PASS (chat session UUID navigation, send button state, sidebar undefined guard); Chat Runtime Smoke Gate clear (no undefined/405 in recent logs)

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
