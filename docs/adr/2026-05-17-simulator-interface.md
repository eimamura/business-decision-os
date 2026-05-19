# ADR: Simulator interface and inventory simulation package

**Date:** 2026-05-17  
**Status:** Accepted  
**Deciders:** Engineering Team

## Context

Phase 2 replaces the in-tool SQL projection stub with a real `InventorySimulator` in `packages/simulation/`, executed through `JobRunner`. The `Simulator` protocol was referenced in `DESIGN.md` layout but not listed in §Public Interfaces. Simulation output must remain identical to the Phase 1 tool contract (`sku_id`, `ending_on_hand`, `stockout_days`, `mean_lead_time_days`) so the UI and Evaluator do not change.

## Decision

1. Define `SimulationInput`, `SimulationOutput`, `SimulationContext`, and `Simulator` in `packages/simulation/`.
2. Implement `InventorySimulator` with the same deterministic mean-demand / mean-lead-time projection as the Phase 1 stub, optionally persisting `daily_on_hand` to `simulation_results` when `session_id` is present.
3. Route all simulation execution through `JobRunner` (`kind=simulation`); `SimulationTool` delegates to `submit` + `result(wait=True)`.
4. Use `InProcessJobRunner` in dev/CI; use `AcaJobsRunner` in production when ACA Job resource ID and Azure credentials are configured.

## Rationale

- Separates domain simulation from tool/audit wiring and enables ACA Jobs without changing tool schemas.
- Keeps Phase 2 intentionally simple (no stochastic model) while making the contract explicit for Phase 3+.
- Idempotency via `job_runs.idempotency_key` matches existing DESIGN concurrency rules.

## Trade-offs

- `Simulator` is documented in DESIGN §Public Interfaces after this ADR; it is not a breaking change to existing tool JSON.
- ACA path adds operational complexity; `JOB_RUNNER_BACKEND=in_process` remains the default for local and CI.

## Consequences

- `packages/simulation/` is the single home for simulation logic.
- `agent` depends on `simulation`; `tools` receive `JobRunner` via `ToolContext` to avoid import cycles.
- Terraform adds `azurerm_container_app_job` and a `simulation-worker` image.

## Reversibility

Re-evaluate if we introduce GPU/stochastic simulators requiring a different payload shape; that would need a new ADR and versioned `SimulationOutput`.
