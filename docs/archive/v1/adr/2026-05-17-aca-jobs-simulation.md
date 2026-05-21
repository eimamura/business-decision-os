# ADR: Azure Container Apps Jobs for simulation workloads

**Date:** 2026-05-17  
**Status:** Accepted  
**Deciders:** Engineering Team

## Context

Phase 2 moves CPU-bound inventory simulation off the API process. Azure Container Apps Jobs (US East 2, same environment as API/Web) provide on-demand execution with managed identity for ACR pull and Key Vault–backed secrets.

## Decision

1. Add `azurerm_container_app_job` for `simulation-worker` with **manual** trigger; API starts executions via Azure Resource Manager REST (`/start?api-version=2024-03-01`).
2. Dedicated image `apps/simulation-worker` (monorepo root build context) runs `run_job.py`, reads `JOB_RUN_ID`, updates `job_runs` in PostgreSQL.
3. `JOB_RUNNER_BACKEND=in_process` (default) for dev/CI; `aca` when `ACA_SIMULATION_JOB_RESOURCE_ID` is set.
4. `AcaJobsRunner` falls back to `InProcessJobRunner` when ACA resource ID is unset.

## Rationale

- Keeps `JobRunner` interface stable; only backend swaps.
- Manual trigger avoids KEDA/event complexity in Phase 2 while allowing API-driven dispatch.
- Worker shares the same `packages/simulation` code path as in-process execution.

## Trade-offs

- ACA Jobs require Azure subscription for full E2E validation; CI remains on `in_process`.
- ARM `/start` with template env overrides is less ergonomic than a queue; Celery (Phase 5) may replace this pattern.

## Consequences

- Terraform `aca` module exports `simulation_job_resource_id`.
- Deploy workflow builds and pushes `simulation-worker` image alongside API.
- API container needs `JOB_RUNNER_BACKEND`, `ACA_SIMULATION_JOB_RESOURCE_ID`, and managed identity with Job Contributor on the job resource.

## Reversibility

Re-evaluate when adding optimization jobs (Phase 3) or Celery (Phase 5); may consolidate to a single worker image with `JOB_KIND` routing.
