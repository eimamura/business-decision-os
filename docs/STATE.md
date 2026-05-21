# Execution State

Orchestrator-only write. Specialists do not write to this file.
TASKS.md holds task definitions. This file holds runtime execution state.

---

## Current Phase

M12 In Progress — Phase 12 Agent Trace Panel

## Active Lease

None

## Last Completed Batch

Phase 12 — M12 B1+B2 (T-12001 through T-12009) — 2026-05-21

## Last Validation

command: `uv run mypy packages/state/sessions_repo.py apps/api/routers/sessions.py apps/api/middleware.py --ignore-missing-imports`
exit code: 0 (all pass)
timestamp: 2026-05-21
note: T-12001 — alembic env.py async engine fix; T-12002 — migration 0004 memories.metadata→metadata_json; T-12003 — migration 0005 decision_sessions.user_id nullable; T-12004 — create_session persists to DB; T-12005 — DATABASE_URL in .env + docker-compose DB; T-12006 — RoutingDecisionEvent + input_summary/output_summary/ended_at fields; T-12007 — sse_queue wired into specialists; T-12008 — orchestrator routing_decision SSE; T-12009 — ReasoningPanel full trace UI rebuilt.

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
