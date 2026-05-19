# App Builder — Agent Spec

## Purpose

Implement application code: FastAPI backend, Next.js frontend, and all Python packages. Work stub-first behind stable public interfaces. Never touch infrastructure.

## Required Reading (before every session)

1. `AGENTS.md` — working rules and prohibitions
2. `DESIGN.md` §Public Interfaces — normative signatures; never change without ADR
3. `DESIGN.md` §Stub Behavior — Day-1 stub contracts
4. `DESIGN.md` §Monorepo Layout — what goes where
5. `TASKS.md` — current phase tasks

## Owned Directories

```
apps/api/          FastAPI app, routers, middleware, config
apps/web/          Next.js App Router, components, hooks, lib
packages/agent/    LLMClient, Orchestrator, Specialists, JobRunner
packages/tools/    Tool registry + SQL/Approval/Audit/Forecast/Sim/Opt/Eval tools
packages/domain/   KPI formulas (kpi.py), risk classification, weight resolution
packages/state/    Repository pattern, Alembic models, migrations
packages/schemas/  Pydantic schemas (source of truth)
packages/simulation/   Simulator implementations
packages/optimization/ Optimizer implementations
packages/prediction/   Predictor implementations
packages/memory/   MemoryStore implementations
config/            risk_thresholds.yaml, kpi_weights*.csv (read; update only with ADR)
data/sample/       Operational CSVs (NOT ground_truth/)
```

`packages/schemas-ts/` is generated from Pydantic — do not hand-edit it.

## Responsibilities

### Per-Phase Focus

| Phase | Work |
|---|---|
| 0 | Protocol classes + Pydantic schemas + KPI formulas + migration 0001 + repository stubs |
| 1 | ClaudeClient, Orchestrator loop, 4 PromptBasedSpecialists, all tools (SQL/Approval/Audit real; Forecast/Sim/Opt stubs), Evaluator, MemoryStore stub, Chat + full UI |
| 2 | Replace Simulation stub with real InventorySimulator; wire ACA JobRunner |
| 3 | Replace Optimization stub with OR-Tools CP-SAT optimizer; wire ACA JobRunner |
| 4 | Revision loop, budget interceptor in LLMClient, Settings/Policies screen |
| 5 | Swap InProcessJobRunner → CeleryJobRunner (callers unchanged) |
| 6 | Predictor implementation (scikit-learn); realtime inference in FastAPI |
| 7 | MemoryStore stub → pgvector retrieval; weight-vector hooks in Orchestrator |
| 8 | Risk-classified auto-execution policy in Approval flow |
| 9 | Split Domain Expert into 5 specialists; swap to AgentBasedSpecialist |

### Always

- Implement stubs first; make tests pass; then replace with real logic
- Assert schema conformance; never assert numerical accuracy of stubs
- Record every `llm_usage` row from inside `LLMClient` (never call-site)
- Write one `tool_calls` + one `audit_log` row per tool invocation in the same transaction
- Keep LLM context sanitized — no raw DB rows; summaries / aggregates only
- Generate `packages/schemas-ts/` via codegen after any Pydantic schema change

## Public Interface Rules

These signatures are locked. **Any change requires an ADR before coding:**

- `LLMClient.complete / stream / embed`
- `Tool.handle(input, ctx) → ToolResult`
- `JobRunner.submit / status / result / cancel`
- `Simulator.run(input) → SimulationOutput`
- `Optimizer.run(input) → OptimizationOutput`
- `MemoryStore.write / search`
- `Orchestrator.run / resume`
- Approval state machine: `pending → approved | rejected | needs_revision | expired`

## Constraints

- Never touch `infra/`, `infra/compose/`, `.github/workflows/`, `Makefile`, `apps/*/Dockerfile`
- Never query tables outside the SQL Tool allowlist: `sku_master`, `inventory`, `demand_history`, `supply`, `cost`, `customers`
- Never read `data/sample/ground_truth/`
- Never collapse per-KPI scores into a single weighted total inside the Evaluator
- Never mutate a closed `approvals` row — create a new row with `parent_approval_id`
- Never call the Anthropic SDK directly — always go through `LLMClient`
- `temperature=0` everywhere
