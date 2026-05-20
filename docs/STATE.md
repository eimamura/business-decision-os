# Execution State

Orchestrator-only write. Specialists do not write to this file.
TASKS.md holds task definitions. This file holds runtime execution state.

---

## Current Phase

M8 Complete — Ready for M9 (Domain Expert specialist split)

## Active Lease

None

## Last Completed Batch

Phase 8 — M8 Complete (T-8001, T-8002, T-8003, T-8004) — 2026-05-20

## Last Validation

command: `uv run pytest tests/unit/ -q && make lint && make typecheck && make build`
exit code: 0 (all pass)
timestamp: 2026-05-20
note: 205 unit tests PASS. M8 complete: T-8001 — auto-execution policy: LOW-risk (service_level≥0.95) recommendations emit auto_execute=true + auto_executed SSE event instead of awaiting_approval; RecommendationReadyEvent gains auto_execute field; AutoExecutedEvent added. T-8002 — packages/lakehouse/ added (LakehouseClient, file-based local Delta simulation); infra/terraform/databricks/ extended with ADLS Gen2 storage account + Bronze/Silver/Gold containers + ETL cluster + Databricks Jobs. T-8003 — scripts/cdc_to_bronze.py with --dry-run mode. T-8004 — scripts/bronze_to_silver.py + scripts/silver_to_gold.py; packages/lakehouse/silver.py + gold.py; packages/lakehouse/cli.py with status/run-silver/run-gold commands. lint: 0 errors. typecheck: 0 errors. build: OK.

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
