# Execution State

Orchestrator-only write. Specialists do not write to this file.
TASKS.md holds task definitions. This file holds runtime execution state.

---

## Current Phase

M6 Complete — Ready for M7 (Memory & Learning Loop / pgvector)

## Active Lease

None

## Last Completed Batch

Phase 6 — M6 Complete (T-6001, T-6002, T-6003, T-6004) — 2026-05-20

## Last Validation

command: `uv run pytest tests/unit/ -q && make lint && make typecheck && make build`
exit code: 0 (all pass)
timestamp: 2026-05-20
note: 172 unit tests PASS. M6 complete: LinearRegressionPredictor + DatabasePredictor in packages/prediction/__init__.py (scikit-learn, reads prediction_features table), ForecastTool upgraded to use real predictor (model_version=linear_regression_v1, adds prediction+source fields to output), Databricks Terraform in infra/terraform/databricks/ (workspace+MLflow+storage), training job in infra/databricks/jobs/train_predictor.py, batch inference job in infra/databricks/jobs/batch_inference.py. lint: 0 errors. typecheck: 0 errors. build: OK.

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
