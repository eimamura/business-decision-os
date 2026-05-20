# Execution State

Orchestrator-only write. Specialists do not write to this file.
TASKS.md holds task definitions. This file holds runtime execution state.

---

## Current Phase

M7 Complete — Ready for M8 (Semi-Autonomous Execution + Databricks Lakehouse)

## Active Lease

None

## Last Completed Batch

Phase 7 — M7 Complete (T-7001, T-7002, T-7003) — 2026-05-20

## Last Validation

command: `uv run pytest tests/unit/ -q && make lint && make typecheck && make build`
exit code: 0 (all pass)
timestamp: 2026-05-20
note: 182 unit tests PASS. M7 complete: PgVectorMemoryStore in packages/memory/__init__.py (asyncpg, deterministic hash embeddings, cosine similarity search via pgvector), memory write hook in Orchestrator (_write_decision_memory writes user_policy after each recommendation), retrieval hook (_resolve_weights_with_memory queries pgvector before resolve_weights), API wires PgVectorMemoryStore when DATABASE_URL set. SSE emits memory_retrieved events. lint: 0 errors. typecheck: 0 errors. build: OK.

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
