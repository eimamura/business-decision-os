# MIGRATION_PLAN.md

## Purpose

Define the safe order in which to refactor the codebase toward the DESIGN.md target state.

This document answers three questions that DESIGN.md, TASKS.md, and TESTING.md do not:
1. In what order do we break things?
2. What checkpoint must pass before moving to the next phase?
3. Where is the rollback point if a phase fails?

---

## Principle

**Protect first. Refactor from leaf nodes upward.**

External contracts are locked before any internal structure changes.
Layers with fewer dependencies are refactored before layers that depend on them.
Each phase ends with a named checkpoint; the next phase does not begin until the checkpoint passes.

**Test execution is deferred to Phase 6.**
Checkpoints in Phases 1–5 use static analysis only (grep, mypy, ruff).
Running the full test suite at every phase creates long feedback loops during rapid structural refactoring.
The Phase 0 contract tests serve as the regression gate; they are re-run once in Phase 6, not per phase.

Dependency order (bottom = safest to change first):

```
Orchestrator          ← depends on everything below
  └─ Domain / Analytical Agents  ← depend on Tools, Memory, Guardrail
       ├─ Tool Layer              ← depend only on external systems + LLMClient
       ├─ Memory Layer            ← standalone
       └─ Guardrail Layer         ← depends on state
```

---

## Phase R — Structural Rename (prerequisite; no production logic changed)

**Goal**: Align package directory names with DESIGN.md vocabulary before any code refactoring begins.
All subsequent phases assume these names are in place.

**Why first**: Renaming after code refactoring has started multiplies merge conflicts. Doing it first is a purely mechanical pass that leaves all logic intact.

**Actions**:
- Rename `packages/state/` → `packages/persistence/`; update all Python imports in `apps/api/`, `packages/agent/`, `packages/tools/`, `tests/`
- Rename `packages/domain/` → `packages/knowledge/`; update all Python imports in `packages/agent/`, `packages/tools/`, `apps/api/`, `tests/`
- Rename `packages/agent/job_runner/` → `packages/agent/runner/`; update all imports in `apps/api/`, `apps/*-worker/`
- Rename 6 test files with phase/ticket codes to descriptive names:
  - `test_b03_state.py` → `test_persistence_approvals.py`
  - `test_b11_b12_phase1.py` → `test_tool_isolation.py`
  - `test_phase1_integration.py` → `test_tool_layer_integration.py`
  - `test_phase4_b4a.py` → `test_agent_reclassification.py`
  - `test_m8_auto_execution.py` → `test_job_runner_execution.py`
  - `test_m8_lakehouse.py` → `test_lakehouse_pipeline.py`
- Update `pyproject.toml` workspace member paths for renamed packages
- Update `AGENTS.md` commit scope table: `state` → `persistence`, `domain` → `knowledge`
- Add `§Monorepo Layout`, `§Public Interfaces`, `§Phase Progression` to `docs/DESIGN.md`

**Checkpoint**:
```bash
uv run pytest --tb=short
uv run mypy --config-file pyproject.toml
uv run ruff check .
# Must return 0 hits:
grep -r "packages/state\|job_runner\|packages/domain" . \
  --include="*.py" --include="*.toml" --include="*.md" \
  | grep -v ".git" | grep -v "__pycache__"
```

**Rollback**: `git tag phase-r-start` before changes begin; `git checkout phase-r-start -- packages/ tests/ pyproject.toml AGENTS.md docs/DESIGN.md` if checkpoint fails.

**Git tag**: `git tag phase-r-complete` when checkpoint passes.

---

## Phase 0 — Protect (prerequisite; no production code deleted)

**Goal**: Lock external behavior before touching internals.

**Actions**:
- Finalize `docs/CONTRACTS.md` (all items must be specific, not placeholder)
- Add contract tests in `tests/` covering every item in CONTRACTS.md:
  - Health check returns 200
  - Session create → retrieve round-trip
  - Approval state machine enforces terminal states
  - Audit log is append-only
  - SSE stream ends with `done` or `error`
  - `RuntimeError` is raised when `ANTHROPIC_API_KEY` is missing
- Run full existing test suite; record baseline pass count in `docs/TESTING.md`

**Checkpoint**: Contract tests pass. No existing tests newly failing vs baseline.

**Rollback**: None needed — Phase 0 is additive only.

**Git tag**: `git tag phase0-complete` when checkpoint passes.

---

## Phase 1 — Tool Layer Isolation

**Goal**: All execution logic lives in `packages/tools/`; agents never call DB, LLM provider SDK, or external systems directly.

**Files touched**: `packages/tools/`, `packages/agent/specialists/`, `packages/agent/orchestrator/`

**Actions**:
- Audit `packages/agent/specialists/agent_based.py` and `base.py` for direct SQLAlchemy usage or `anthropic` SDK calls; extract any found into `packages/tools/`
- Audit `packages/agent/orchestrator/__init__.py` and `weights.py` for the same; extract
- Confirm every tool in `packages/tools/` inherits from `packages/tools/base.py:Tool`
- Confirm all LLM calls go through `packages/agent/llm/`

**Checkpoint** (static analysis only — no pytest):
```bash
# Must return 0 results (outside the llm/ subdirectory):
grep -rn "import anthropic\|from anthropic" packages/agent/ | grep -v "packages/agent/llm"
grep -rn "from sqlalchemy\|import sqlalchemy" packages/agent/
```

**Rollback**: `git tag phase1-start` before changes begin; `git checkout phase1-start -- packages/` if checkpoint fails.

---

## Phase 2 — Memory Layer Formalization

**Goal**: `packages/memory/` exports six typed memory classes; no raw dict is passed as "memory" between components.

**Files touched**: `packages/memory/`, `packages/agent/history.py`, `packages/agent/specialists/`

**Actions**:
- Implement in `packages/memory/__init__.py`:
  - `ShortTermMemory` — current conversation context only
  - `WorkingMemory` — in-progress task state and intermediate results
  - `LongTermMemory` — cross-session persistent knowledge
  - `DecisionMemory` — reasoning records, alternatives considered, rejection reasons
  - `UserMemory` — user preferences and context
  - `DomainMemory` — business rules, KPI definitions, domain knowledge
- Migrate `packages/agent/history.py` usage to `ShortTermMemory` or `WorkingMemory` as appropriate
- Remove any `dict`-typed "memory" parameters in agent method signatures

**Checkpoint** (static analysis only — no pytest):
```bash
python -c "from packages.memory import ShortTermMemory, WorkingMemory, LongTermMemory, DecisionMemory, UserMemory, DomainMemory; print('ok')"
uv run mypy packages/memory/
```

**Rollback**: `git tag phase2-start` before changes begin.

---

## Phase 3 — Guardrail Layer Separation

**Goal**: All permission and approval checks are consolidated in a single Guardrail module; no scattered `if permission` or `if approval` checks in agent or tool code.

**Files touched**: `packages/agent/`, `apps/api/middleware.py`; new `packages/guardrails/` (or extend `packages/tools/`)

**Actions**:
- Search for ad-hoc permission/approval checks in agent and router code:
  ```bash
  grep -rn "permission\|approval\|can_execute\|requires_approval" packages/agent/ apps/api/routers/
  ```
- Consolidate into a Guardrail module exposing: `can_execute(action, context)`, `needs_approval(action, context)`, `audit_required(action)`
- Agents call Guardrail; they never own the permission logic
- Approval state enforcement remains in `packages/persistence/approvals.py` (domain layer); Guardrail calls it

**Checkpoint** (static analysis only — no pytest):
```bash
# No direct permission logic in agent code (outside guardrail module):
grep -rn "requires_approval\|can_execute" packages/agent/ | grep -v "guardrail"
# Should return 0 hits
```

**Rollback**: `git tag phase3-start` before changes begin.

---

## Phase 4 — Agent Reclassification

**Goal**: `packages/agent/specialists/` is replaced by `packages/agent/domain/` and `packages/agent/analytical/`, mapping to Domain Agents + Analytical Agents as defined in DESIGN.md.

**Files touched**: `packages/agent/specialists/`, new `packages/agent/domain/`, new `packages/agent/analytical/`

**Actions**:
- Map pre-classification roles in `agent_based.py` to DESIGN.md classifications:
  - Domain Agents (`packages/agent/domain/`): demand, inventory, replenishment, procurement, supplier, production, logistics
  - Analytical Agents (`packages/agent/analytical/`): exception, scenario, ranking, root_cause
- Create one class per agent in the appropriate subdirectory
- Verify each agent class conforms to ARCHITECTURE_RULES.md boundaries for its classification
- Remove `packages/agent/specialists/` after all references are migrated

**Checkpoint** (static analysis only — no pytest):
- Every agent class name has a corresponding row in the DESIGN.md agent classification table
- `packages/agent/specialists/` directory does not exist
- ARCHITECTURE_RULES.md domain-agent and analytical-agent rules confirmed by grep

**Rollback**: `git tag phase4-start` before changes begin.

---

## Phase 5 — Orchestrator Responsibility Cleanup

**Goal**: Orchestrator contains only: intent analysis, planning, routing, aggregation, conflict detection, scoring, response generation. No domain logic.

**Files touched**: `packages/agent/orchestrator/`

**Actions**:
- Audit `packages/agent/orchestrator/weights.py` for domain-specific constants or supply-chain thresholds; move to appropriate Domain Agent or `packages/knowledge/`
- Audit `packages/agent/orchestrator/__init__.py` for any domain reasoning that should belong to a specialist
- Confirm Orchestrator never holds supply chain domain knowledge as hardcoded values

**Checkpoint** (static analysis only — no pytest):
```bash
# Orchestrator should not reference supply chain domain constants:
grep -n "safety_stock\|reorder_point\|lead_time\|service_level" packages/agent/orchestrator/
# Should return 0 hits (or be moved to knowledge/ or a specialist)
```

**Rollback**: `git tag phase5-start` before changes begin.

---

## Phase 6 — Final Validation

**Goal**: Confirm the full system matches DESIGN.md target state.

**Checklist**:
- [ ] All Phase 0 contract tests pass
- [ ] Full pytest suite passes (no new failures vs Phase 0 baseline)
- [ ] mypy passes across all packages
- [ ] ruff/lint passes
- [ ] Code layer structure matches DESIGN.md 7-layer diagram and §Monorepo Layout
- [ ] ARCHITECTURE_RULES.md cross-cutting rules confirmed by grep or arch tests
- [ ] DEFERRED.md items have not been implemented (scope check)
- [ ] TASKS.md completion criteria reviewed

---

## What This Plan Does NOT Cover

- UI/frontend refactoring (see DEFERRED.md — UI redesign is deferred)
- Lakehouse schema changes (see DEFERRED.md — frozen during refactoring)
- Adding new Domain Agents beyond current specialists (new scope, requires TASKS.md update)
- Performance optimization (separate concern)
