# Execution State

Orchestrator-only write. Specialists do not write to this file.
TASKS.md holds task definitions. This file holds runtime execution state.

---

## Current Phase

M4 + M5 Complete — Ready for M6 (Real Predictor on Databricks)

## Active Lease

None

## Last Completed Batch

Phase 5 — M5 Complete (T-5001, T-5002, T-5003) — 2026-05-20

## Last Validation

command: `uv run pytest tests/unit/ -q && make lint && make typecheck && make build`
exit code: 0 (all pass)
timestamp: 2026-05-20
note: 165 unit tests PASS. M5 complete: CeleryJobRunner in packages/agent/job_runner/celery_runner.py, Celery app + tasks in celery_app.py, JOB_RUNNER_BACKEND=celery support in state.py, decisions endpoint returns job_id JSON when backend=celery + GET /{job_id}/status, Redis + celery-worker services in compose.yaml, azurerm_redis_cache in Terraform shared/, azurerm_container_app celery_worker in Terraform aca/. lint: 0 errors. typecheck: 0 errors. build: OK.

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
