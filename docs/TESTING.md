# TESTING.md

## Phase Baselines

### Phase 0 Baseline — 2026-05-21

Command: `pytest tests/unit/ --tb=short -q`

| Result | Count |
|---|---|
| Passed | 213 |
| Failed | 3 (pre-existing — see below) |

New tests added in Phase 0: `tests/unit/test_contracts.py` (10 tests covering P0-2 through P0-7).

**Pre-existing failures** (carried forward from Phase R; all require a live PostgreSQL connection):

| Test | Reason |
|---|---|
| `test_persistence_approvals.py::test_sessions_repo_raises` | Expects `RuntimeError("DATABASE_URL not set")`; fails with `ConnectionRefusedError` when `DATABASE_URL` is set but no Postgres is running |
| `test_persistence_approvals.py::test_llm_usage_repo_raises` | Same cause |
| `test_tool_isolation.py::test_sql_tool_no_db_returns_empty` | Expects a `"note"` key in the error result; receives a raw connection error dict instead |

These 3 tests are **pre-existing** and do not represent Phase 0 regressions.
They will be addressed or reclassified in Phase 1.

---

## Purpose

This document defines the testing strategy for the large-scale refactoring.

The goal of testing is not to preserve the old internal structure.  
The goal is to preserve critical external behavior while moving the system toward the architecture defined in `DESIGN.md`.

Tests must support the new design, not block it.

---

## Current Focused Verification Notes

### SQL Guardrail Hardening — 2026-05-23

The SQL read guardrail is covered by `tests/unit/test_tool_isolation.py`.

Focused command:

```
pytest tests/unit/test_tool_isolation.py -q
```

Coverage expectations:

- `SELECT * FROM sku_master`, `SELECT * FROM public.sku_master`, and `SELECT * FROM "sku_master"` are accepted.
- Table-less `SELECT`, multi-statement SQL, write operations, `COPY`, and dangerous functions such as `pg_sleep` are rejected.
- Non-allowlisted tables are rejected through plain identifiers, quoted identifiers, joins, comma joins, CTEs, subqueries, and `UNION` branches.
- `SqlQueryTool` and `NlQueryTool` return guardrail errors without executing blocked SQL.

Environment-dependent commands:

- `pytest tests/unit/test_data_access_tools_integration.py -q` requires a live PostgreSQL database; without it, the data access tools use their no-database fallback and integration assertions fail.
- `pytest tests/ -x -q` currently stops on the known `tests/unit/test_contracts.py` import issue for `sse_queues` from `apps.api.state`.

---

## Core Principle

During large-scale refactoring, not all existing tests are authoritative.

Existing tests must be classified before being fixed.

A failing test does not automatically mean the implementation is wrong.  
It may mean the test is tied to the old architecture.

---

## Test Classification

All tests must be classified into one of the following categories.

### 1. Contract Tests

These tests protect external behavior.

They must be preserved unless an intentional breaking change is documented.

Examples:

- Public API behavior
- Request and response formats
- Authentication and authorization
- Persistence behavior
- User-visible behavior
- Critical workflows
- Error response behavior

Contract tests are the highest priority.

---

### 2. Integration Tests

These tests protect major system flows.

They should be preserved or updated to match the new architecture.

Examples:

- User request reaches Orchestrator
- Orchestrator creates a plan
- Orchestrator routes work to agents
- Agents call tools through the correct boundary
- Tool results return to Orchestrator
- Final response is generated
- Memory or audit behavior is triggered when required

Integration tests should verify behavior, not old module structure.

---

### 3. Architecture Boundary Tests

These tests protect the new architecture defined in `DESIGN.md`.

They should be added or rewritten during the refactoring.

Examples:

- Orchestrator handles planning, routing, aggregation, and response generation
- Domain Agents contain domain-specific responsibilities
- Analytical Agents contain cross-domain analysis responsibilities
- Tool logic is separated from Agent logic
- Memory access is explicit and controlled
- Guardrail logic is centralized
- Agents do not bypass Guardrails
- Legacy architecture is not reintroduced

Architecture tests should reflect the target design, not the old implementation.

---

### 4. Legacy Internal Tests

These tests depend on the old internal structure.

They are not automatically authoritative.

Examples:

- Tests tied to old class names
- Tests tied to old file structure
- Tests tied to obsolete module boundaries
- Tests for temporary MVP implementation details
- Tests for completed phase-specific behavior
- Tests that force Orchestrator, Agent, Tool, Memory, or Guardrail responsibilities into the old structure

These tests should be removed, suspended, or rewritten.

The goal is not to make all legacy internal tests pass.  
The goal is to replace them with tests that support `DESIGN.md`.

---

## Failing Test Policy

Do not blindly fix all failing tests.

Each failing test must be classified first.

Use the following categories:

### Regression

The test protects valid external behavior or valid business logic.

Action: fix the implementation.

### Outdated Legacy Test

The test depends on old internal structure that conflicts with `DESIGN.md`.

Action: remove, suspend, or rewrite the test.

### Architecture Test to Rewrite

The test checks a valid concern, but its assumptions are tied to the old architecture.

Action: rewrite the test according to `DESIGN.md`.

### Missing New Test

The current test suite does not cover an important new boundary.

Action: add a new test.

### Unclear Behavior

It is not clear whether the behavior should be preserved.

Action: stop and request human decision.

---

## Refactoring Test Strategy

The refactoring must follow this testing order.

### Step 1: Protect External Behavior

Identify and preserve tests that protect public behavior.

Focus on:

- API contracts
- Authentication
- Persistence
- Critical user flows
- Error handling
- Smoke tests

These tests define what must not break.

---

### Step 2: Classify Existing Tests

Before fixing failing tests, classify them as:

- Contract Test
- Integration Test
- Architecture Boundary Test
- Legacy Internal Test

Do not spend time fixing legacy tests before classification.

---

### Step 3: Rewrite Internal Tests

Internal tests should be rewritten to match the new architecture.

They should verify:

- Orchestrator responsibilities
- Agent boundaries
- Tool boundaries
- Memory behavior
- Guardrail behavior
- Workflow behavior

They should not preserve obsolete internal structure.

---

### Step 4: Add Architecture Boundary Tests

Add tests that prevent the system from drifting back to the old design.

These tests should make sure:

- Orchestrator does not absorb all domain logic
- Agents do not directly implement tools
- Tools do not contain orchestration logic
- Memory is not treated as simple logging
- Guardrails are not scattered across agents
- Domain Agents and Analytical Agents remain conceptually separate

---

### Step 5: Final Verification

Only after test classification and rewriting, run the full verification suite.

Required verification:

- build
- unit tests
- integration tests
- lint
- typecheck
- smoke test

The exact commands are defined by the project tooling.

---

## Smoke Test

At minimum, one complete flow must be verified.

The smoke test should confirm that:

1. A user request is received
2. Orchestrator analyzes the request
3. Orchestrator creates or selects a plan
4. Orchestrator routes work to one or more agents
5. Agents use tools through the proper boundary
6. Tool results return to the agents or Orchestrator
7. Orchestrator aggregates the result
8. Final response is generated
9. Important state, decision, or audit information is recorded when required

The smoke test should validate the new system shape, not the old implementation.

---

## What Must Not Break

The following must not be broken unless explicitly documented as intentional design changes:

- Public APIs
- Authentication and authorization
- Data persistence
- User-visible critical flows
- Existing valid business rules
- Audit behavior
- Error handling contracts
- Configuration required for runtime operation

---

## What May Change

The following may change during refactoring:

- Internal module structure
- Class names
- Function names
- File organization
- Agent implementation details
- Tool implementation details
- Internal test structure
- Old MVP-specific shortcuts
- Completed phase-specific behavior
- Legacy orchestration assumptions

Internal change is expected.  
External behavior must remain controlled.

---

## Testing Rules for Coding Agent

The coding agent must follow these rules.

1. Do not blindly fix every failing test.
2. Classify failing tests before changing code.
3. Preserve Contract Tests unless a breaking change is intentional.
4. Rewrite internal tests that depend on the old architecture.
5. Add new tests for `DESIGN.md` boundaries.
6. Do not restore old architecture just to satisfy old tests.
7. Do not treat old test structure as the source of truth.
8. Treat `DESIGN.md` as the source of truth for architecture.
9. Treat this `TESTING.md` as the source of truth for test strategy.
10. Ask for human decision when behavior is ambiguous.

---

## Completion Criteria

Testing is considered complete when:

- Contract Tests pass
- Critical Integration Tests pass
- Architecture Boundary Tests reflect `DESIGN.md`
- Legacy Internal Tests are removed, suspended, or rewritten
- Smoke test passes
- Build passes
- Lint passes
- Typecheck passes
- No failing test remains unclassified
- Any intentional behavior change is documented

---

## Final Testing Principle

The purpose of tests during this refactoring is not to protect the old system.

The purpose is to protect:

- critical external behavior
- valid business logic
- new architecture boundaries
- safe refactoring progress

Do not let legacy tests force the system back into the old design.
