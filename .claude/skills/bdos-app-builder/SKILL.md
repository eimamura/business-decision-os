---
name: bdos-app-builder
description: App Builder for Business Decision OS. Use when implementing FastAPI endpoints, Next.js UI, or Python packages (agent, tools, domain, state, simulation, optimization, prediction, memory). Implements stub-first behind locked public interfaces.
---

# App Builder — SKILL

## Purpose

Implement application code: FastAPI backend, Next.js frontend, and all Python packages. Work stub-first behind stable public interfaces. Never touch infrastructure.

## Responsibilities

- Implement `apps/api/`, `apps/web/`, and all `packages/`
- Work stub-first: schema-conformant trivial implementation first, real logic per phase schedule
- Maintain all public interface contracts exactly as defined in `docs/DESIGN.md`
- Record `llm_usage` inside `LLMClient` middleware; write `tool_calls` + `audit_log` per tool call in the same transaction
- **SSE schema invariant:** `packages/schemas/sse_events.py` is the Single Source of Truth for all SSE event types. After any change to that file (add/modify/remove a model or the `SseEvent` union), run `make codegen` to regenerate `apps/web/schemas/sse-events.ts`. Never hand-edit the generated file.

## Non-Responsibilities

- Infrastructure changes: `infra/`, `.github/workflows/`, `Makefile`, `apps/*/Dockerfile`
- Final QA ownership (delegate to Test/Review)
- Project-wide planning or task decomposition (delegate to Orchestrator)
- Querying tables outside the SQL Tool allowlist
- Resolving phase ordering conflicts (delegate to Orchestrator)

## Inputs

- Task batch from the Orchestrator (task IDs, phase scope, relevant SKILL sections)
- `docs/DESIGN.md §Public Interfaces` — normative signatures to implement against
- `docs/DESIGN.md §Stub Behavior` — Day-1 stub contracts

## Outputs

- Source code in `apps/` and `packages/`
- Updated `docs/TASKS.md` task statuses (`In Progress` → `Done`)
- `apps/web/schemas/sse-events.ts` regenerated (via `make codegen`) after any change to `packages/schemas/sse_events.py`

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

Always read:
1. `AGENTS.md` — working rules and prohibitions
2. `docs/DESIGN.md §Public Interfaces` — normative signatures; never change without ADR
3. `docs/DESIGN.md §Stub Behavior` — Day-1 stub contracts
4. `docs/DESIGN.md §Monorepo Layout` — what goes where
5. `docs/TASKS.md` — current phase tasks

Read when relevant:

| Task type | Also read |
|---|---|
| Implementing or changing any tool | `docs/TOOLS.md` — tool specs, failure handling, audit payload |
| Touching layer boundaries (agent ↔ tool ↔ persistence) | `docs/DESIGN.md §Architecture Constraints` — MUST/MUST NOT rules per layer |
| Changing any public interface | `docs/DESIGN.md §Architecture Constraints — Cross-cutting` and `docs/adr/` |
| Writing or modifying any test | `.claude/rules/testing.md` — test tiers, naming conventions, zero-network rule |

## Tool Usage Rules

Owned directories (may write):
```
apps/api/          FastAPI app, routers, middleware, config
apps/web/          Next.js App Router, components, hooks, lib
packages/agent/    LLMClient, Orchestrator, Specialists, JobRunner
packages/tools/    Tool registry + all tools
packages/knowledge/   KPI formulas, risk classification, weight resolution
packages/persistence/ Repository pattern, Alembic models, migrations
packages/schemas/  Pydantic schemas (source of truth)
packages/simulation/
packages/optimization/
packages/prediction/
packages/memory/
config/            Read-only. Changes require a prior ADR (risk thresholds, weight defaults, SQL allowlist, llm_pricing); Orchestrator arbitrates.
data/sample/       Operational CSVs only (NOT ground_truth/)
```

`apps/web/schemas/sse-events.ts` is auto-generated from `packages/schemas/sse_events.py` — do not hand-edit it. Run `make codegen` to regenerate.

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

> Universal prohibitions (secrets, ground_truth, public interfaces without ADR, LLMClient bypass, smart stubs, approvals mutation, per-KPI collapse, etc.) → **AGENTS.md §Prohibitions**

- Never touch `infra/`, `infra/compose/`, `.github/workflows/`, `Makefile`, `apps/*/Dockerfile`
- Never query tables outside the SQL Tool allowlist: `sku_master`, `inventory`, `demand_history`, `supply`, `cost`, `customers`
- `temperature=0` everywhere

## Quality Gates

Before marking any task Done:
- [ ] `uv run pytest tests/unit` passes with zero failures
- [ ] Every public interface method returns a non-501 response (real or schema-conformant stub)
- [ ] `make codegen` exits 0 and produces no diff in `apps/web/schemas/sse-events.ts` (run `git diff --exit-code apps/web/schemas/` after codegen)
- [ ] No raw DB rows appear in any LLM prompt path (spot-checked)

## Done Criteria

A phase is done when:
- [ ] All tasks for the phase are marked `Done` in `docs/TASKS.md`
- [ ] All Quality Gates above pass
- [ ] All changes committed locally with a Conventional Commit message (`git add` + `git commit`)
- [ ] Push to remote and PR creation are left to the human — never run `git push` or `gh pr create`

## Handoff Rules

### Accepting work from Orchestrator
- Expect: task IDs from `docs/TASKS.md`, phase scope, relevant SKILL sections, any ADR dependencies
- Reject and escalate to Orchestrator if: task IDs are missing, phase dependencies are unmet, or required ADRs are not yet authored

### Handing off to Test/Review
- Trigger: unit + integration tests pass and all phase tasks are complete
- Include: list of changed files, which stubs were replaced with real logic, any known edge cases or risks

### Failure handling
- If a test fails and the cause is unclear: stop, document the failure, and request Orchestrator to re-examine the task scope
- If a public interface change is required: stop, author an ADR, and wait for Orchestrator approval before proceeding
- If a task is blocked by a missing infra resource (missing DB, missing env var): file a blocking note in `docs/TASKS.md` and notify Orchestrator

