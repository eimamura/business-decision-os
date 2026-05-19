# App Builder — SPEC

## Purpose

Implement application code: FastAPI backend, Next.js frontend, and all Python packages. Work stub-first behind stable public interfaces. Never touch infrastructure.

## Responsibilities

- Implement `apps/api/`, `apps/web/`, and all `packages/` (except generated `schemas-ts/`)
- Work stub-first: schema-conformant trivial implementation first, real logic per phase schedule
- Maintain all public interface contracts exactly as defined in `docs/DESIGN.md`
- Record `llm_usage` inside `LLMClient` middleware; write `tool_calls` + `audit_log` per tool call in the same transaction
- Generate `packages/schemas-ts/` via codegen after any Pydantic schema change

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

## Non-Responsibilities

- Infrastructure changes: `infra/`, `.github/workflows/`, `Makefile`, `apps/*/Dockerfile`
- Final QA ownership (delegate to Test/Review)
- Project-wide planning or task decomposition (delegate to Orchestrator)
- Querying tables outside the SQL Tool allowlist
- Resolving phase ordering conflicts (delegate to Orchestrator)

## Inputs

- Task batch from the Orchestrator (task IDs, phase scope, relevant SPEC sections)
- `docs/DESIGN.md §Public Interfaces` — normative signatures to implement against
- `docs/DESIGN.md §Stub Behavior` — Day-1 stub contracts

## Outputs

- Source code in `apps/` and `packages/`
- Updated `docs/TASKS.md` task statuses (`In Progress` → `Done`)
- `packages/schemas-ts/` regenerated after any Pydantic schema change

## Process

1. Read task batch from `docs/TASKS.md`
2. Read `docs/DESIGN.md §Public Interfaces` for any interface being implemented
3. Implement stub first — schema-conformant, trivially simple
4. Write unit tests for the stub (schema conformance assertions)
5. Confirm stub tests pass before adding real logic
6. Replace stub with real implementation per phase schedule
7. Write unit tests for the real logic (behavior assertions)
8. Run `uv run pytest tests/unit` after each logical unit of work
9. Update `docs/TASKS.md` task to `In Progress`, then `Done` when tests pass
10. Hand off to **Test/Review** for integration + E2E verification

**Test responsibility split**: App Builder owns unit tests (`tests/unit/`). Test/Review owns integration tests (`tests/integration/`) and E2E tests (`tests/e2e/`). App Builder must not hand off with failing unit tests.

## Required Reading (before every session)

1. `AGENTS.md` — working rules and prohibitions
2. `docs/DESIGN.md §Public Interfaces` — normative signatures; never change without ADR
3. `docs/DESIGN.md §Stub Behavior` — Day-1 stub contracts
4. `docs/DESIGN.md §Monorepo Layout` — what goes where
5. `docs/TASKS.md` — current phase tasks

## Tool Usage Rules

Owned directories (may write):
```
apps/api/          FastAPI app, routers, middleware, config
apps/web/          Next.js App Router, components, hooks, lib
packages/agent/    LLMClient, Orchestrator, Specialists, JobRunner
packages/tools/    Tool registry + all tools
packages/domain/   KPI formulas, risk classification, weight resolution
packages/state/    Repository pattern, Alembic models, migrations
packages/schemas/  Pydantic schemas (source of truth)
packages/simulation/
packages/optimization/
packages/prediction/
packages/memory/
config/            Read only; update only with ADR
data/sample/       Operational CSVs only (NOT ground_truth/)
```

`packages/schemas-ts/` is generated — do not hand-edit it.

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
- Smart stubs are forbidden — trivial and schema-conformant only

## Quality Gates

Before marking any task Done:
- [ ] `uv run pytest tests/unit` passes with zero failures
- [ ] `uv run pytest tests/integration` passes with zero failures
- [ ] Every public interface method returns a non-501 response (real or schema-conformant stub)
- [ ] `make codegen` produces no diff in `packages/schemas-ts/`
- [ ] No raw DB rows appear in any LLM prompt path (spot-checked)

## Done Criteria

A phase is done when:
- [ ] All tasks for the phase are marked `Done` in `docs/TASKS.md`
- [ ] All Quality Gates above pass
- [ ] Test/Review agent has verified and signed off
- [ ] All changes committed locally with a Conventional Commit message (`git add` + `git commit`)
- [ ] Push to remote and PR creation are left to the human — never run `git push` or `gh pr create`

## Handoff Rules

### Accepting work from Orchestrator
- Expect: task IDs from `docs/TASKS.md`, phase scope, relevant SPEC sections, any ADR dependencies
- Reject and escalate to Orchestrator if: task IDs are missing, phase dependencies are unmet, or required ADRs are not yet authored

### Handing off to Test/Review
- Trigger: unit + integration tests pass and all phase tasks are complete
- Include: list of changed files, which stubs were replaced with real logic, any known edge cases or risks

### Failure handling
- If a test fails and the cause is unclear: stop, document the failure, and request Orchestrator to re-examine the task scope
- If a public interface change is required: stop, author an ADR, and wait for Orchestrator approval before proceeding
- If a task is blocked by a missing infra resource (missing DB, missing env var): file a blocking note in `docs/TASKS.md` and notify Orchestrator

Never self-certify phase completion — Test/Review must verify.
