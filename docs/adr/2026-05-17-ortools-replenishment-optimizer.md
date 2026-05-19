# ADR: OR-Tools replenishment optimizer

**Date:** 2026-05-17  
**Status:** Accepted  
**Deciders:** Engineering Team

## Context

Phase 3 replaces the enumeration stub in `OptimizationTool` with a real optimizer behind the `Optimizer` protocol. The tool contract requires ≥3 candidates with `action`, `simulation`, `total_supply_chain_cost`, and constraint fields. Simulation must run through `JobRunner` (Phase 2), not inline SQL.

## Decision

1. Define `Optimizer` in `packages/optimization/` with `ReplenishmentOptimizer` as the Phase 3 implementation.
2. Use **Google OR-Tools CP-SAT** to select the minimum-cost feasible MOQ multiplier among pre-evaluated options (`m ∈ {0,…,5}`).
3. Evaluate each multiplier by submitting a nested `kind=simulation` job (audit trail in `job_runs`).
4. Return the three lowest-cost feasible candidates (relax constraints when fewer than three exist, matching Phase 1 stub behavior).
5. Route `kind=optimization` through `JobRunner`; production uses a dedicated ACA Job (`ACA_OPTIMIZATION_JOB_RESOURCE_ID`).

## Rationale

- OR-Tools is already named in `TASKS.md` and `DESIGN.md`; CP-SAT gives a deterministic, explicit optimization step without a full multi-SKU MIP in MVP.
- Pre-evaluation + CP-SAT keeps the model simple while honoring the “real optimizer” milestone.
- Nested simulation jobs preserve audit consistency with Phase 2.

## Trade-offs

- Up to six simulation jobs per optimize call increases `job_runs` volume (acceptable until Celery in Phase 5).
- CP-SAT on six points is heavier than pure sort; it establishes the optimizer hook for Phase 3+ constraint growth.
- OR-Tools increases container image size.

## Consequences

- `ortools` dependency in `packages/optimization/`.
- `OptimizationTool` delegates to `JobRunner`; orchestrator wiring unchanged.
- Terraform adds a second ACA Job for optimization workloads.

## Reversibility

Re-evaluate if multi-SKU or continuous order quantities require a different solver; document in a new ADR before changing public `Optimizer` signatures.
