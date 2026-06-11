# TASKS.md

## Goal

Incrementally build and stabilize the Business Decision OS agent system — eliminating AGENTS.md
violations, closing architectural gaps, and extending capabilities through well-tested phases.

Full task history for P0–P23 is archived at `docs/archive/v3/TASKS.md`.

---

## Completed Phases (Summary)

| Phase | Tasks | Completed |
|---|---|---|
| P0 — Prohibited Violation | T-001 | 2026-06-02 |
| P1–P3 — Domain Integrity, Access Control, Observability | T-002–T-029 | 2026-06-02 |
| P4 — Job Execution & HITL Flow | T-030–T-039 | 2026-06-02 |
| P5 — Test Infrastructure & Cost Reduction | T-040–T-045 | 2026-06-02 |
| P6 — Chat UI Stability | T-046–T-054 | 2026-06-02 |
| P7 — CI Quality & Memory Loop Validation | T-055–T-058 | 2026-06-02 |
| P8 — Mock Mode for Cost-Free UI Testing | T-059–T-062 | 2026-06-02 |
| P9 — LangGraph Migration | T-063–T-075 | 2026-06-02 |
| P10 — Web UI Server State Standardisation | T-076–T-082 | 2026-06-03 |
| P11 — AskUser: Pre-execution Information Gathering | T-083–T-085 | 2026-06-03 |
| P12 — Test Session Pollution Fix | T-086–T-087 | 2026-06-03 |
| P13 — AskUser: interrupt()-based Mid-Execution Gathering | T-088–T-099 | 2026-06-03 |
| P14 — Agent Node Cards | T-100–T-108 | 2026-06-03 |
| P15 — Text Streaming / text_delta SSE | T-109–T-116 | 2026-06-03 |
| P16 — Backward Compat Removal | T-117–T-119 | 2026-06-03 |
| P17 — Orchestrator Cost Reduction | T-120–T-123 | 2026-06-03 |
| P18 — Tool Scenario Coverage | T-124 | 2026-06-03 |
| P19 — SSE Consumer Consolidation | T-125–T-127 | 2026-06-03 |
| P20 — LangGraph-Native SSE Pipeline Rebuild | T-128–T-134 | 2026-06-03 |
| P21 — Chat Bubble Component Refactor | T-135–T-138 | 2026-06-03 |
| P22 — Test Coverage Gaps | T-139–T-140 | 2026-06-03 |
| P23 — Test Suite Rationalization | T-141–T-146 | 2026-06-03 |
| P24 — Ollama Local LLM Provider | T-147–T-152 | 2026-06-04 |
| P25 — Tool Scenario E2E Validation & Session Cleanup | T-153–T-159 | 2026-06-04 |
| P26 — SSE/Broadcaster Bug Fixes | T-160–T-166 | 2026-06-04 |
| P27 — Model Name in Execution Trace Nodes | T-167–T-171 | 2026-06-04 |
| P28 — Real-time Execution Trace & Persistence Recovery | T-172–T-178 | 2026-06-04 |
| P29–P31 — Goal-Based Agent, Forecasting & Demand Analysis | T-179–T-209 | 2026-06-04 |
| P32 — Supply Planning Agent | T-210–T-223 | 2026-06-04 |
| P33 — Finance Impact Agent | T-224–T-234 | 2026-06-04 |
| P34 — Inventory Agent Enhancement | T-235–T-243 | 2026-06-04 |
| P35 — S&OP Agent & Orchestration | T-244–T-251 | 2026-06-04 |
| P36 — Tool Scenario Prompts for S&OP Agents | T-252–T-257 | 2026-06-04 |
| P37 — Playwright E2E: Remove Mocks, Consolidate | T-258–T-265 | 2026-06-05 |
| P38 — Architecture Realignment | T-266–T-271 | 2026-06-06 |
| P44 — Playwright Tests: Revert to Mock SSE | T-311–T-317 | 2026-06-06 |
| P39 — Supply Chain Control Agent (MVP Core) | T-273–T-280 | 2026-06-06 |
| P45 — Control-Agent-Only Routing | T-318–T-324 | 2026-06-06 |
| P40 — Skill Registry | T-281–T-289 | 2026-06-06 |
| P41 — Memory Layer | T-290–T-298 | 2026-06-06 |
| P42 — Context Engineering Integration | T-299–T-304 | 2026-06-06 |
| P43 — MVP Validation (3 Questions) | T-305–T-310 | 2026-06-06 |
| P46 — Skill & Tool Enrichment | T-325–T-330 | 2026-06-06 |
| P47 — Long-Term Memory Physical Implementation | T-331–T-335 | 2026-06-06 |
| P48 — LongTermMemory Integration + Test Accuracy Fix | T-336–T-339 | 2026-06-06 |
| P50 — LLM Response Normalization Layer | T-343–T-347 | 2026-06-07 |
| P51 — Qwen3 Thinking Disable for Structured Output Calls | T-348–T-352 | 2026-06-07 |
| P56 — nl_query クリーンアップ後処理 | T-363–T-369 | 2026-06-07 |
| P57 — nl_query 品質強化 | T-370–T-375 | 2026-06-07 |
| P59 — Control Agent Degenerate Response Guard | T-383–T-387 | 2026-06-07 |
| P60 — Control Agent Tool-Loop Guard | T-388–T-394 | 2026-06-07 |
| P61 — Quality Hardening: Degenerate Guard / Rule-Based Verifier | T-395–T-400 | 2026-06-07 |
| P62 — ControlAgent Groundedness Verifier Rule 1b | T-401–T-406 | 2026-06-07 |
| P63 — ControlAgent Intent-to-Tool Subset Alignment | T-407 (B-01 only) | 2026-06-07 |
| P64 — Agent Architecture Gap Closure (5 Gaps) | T-407–T-420 | 2026-06-10 |
| P65 — Dead Agent Class Removal | T-421–T-426 | 2026-06-10 |
| P66 — Orchestration Routing Simplification | T-427–T-432 | 2026-06-10 |
| P67 — Tool Layer Rationalization | T-433–T-437 | 2026-06-10 |
| P68 — Frontend Dead Code Cleanup | T-438–T-441 | 2026-06-10 |
| P69 — Dependency & Config Hygiene | T-442–T-445 | 2026-06-10 |
| P70 — Test Suite & Documentation Consolidation | T-446–T-450 | 2026-06-10 |
| P71 — Goal Evaluation Loop | T-451–T-457 | 2026-06-10 |
| P72 — Grounded Runtime Evaluator | T-458–T-462 | 2026-06-10 |
| P73 — Feedback Learning Loop | T-463–T-469 | 2026-06-10 |
| P74 — Integration Tier Latent Debt | T-470 | 2026-06-10 |
| P75 — Tool Layer Full Audit | T-471–T-476 | 2026-06-10 |
| P76 — Tool Layer Conformance Remediation | T-477–T-487 | 2026-06-10 |
| P77 — Runtime Error Surfacing Fixes | T-488–T-491 | 2026-06-10 |
| P78 — Deterministic Routing Completion | T-492–T-494 | 2026-06-10 |
| P79 — Session Resume & Lifecycle Robustness | T-495–T-500 | 2026-06-10 |
| P80 — Verifier Blocked-Path UX | T-501–T-505 | 2026-06-10 |
| P81 — Tool Scenario Modal Content Refresh | T-506–T-518 | 2026-06-10 |
| P82 — Seed Data Staleness & list_stockout_risk missing_data Fix | T-519–T-522 | 2026-06-10 |
| P83 — LLM Usage Recording Restoration | T-523–T-527 | 2026-06-10 |
| P84 — Demo Data Risk Distribution Fix | T-528–T-530 | — |

> **Design Realignment Note (2026-06-05):** P29–P36 built Specialist Domain Agents (DemandAgent,
> InventoryAgent, SupplyPlanningAgent, FinanceImpactAgent, SopAgent) as independent runtime units.
> The DESIGN.md refresh (ADR: `docs/adr/2026-06-05-integrated-control-agent-first.md`) specifies
> that in MVP, Specialist Agents exist as **Skill files only (Level 2)** — not runtime units.
> The **domain tools** created in P31–P34 (calculation, analysis, gap tools) remain valid and will
> be accessed by the Supply Chain Control Agent via the Tool Gateway. The agent runtime classes
> will be retired in P38.

---

> Phase detail sections for P24–P64 are archived at `docs/archive/v4/TASKS.md` (P70 T-449).

---

# Full Refactoring Programme (P65–P70)

**Scope decision (2026-06-10):** production infra code (`infra/terraform/`, `infra/databricks/`,
`packages/lakehouse/`, `AcaJobsRunner`, Celery worker, `celery`/`redis` dependencies) is
**explicitly preserved** per user decision — it is out of scope for all phases below.
Targets are application-code waste only: dead agent classes, unreachable orchestration paths,
registry/allowlist drift, unused frontend modules, config hygiene, and doc bloat.

**Evidence base (survey 2026-06-10):** `VALID_AGENT_ROLES == {"control"}` and
`CROSS_DOMAIN_AGENT_CLASSES == {}` since P38/P45 — `_make_agent()` can only ever instantiate
`ControlAgent`, yet 15 legacy agent class files and the multi-agent execution machinery
(`sequential_agents` / `planned_execution` / DAG, `decision.py` `simulation_optimizer` gating)
remain in the tree.

**Phase ordering:** P65 → P66 → P67 (sequential — each removes the context the next audits).
P68 and P69 are independent and parallel-eligible after P65. P70 runs last.

---

## P65 — Dead Agent Class Removal — Done (2026-06-10)

**Goal:** Delete all agent classes unreachable from any runtime path, and the dead branches
that reference them. Lowest-risk, highest-volume deletion; establishes a clean base for P66.

Dependencies: P64 Done

### Batch B-01 — Delete dead agent class files (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-421 | Delete `packages/agent/deprecated/` entirely (demand, inventory, supply_planning, finance_impact, sop + `__init__.py`). P38 kept them "until they create problems"; they now carry stale `sql_query` references (tool deleted in P55) and are imported only by a unit test of deprecated code. | Done |
| T-422 | Delete `packages/agent/cross_domain/` entirely (AnomalyDetectorAgent, DataEngineerAgent, EvaluatorAgent, SimulationOptimizerAgent). `CROSS_DOMAIN_AGENT_CLASSES == {}` means none are instantiable at runtime; only `tests/unit/test_output_builders.py` imports the module. | Done |
| T-423 | Delete unused `packages/agent/domain/` agent files: `exception.py`, `logistics.py`, `procurement.py`, `production.py`, `replenishment.py`, `supplier.py` — classes defined but never imported anywhere. Afterward audit `AgentBasedSpecialist` in `packages/agent/base.py`; if `ControlAgent` is its sole remaining subclass, keep the base class but remove any branches that exist only for deleted subclasses. | Done |
| T-424 | Remove the now-dead `CROSS_DOMAIN_AGENT_CLASSES` branch in `packages/agent/orchestrator/runtime.py::_make_agent`; simplify `packages/agent/orchestrator/roles.py` accordingly (keep `VALID_AGENT_ROLES` as the public lookup). | Done |

#### Defect: D-001

- Status: Resolved (2026-06-10 — fixed in P65-B-01 commit; Test/Review confirmed `make typecheck` exit 0)
- Severity: Medium
- Repro: `make typecheck`
- Observed: 4 mypy errors pre-dating P65 — `packages/tools/base.py:50` (no-any-return), `packages/tools/base.py:52`, `packages/agent/runtime.py:698`, `packages/agent/runtime.py:809` (unused-ignore). Discovered during P65 B-01 batch check; verified pre-existing via stash/restore.
- Expected: `make typecheck` exits 0 (P64 T-420 sign-off claimed all gates pass).
- Area: packages/tools, packages/agent
- Owner: App Builder
- Acceptance: `make typecheck` exits 0.

Dependencies: none

### Batch B-02 — Remove tests of deleted code + quality gate (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-425 | Delete `tests/unit/agent/test_sop_agent.py` and `tests/unit/test_output_builders.py`; audit `tests/unit/test_sop_roles.py` and any other test importing removed modules — delete or trim to surviving behavior only. | Done |
| T-426 | `make test-unit && make lint && make typecheck` — all pass. | Done |

#### Defect: D-002

- Status: Resolved (2026-06-10 — integration fixtures now inject a structured-output stub ModelRegistry; `make test-integration` 16 passed / 0 failed)
- Severity: High
- Repro: `docker compose -f infra/compose/compose.yaml up -d db && make test-integration`
- Observed: 11 integration tests fail (`test_ask_user_hitl_variants.py`, `test_prompts_mock_llm.py`, `test_session_persistence.py`) with `AttributeError: 'NoneType' object has no attribute 'get'` on `self._model_registry` in `session_orchestrator.py`. Verified pre-existing at P64 HEAD (29127ae) — identical failures. Inherited debt from the P52–P53 ModelRegistry migration; integration gate was not run at those sign-offs.
- Expected: `make test-integration` exits 0 (5 passed, 47 skipped baseline preserved).
- Area: tests/integration (fixtures) and/or packages/agent/orchestrator/session_orchestrator.py
- Owner: App Builder (diagnose: if orchestrator requires model_registry by design, fix test fixtures via Test/Review handoff; if None should be tolerated, add the guard in session_orchestrator)
- Acceptance: `make test-integration` exits 0 with no newly skipped tests.

Dependencies: B-01

---

## P66 — Orchestration Routing Simplification — Done (2026-06-10)

**Goal:** With ControlAgent as the only runtime agent, the multi-agent execution modes are
degenerate: `sequential_agents` and `planned_execution` can only ever produce a 1-element
control-agent sequence, and `decision.py` gates on `simulation_optimizer` results that can
never exist (`packages/agent/orchestrator/decision.py:97,241`). Collapse routing to the paths
that actually execute, without changing intent categories (they drive `_INTENT_TOOL_SUBSET`)
or the SSE event contract.

Dependencies: P65 Done

### Batch B-01 — ADR: routing collapse (Orchestrator) — Done

| Task | Description | Status |
|---|---|---|
| T-427 | ADR `docs/adr/2026-06-10-orchestrator-routing-collapse.md` — document removal of `sequential_agents`/`planned_execution`/DAG execution modes and `simulation_optimizer`-dependent decision logic; state that the 6 intent categories and SSE `graph_node` event shape are preserved. | Done |

Dependencies: none

### Batch B-02 — Remove unreachable orchestration branches (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-428 | `packages/agent/orchestrator/decision.py` — remove `simulation_optimizer`-gated candidate logic and any code reachable only from it; fold `weights.py` usage: if `resolve_weights` becomes dead, delete `weights.py`; if `decision_support` ranking survives via ControlAgent output, keep the minimal live path. | Done |
| T-429 | Collapse `_INTENT_MODE_MAP` in `routing.py` so every non-chat intent routes through the single-ControlAgent path; remove `run_dag_execution` and sequential multi-agent loops from `planning.py` and the corresponding `_node_run_planned`/`_node_run_dag` nodes in `session_orchestrator.py` (keep `_node_run_sequential` only if it is the surviving single-agent executor). SSE event shape must not change. | Done |
| T-430 | Update `packages/agent/orchestrator/prompts.py` intent-classification text and `validate_route` in `routing.py` to match the surviving modes. Keep all 6 intent categories. | Done |

Dependencies: B-01

### Batch B-03 — Test updates + quality gate (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-431 | Update or delete tests bound to removed paths: `test_dag_parallel_execution.py`, `test_decision_rank_candidates.py`, `test_routing.py`, `test_tool_isolation.py` (imports `orchestrator.weights`), `test_session_orchestrator_*` cases covering planned/DAG nodes. Also update `test_agent_reclassification.py` (3 cases expecting `run_planned`/`run_dag` nodes) and `test_tool_layer_integration.py` (2 cases using `planned_execution`/`dag_execution` modes) — both discovered in B-02. | Done |
| T-432 | `make test-unit && make lint && make typecheck && make test-playwright` — Playwright confirms the execution-trace UI is unaffected. | Done |

Dependencies: B-02

#### Defect: D-005

- Discovered: 2026-06-10, post-sign-off, live user session (API log 22:15 UTC, session b45d034c)
- Symptom: lookup-intent query fails with `ValueError: single_agent route requires exactly one agent` → user sees "Processing failed. Please try again."
- Location: `packages/agent/orchestrator/session_orchestrator.py` `select_execution_mode` — non-supply_chain intents still ask the orchestrator LLM to generate `AgentRoute`; gemma4:12b returned `agents` ≠ exactly 1 and `validate_route` raised. P66's routing collapse added a deterministic shortcut for `supply_chain` only, leaving an LLM call with zero decision content (`VALID_AGENT_ROLES == {"control"}`, `_INTENT_MODE_MAP` is total) as a per-request failure source.
- Status: Resolved (T-492 deterministic routing + T-493 tests; gates passed 2026-06-10)

---

## P67 — Tool Layer Rationalization — Done (2026-06-10)

**Goal:** ~40 tool modules exist; P64 made the control allowlist derived from
`_INTENT_TOOL_SUBSET`, but the registry may still register tools no intent can reach
(candidate: `EvaluatorTool`). Make `create_tool_registry()` ↔ allowlists ↔ `docs/TOOLS.md`
mutually consistent and delete what nothing can call.

Dependencies: P66 Done

### Batch B-01 — Reachability audit + dead tool removal (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-433 | Reachability audit: for every tool registered in `create_tool_registry()`, verify it appears in at least one `_ROLE_TOOL_ALLOWLIST` entry / `_INTENT_TOOL_SUBSET` list; produce the unreachable list in the batch report. | Done |
| T-434 | Delete unreachable tool modules and their registry entries. Keep classes used by non-LLM paths (`AuditLogTool` post-completion hook, `JobDispatchTool`, `TrainForecastTool` — per P64 B-02). | Done |
| T-435 | Update `docs/TOOLS.md` to exactly match the post-cleanup registry and allowlists. | Done |

Dependencies: none

### Batch B-02 — Orphaned tool tests + quality gate (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-436 | Delete unit tests for removed tools (`tests/unit/tools/`); confirm no cassette files in `tests/cassettes/` reference removed tools. | Done |
| T-437 | `make test-unit && make lint && make typecheck` — all pass. | Done |

Dependencies: B-01

---

## P68 — Frontend Dead Code Cleanup — Done

**Goal:** Remove unused frontend modules and exports accumulated across the P6–P44 UI
iterations. Parallel-eligible with P66/P67 (no shared files).

Dependencies: P65 Done (parallel-eligible with P66, P67)

### Batch B-01 — Unused module deletion (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-438 | Delete `apps/web/data/mockInventoryShortageAnalysis.ts` — zero imports (only appears in `tsconfig.tsbuildinfo` cache). | Done |
| T-439 | Run an unused-export audit (`npx knip` or `ts-prune`) across `apps/web/`; manually verify and delete confirmed-unused components, hooks, feature modules, schemas, and types (audit candidates: `schemas/evaluations.ts`, `types/workspace.ts`, unused `features/*` hooks). Dynamic-import and Next.js convention files (`page.tsx`, `layout.tsx`) are exempt from deletion on tool output alone. | Done |
| T-440 | Dedupe overlapping execution-trace components if the audit confirms overlap (`components/ExecutionProgressPanel.tsx` vs `components/agent/ExecutionPanel.tsx`, `AgentNodeCard.tsx`); keep the variant the chat page renders. | Done |

Dependencies: none

### Batch B-02 — Quality gate (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-441 | Vitest suite (via Makefile target), `make test-playwright`, and `make build` — all pass. | Done |

Dependencies: B-01

---

## P69 — Dependency & Config Hygiene — Done

**Goal:** Align declared dependencies and config files with what the code actually uses.
Infra services themselves (Celery, Redis, compose definitions) are preserved per the
2026-06-10 scope decision.

Dependencies: P65 Done (parallel-eligible with P66–P68)

### Batch B-01 — pyproject / .env.example / Makefile audit (Infra) — Done

| Task | Description | Status |
|---|---|---|
| T-442 | `pyproject.toml`: move `pytest` and `pytest-asyncio` from `[project] dependencies` to `[tool.uv] dev-dependencies`; audit remaining runtime deps against actual imports (`celery`/`redis` stay — preserved infra). | Done |
| T-443 | `.env.example`: verify every variable against an actual `os.environ` read in the codebase; delete entries nothing reads; fix stale comments. | Done |
| T-444 | `Makefile`: remove targets referencing deleted paths; verify every target still runs after P65–P68 deletions. | Done |

Dependencies: none

<!--
## Infra Handoff — P69 B-01
Changed files: pyproject.toml, .env.example, Makefile, uv.lock, docs/TASKS.md
Smoke checks: SKIPPED (stack not running — pure file-edit task; no service changes)
New env vars: none
Quality gates:
  uv sync          exit 0  ("Resolved 181 packages in 2ms; Audited 49 packages in 0.12ms")
  make test-unit   exit 0  (770 passed, 11 skipped, 61 warnings in 7.22s)
  make lint        exit 0  ("All checks passed!")
  make typecheck   exit 0  ("Success: no issues found in 159 source files")
-->

### Batch B-02 — Quality gate (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-445 | `uv sync` succeeds from a clean lock state; `make test-unit && make lint && make typecheck` — all pass. | Done |

Dependencies: B-01

---

## P70 — Test Suite & Documentation Consolidation — Done (2026-06-10)

**Goal:** Final pass once all deletions land: remove redundant test coverage, then bring the
documentation set back in sync with the slimmed codebase.

Dependencies: P66 Done, P67 Done, P68 Done, P69 Done

### Batch B-01 — Test suite rationalization (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-446 | Remove any leftover `@pytest.mark.asyncio` decorators (`asyncio_mode = "auto"` is global — `.claude/rules/testing.md`). | Done |
| T-447 | Duplicate-coverage audit across `tests/unit/` (84 files; the control-agent and agent-runtime clusters are the largest). Merge or delete tests whose assertions are fully covered elsewhere; no unique assertion may be lost. | Done |
| T-448 | `make test-unit && make lint && make typecheck` — all pass; record test count before/after in the batch report. | Done |

Dependencies: none

### Batch B-02 — TASKS.md archive (Orchestrator) — Done

| Task | Description | Status |
|---|---|---|
| T-449 | Move P24–P64 phase detail sections from `docs/TASKS.md` to `docs/archive/v4/TASKS.md`, keeping only the Completed Phases summary table (~1,650 → ~200 lines). | Done |

Dependencies: none

### Batch B-03 — Doc reference sweep (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-450 | Sweep `docs/DESIGN.md`, `docs/AGENT_ARCHITECTURE.md`, `docs/TOOLS.md`, `docs/ORCHESTRATOR.md` for references to modules removed in P65–P68 (deprecated/cross-domain agents, `sql_query`, removed routing modes, deleted tools/components) and update them to the post-refactoring state. | Done |

Dependencies: P65–P68 Done


---

# Autonomy Loops Programme (P71–P73)

**Goal:** Close the three core autonomy gaps identified 2026-06-10 (see ADR
`docs/adr/2026-06-10-autonomy-loops.md`, normative for all three phases): no goal loop,
no grounded verification, no feedback learning loop. Deferred deliberately: persistent
cross-turn agenda, prediction-vs-actuals learning (future ADRs).

**Ordering:** P71-B-01 (ADR) first; then P71-B-02 (session_orchestrator/models) and
P72-B-01 (runtime.py) are parallel-eligible (disjoint files); P73 migration can run in
parallel; test batches follow their implementation batches.

---

## P71 — Goal Evaluation Loop — Done (2026-06-10)

**Goal:** Make the goal first-class and close the outer loop: derive GoalSpec, evaluate the
answer against it, allow exactly one refinement pass with optional intent re-route.

Dependencies: P70 Done

### Batch B-01 — ADR (Orchestrator) — Done

| Task | Description | Status |
|---|---|---|
| T-451 | ADR `docs/adr/2026-06-10-autonomy-loops.md` — goal loop, grounded verification, feedback learning; invariants (SSE schema, protocols, additive-only changes); bounded LLM budget. | Done |

Dependencies: none

### Batch B-02 — GoalSpec + evaluate_goal node + refinement loop (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-452 | `packages/agent/orchestrator/models.py` — add `GoalSpec {goal_text: str, success_criteria: list[str] (≤3)}` and `GoalEvaluation {satisfied: bool, missing: str|None, reroute_category: str|None}` Pydantic models; add additive-optional `goal_evaluation: dict | None = None` to `SessionResponse`. `OrchestratorState` gains `goal`, `goal_eval`, `refine_count` keys. | Done |
| T-453 | `session_orchestrator.py` — new node `set_goal` (after classify_intent, non-chat only: one structured-output call, orchestrator role, fail-open to `GoalSpec(goal_text=query, success_criteria=[])`); new node `evaluate_goal` (after run_sequential: structured GoalEvaluation verdict; fail-open to satisfied=True); conditional edge: satisfied or refine_count≥1 → END, else refine path → re-enter run_sequential with `missing` appended to instruction and intent updated when `reroute_category` is a valid different category. direct_chat bypasses entirely. | Done |
| T-454 | SSE: `set_goal`/`evaluate_goal` emit standard `graph_node` events (kind="orchestrator", meta includes satisfied/missing for evaluate_goal); populate `SessionResponse.goal_evaluation`. Event schema unchanged. | Done |

Dependencies: B-01

### Batch B-03 — Tests + gate (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-455 | Unit tests: satisfied verdict → single run; unsatisfied → exactly one refinement then END (cap enforced); chat intent bypasses set_goal/evaluate_goal; fail-open on verdict parse failure. | Done |
| T-456 | Unit test: reroute_category updates intent and tool subset on the refinement pass; invalid category ignored. | Done |
| T-457 | `make test-unit && make lint && make typecheck` — all pass (proof-of-execution). | Done |

#### Defect: D-003

- Status: Resolved (2026-06-10 — integration conftest stub made type-aware mirroring unit helpers; 8 target tests pass; canonical gate 16 passed/0 failed; full-DSN run 47 passed)
- Severity: High
- Repro: `docker compose -f infra/compose/compose.yaml up -d db && DATABASE_URL=<dev> make test-integration`
- Observed: 8 integration tests fail (`test_ask_user_hitl_variants.py` ×6, `test_prompts_mock_llm.py` ×2) with `AttributeError: 'AgentRoute' object has no attribute 'needs_input'`. Root cause: P71's `set_goal` node consumes one structured-output response before `prepare_ask_user`; the integration conftest stub (`_StructuredOutputFakeModel`) is positional, so the response sequence shifted off-by-one. Unit helpers were made type-aware in P71-B-03 but the integration conftest equivalent was not updated. Discovered at P73-B-03 programme sign-off — after P71 batch sign-off was given.
- Expected: `make test-integration` 0 failed against the programme baseline (16 passed pre-P71, 19+ after T-468).
- Area: tests/integration/conftest.py (and per-test sequences)
- Owner: Test/Review
- Acceptance: `make test-integration` (with dev DATABASE_URL) exits 0 with 0 failed and ≥27 passed.

Dependencies: B-02

---

## P72 — Grounded Runtime Evaluator — Done (2026-06-10)

**Goal:** Reconnect the dead `add_revision_message → call_model_final` self-correction path
behind a real LLM groundedness verdict, keeping rule-based checks as pre-filter.

Dependencies: P71 B-01 (ADR); parallel-eligible with P71 B-02 (disjoint files)

### Batch B-01 — Groundedness verdict + revision rewire (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-458 | `packages/agent/runtime.py` — add `GroundednessVerdict {grounded: bool, unsupported_claims: list[str]}`; in `_verify_findings_node`, after rule-based pre-filter passes, run one structured-output groundedness call (control role via model_registry) gated by: intent ∈ {domain_analysis, cross_domain_analysis, decision_support, supply_chain} AND tool_results non-empty AND model_registry present; fail-open to rule-based result on any verifier error. | Done |
| T-459 | Wire `needs_revision`: `_after_verify` returns "add_revision_message" when verdict is ungrounded; revision message embeds the specific `unsupported_claims`; existing one-retry `call_model_final` path preserved (no second verify). | Done |
| T-460 | Verdict surfaced in run output meta (e.g., `verification: {grounded, revised}`) for observability; no SSE schema change. | Done |

Dependencies: P71 B-01

### Batch B-02 — Tests + gate (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-461 | Unit tests: grounded verdict → END no revision; ungrounded → exactly one revision retry with claims in message; verifier exception → falls back to rule-based; gating (chat/lookup intents and empty tool_results skip the LLM verdict). | Done |
| T-462 | `make test-unit && make lint && make typecheck` — all pass (proof-of-execution). | Done |

Dependencies: B-01

---

## P73 — Feedback Learning Loop — Done (2026-06-10)

**Goal:** Close decide → observe(feedback) → recall: user feedback lands on the decision
record and changes how past decisions are injected into future context.

Dependencies: P71 B-01 (ADR)

### Batch B-01 — Migration (Infra) — Done

| Task | Description | Status |
|---|---|---|
| T-463 | Alembic migration `0018_decision_log_outcome.py` — add `outcome SMALLINT NULL` to `decision_log` (additive; +1/−1/NULL). | Done |

Dependencies: none

### Batch B-02 — Outcome write path + context annotation (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-464 | `packages/memory/decision.py` — add `set_latest_outcome(session_id: str, outcome: int) -> bool` (updates latest `record_type='decision'` row of the session); `search()` includes `outcome` in returned rows. | Done |
| T-465 | `apps/api/routers/sessions.py` feedback endpoint — after successful `set_message_feedback`, best-effort call `DecisionMemoryStore.set_latest_outcome` (try/except log-warning; never fails the request). | Done |
| T-466 | `packages/agent/control/control_agent.py` — Past Decisions block annotates entries with `[user feedback: positive|negative]` when outcome present; `_SYSTEM_PROMPT` gains one instruction to avoid approaches that previously received negative feedback. | Done |

Dependencies: B-01

### Batch B-03 — Tests + gate + programme sign-off (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-467 | Unit tests: `set_latest_outcome` SQL path (mock pool); endpoint non-fatal on store failure; Past Decisions annotation rendering; prompt instruction present. | Done |
| T-468 | Integration test (real DB): write decision record → PATCH feedback → decision_log.outcome updated → search returns outcome. | Done |
| T-469 | Programme sign-off: `make test-unit && make lint && make typecheck && make test-integration && make build && make test-playwright` — all pass (proof-of-execution). | Done |

Dependencies: B-02, P71 Done, P72 Done


---

## P74 — Integration Tier Latent Debt — Done (2026-06-10)

**Goal:** When `DATABASE_URL` is fully exported, 14 integration tests fail that the canonical
`make test-integration` gate never executes (they are skipped without the env var). All 14
pre-date P71 (verified during D-003 resolution). Causes reported: asyncpg DSN format issue,
`model_registry=None` constructions in non-registry tests, scenario coverage failures.

### Batch B-01 — Diagnose + fix latent integration failures (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-470 | Reproduce with dev `DATABASE_URL` exported (`14 failed, 47 passed, 4 skipped` at 2026-06-10 HEAD); classify each failure (env/DSN vs stale fixture vs genuine bug); fix test-side issues; escalate any production bug as a Defect Task. Acceptance: full-DSN `make test-integration` 0 failed. | Done |

Dependencies: none

---

## P75 — Tool Layer Full Audit — Done (2026-06-10)

**Goal:** Audit all 35 tool files in `packages/tools/` (32 registered + `write_audit_log`,
`job_dispatch`, `train_forecast` unregistered) on four axes: (1) input→output contract
conformance (`Tool` base class + Context Pack return: `summary`/`schema`/`key_metrics`/
`missing_data`/`artifact_id`); (2) implementation quality (parameterized SQL, no hardcoded
schema strings, `RuntimeError` on missing config, typed exception propagation); (3) role
overlap — overlap means duplicated responsibility, NOT "currently unused"; tools with
plausible future use are kept; (4) test coverage and proof of green execution.
Audit is read-only; any production defect found is registered as a D-NNN Defect Task,
not fixed ad-hoc.

### Batch B-01 — Static conformance + implementation quality audit (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-471 | For each of the 35 tool files: verify `Tool` base-class conformance — declared `name`, input args schema, `run()` accepts structured input and returns a Context Pack (`summary`, `schema`, `key_metrics`, `missing_data`, `artifact_id`); flag any tool returning raw rows, ad-hoc dicts, or having side-effect-only behavior (no meaningful output). Deliver a 35-row conformance matrix. | Done |
| T-472 | Same sweep for implementation quality: parameterized SQL via `execute_read_query`/repository layer only; no hardcoded table/column literals (must use `get_schema_context()`); `RuntimeError` on missing config; no silently swallowed exceptions; LLM-invoking tools go through the model layer (no direct SDK calls). Flag violations per file. | Done |

Dependencies: none

### Batch B-02 — Role overlap analysis (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-473 | Pairwise responsibility analysis within each domain group, with verdict keep / merge-candidate / boundary-unclear per pair. Mandatory pairs: `get_open_supply_orders` vs `get_delayed_supply_orders`; `calculate_days_of_supply` vs `calculate_days_of_inventory`; `analyze_supply_risk` vs `calculate_stockout_risk` vs `calculate_supply_gap`; `calculate_stockout_risk` vs `list_stockout_risk`; `compare_cost_scenarios` vs the 3 individual cost tools; `analyze_demand_trend` vs `compare_demand_periods`; `profile_demand_data` vs `data_quality_checker`; `data_catalog_search` vs `table_schema_reader`; `forecast` vs `train_forecast`; `nl_query` vs every thin SQL-wrapper tool (generic-vs-specialized justification per DESIGN.md §Tool Design Philosophy). Unused-but-future-valuable tools are explicitly kept (per 2026-06-10 decision: production infra preserved). | Done |

Dependencies: none

### Batch B-03 — Test coverage map + execution verification (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-474 | Map each of the 35 tools to its unit and integration test files (grep `tests/unit` + `tests/integration`); deliver coverage matrix marking tools with no unit test, no integration test, or assertion-free tests. | Done |
| T-475 | Proof-of-execution: `make test-unit` and full-DSN `make test-integration` — capture command, exit code, pass/fail counts; confirm every tool-related test green. Any failure → register Defect Task. | Done |

Dependencies: none

### Batch B-04 — Consolidated audit report + decision log (Orchestrator) — Done

| Task | Description | Status |
|---|---|---|
| T-476 | Consolidate B-01/B-02/B-03 findings into the final audit report (conversation deliverable); append accepted keep/merge decisions to `docs/DECISIONS.md`; register follow-up phase or Defect Tasks for any non-conformance requiring code change. | Done |

Dependencies: B-01, B-02, B-03

---

## P76 — Tool Layer Conformance Remediation — Done (2026-06-10)

**Goal:** Fix the non-conformances found by the P75 audit, under the **hybrid** output-contract
resolution chosen by the user (2026-06-10): the domain-dict return contract is codified as
official (DESIGN.md amended); full Context Pack is NOT implemented; the two real holes —
`missing_data` absence and unbounded row returns — are closed surgically. DOS→DOI merge
approved (DOI is the warehouse-aware superset; DOS-unique `stockout_date_estimate` is ported).

### Batch B-01 — ADR: hybrid tool output contract + DOS/DOI merge (Orchestrator) — Done

| Task | Description | Status |
|---|---|---|
| T-477 | Author `docs/adr/2026-06-10-tool-output-contract-hybrid.md`: (1) official contract = domain-specific dict conforming to declared `output_schema`; (2) DB tools MUST populate `missing_data: list[str]` when required source data is absent; (3) row-array tools MUST cap rows and set `truncated` (existing caps retained; new `LIMIT 100` for supply-order tools); (4) shared helpers module for `_classify_stockout_risk` / `_db_error_message`; (5) DOS→DOI merge decision; (6) escalation criteria to full Context Pack (multi-agent runtime, artifact store, report tools). Append DECISIONS.md entry. | Done |

Dependencies: none

### Batch B-02 — Contract fixes (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-478 | `evaluator_tool.py`: raise `RuntimeError` when `risk_thresholds.yaml` is missing instead of silently falling back to hardcoded 0.85/0.95 defaults. | Done |
| T-479 | `supply_open_orders_tool.py` / `supply_delayed_orders_tool.py`: add `LIMIT 100` + `truncated` output flag. | Done |
| T-480 | Create `packages/tools/_shared.py` (name per App Builder judgment): extract `classify_stockout_risk` (2 copies) and `db_error_message` (~16 copies); update all importing tools. | Done |
| T-481 | `data_catalog_search_tool.py`: surface DB failure via explicit `error` key instead of silently returning `row_count: None` rows. | Done |
| T-484 | Add `missing_data: list[str]` population to the 28 DB-accessing tools per ADR: when a required source (master row, history rows, cost record) is unavailable, append a human-readable entry; field present and empty otherwise. Update each tool's `output_schema`. | Done |

Dependencies: B-01. Note: tests are updated by Test/Review in B-04; batch check = `make lint && make typecheck` + no NEW unit failures beyond those enumerated for B-04.

### Batch B-03 — DOS→DOI merge + doc amendments (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-483 | Merge `calculate_days_of_supply` into `calculate_days_of_inventory`: add `stockout_date_estimate` output to DOI; delete `supply_days_tool.py`; remove registry entry; replace DOS with DOI in `_INTENT_TOOL_SUBSET` (`supply_chain`; dedupe in `domain_analysis`/`cross_domain_analysis`/`decision_support`) and in the ControlAgent system prompt. | Done |
| T-485 | Amend `docs/DESIGN.md` §Tool Design Constraints to the hybrid contract per ADR (remove Context Pack 5-field mandate; add missing_data + row-cap rules); update `docs/AGENT_ARCHITECTURE.md` (tool count 35→from-registry, Tier 2 DOS reference, "35 registered tools" figure → actual). | Done |

Dependencies: B-01 (parallel-eligible with B-02; runs after B-02 in practice)

### Batch B-04 — Tests + phase sign-off (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-482 | Add behavioral unit test for `train_forecast` `handle()` (only tool with indirect-only coverage in P75). | Done |
| T-486 | Update/add unit tests for B-02/B-03: evaluator RuntimeError path; LIMIT+truncated; shared helpers; data_catalog_search error key; missing_data population (representative tools); DOS removal (subset test, registry test); DOI `stockout_date_estimate`. | Done |
| T-487 | Phase sign-off: `make test-unit && make lint && make typecheck && make test-integration` (full DSN) `&& make build && make test-playwright` — proof-of-execution. | Done |

Dependencies: B-02, B-03

#### Defect: D-004

- Discovered: 2026-06-10, post-sign-off, during user runtime session (API logs 21:45 UTC)
- Symptom: `POST /api/v1/approvals` returns 500 — `TypeError: Object of type UUID is not JSON serializable`
- Location: `apps/api/routers/approvals.py` `create_approval` — `JSONResponse(status_code=201, content=created)` serializes the raw repo row (UUID/datetime objects) with stdlib `json.dumps`. Same risk at `post_decision`'s `JSONResponse(content=updated)`.
- Note: the repeated 500s coincide with the `job_approval` Playwright spec marked "pre-existing flaky" at P76 sign-off — the flakiness likely masks this real bug, not SSE timing. Pre-dates P76 (no P76 change touched approvals).
- Status: Resolved (T-488 fix + T-490 regression tests; gates passed 2026-06-10)

---

## P77 — Runtime Error Surfacing Fixes — Done

**Goal:** Resolve D-004 (approvals 500 on UUID serialization) and fix the misleading
frontend error message that displays "Error contacting the API. Please check the backend
is running." for ALL failures — including HTTP business errors like 404 "Session not
found" — which misled runtime diagnosis on 2026-06-10 (stale browser session after dev
stack reset surfaced as an apparent connectivity failure).

### Batch B-01 — API + web fixes (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-488 | `apps/api/routers/approvals.py` (D-004): `create_approval` and `post_decision` return raw repo rows via `JSONResponse(content=...)` — UUID/datetime objects crash stdlib `json.dumps` with 500. Serialize with `fastapi.encoders.jsonable_encoder` (or equivalent) on both paths. | Done |
| T-489 | `apps/web/lib/api.ts` `postMessage`/`postAskUserAnswer`: on `!res.ok`, parse the response body's `detail` and throw a typed error carrying status + detail. `apps/web/app/chat/ChatStateContext.tsx` (lines ~623, ~855): show the server `detail` for HTTP errors (404 → e.g. "Session not found — it may have been deleted. Start a new session."); reserve "Error contacting the API. Please check the backend is running." for network-level fetch failures only. | Done |

Dependencies: none

### Batch B-02 — Tests + gate (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-490 | Unit test: `POST /api/v1/approvals` via ASGITransport with a stubbed repo returning UUID/datetime values → 201 and JSON-serializable body (regression for D-004). Same for the `post_decision` path. | Done |
| T-491 | Gate: `make test-unit && make lint && make typecheck && make build && make test-playwright` — verify the `job_approval` spec passes (was flaky while D-004 was live). Proof-of-execution. Mark D-004 Resolved on pass. | Done |

Dependencies: B-01

---

## P78 — Deterministic Routing Completion — Done (2026-06-10)

**Goal:** Resolve D-005 by completing P66's routing collapse: construct `AgentRoute`
deterministically for ALL intent categories (`_INTENT_MODE_MAP` + `agents=["control"]`
for single_agent modes) and remove the routing LLM call. Saves one LLM round-trip per
non-supply_chain request and eliminates structured-output flakiness as a request-fatal
failure source. No public interface signature changes (`select_execution_mode` retained).

### Batch B-01 — Deterministic route construction (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-492 | `session_orchestrator.py`: `_node_select_mode` builds the route deterministically for every category — mode from `route_after_intent(intent)`; `agents=["control"]` iff mode is `single_agent`, else `[]`; `requires_planning=False`, `requires_dag=False`, static rationale. `select_execution_mode` keeps its signature but delegates to the deterministic builder (no LLM call; keep the `make_step("routing")` trace step). Remove `ROUTER_SYSTEM` from prompts.py and its imports. | Done |

Dependencies: none

### Batch B-02 — Tests + gate (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-493 | Unit tests: every `_INTENT_MODE_MAP` category (+ unknown category fallback) yields a route that passes `validate_route`; routing performs no LLM call (model registry not invoked for the routing step). Update any test stubbing the router LLM. | Done |
| T-494 | Gate: `make test-unit && make lint && make typecheck && make build && make test-playwright` — proof-of-execution. Mark D-005 Resolved on pass. | Done |

Dependencies: B-01

---

## P79 — Session Resume & Lifecycle Robustness — Not Started

**Goal:** Resolve D-006 (ask_user resume crashes with `KeyError: 'session_id'` when no
LangGraph checkpoint exists for the thread) and D-007 (session deletion does not cancel
in-flight background runs → orphaned runs spam `session_events` FK violations; session
endpoints other than `post_message` lack DB recovery after a process restart). Both are
latent defects from archived phases, surfaced during live runtime diagnosis on 2026-06-10
(the same session that uncovered D-004/D-005).

#### Defect: D-006

- Discovered: 2026-06-10, live runtime diagnosis post-P77 (compose-api-1 logs 21:45:49, 21:48:05, 22:07:39 UTC — 3 distinct sessions)
- Symptom: `POST /api/v1/sessions/{id}/answer` returns 202, then the background resume task crashes with `KeyError: 'session_id'`; the user receives SSE error `resume_failed` ("Processing failed. Please try again.")
- Location: `packages/agent/orchestrator/session_orchestrator.py` — `answer_ask_user` issues `Command(resume={"answer": ...})` unconditionally. When the thread has no LangGraph checkpoint (original run died in a uvicorn reload, or the session never ran a graph), LangGraph starts the graph from `START` with empty input state and `_node_classify_intent`'s `UUID(state["session_id"])` raises KeyError. Verified via `checkpoints` table: the failing thread's only 2 checkpoints (step -1 `input`, step 0 `loop`) were created by the resume call itself, with an `__error__` write at `classify_intent`. Same latent risk in `resume()` (approval path).
- Originating phase: P13 (ask_user interrupt flow; T-088–T-099) — predates the checkpoint-existence guard ever being needed because in-process MemorySaver state could not outlive the run
- Repro: `POST /api/v1/sessions` then immediately `POST /api/v1/sessions/{id}/answer` with `{"answer":"x"}` (no prior paused run) → SSE error event, log shows `Resume failed ... KeyError: 'session_id'`
- Severity: Medium
- Observed: unhandled KeyError surfaced as generic `resume_failed`; graph executes from empty state, burning an LLM call before crashing
- Expected: missing checkpoint / no pending `wait_for_answer` interrupt is detected before resuming; router returns HTTP 409 with an actionable detail (e.g. "No pending question for this session — it may have been lost on a server restart. Re-send your message."); no graph execution from empty state
- Area: `packages/agent/orchestrator/session_orchestrator.py`, `apps/api/routers/sessions.py`
- Owner: App Builder
- Acceptance: unit tests — (1) `submit_ask_user_answer` on a session with no pending interrupt → 409, no orchestrator graph invocation; (2) `answer_ask_user` raises a typed error (not KeyError) when the thread has no checkpoint; existing happy-path ask_user tests still pass
- Status: Resolved (T-495 guard via `graph.aget_state` + `NoPendingInterruptError` + router 409; T-498 acceptance tests; gates passed 2026-06-10)

#### Defect: D-007

- Discovered: 2026-06-10, same diagnosis session (198 × `event persist failed: ... violates foreign key constraint "session_events_session_id_fkey"` warnings; ~25 sessions × 8 events each)
- Symptom: (1) deleting a session while its background run (`_run_and_signal` / `_run_resume_and_signal`) is in flight leaves the run executing — it keeps calling the LLM and persisting events into a deleted `decision_sessions` row, producing FK-violation warning spam (observed sequence: `POST .../answer` 202 → `DELETE /sessions/{id}` 204 → resume continues → every event INSERT fails FK). (2) After a uvicorn reload wipes the in-memory `sessions` dict, only `post_message` recovers from DB; `update_session_title`, `submit_ask_user_answer`, `get_messages`, `set_message_feedback` 404 on dict miss even when the DB row exists (observed: session eebeff3b POST /messages 404 at 21:54–21:59 UTC after reload + delete-all race)
- Location: `apps/api/routers/sessions.py` (`delete_session`, `delete_all_sessions`, dict-only lookups), `apps/api/state.py` (`make_event_persister` writes unconditionally; `session_run_ids` tracks run ids but no task handles are kept, so nothing can be cancelled)
- Originating phase: session event log introduction (commit c9e383f) + P13 background-task pattern
- Repro: start a message run, `DELETE /api/v1/sessions/{id}` before it completes → observe `event persist failed` FK warnings until the orphaned run finishes
- Severity: Medium
- Observed: orphaned background runs survive session deletion (wasted LLM spend, FK warning spam, `done` events broadcast for deleted sessions); session endpoints inconsistently recover after restart
- Expected: session deletion cancels the session's in-flight asyncio task and tears down its broadcaster/run-id entries; event persistence stops once the session is deleted; all session-scoped endpoints share `post_message`'s DB-recovery fallback
- Area: `apps/api/routers/sessions.py`, `apps/api/state.py`
- Owner: App Builder
- Acceptance: unit tests — (1) deleting a session with an in-flight (stub-blocked) run cancels the task and no event persist is attempted afterwards; (2) `update_session_title` / `get_messages` / `submit_ask_user_answer` succeed after the in-memory dict is cleared when the DB row exists (404 only when both are absent); no FK-violation warnings in a normal create→run→delete unit flow
- Status: Resolved (T-496 task-handle cancellation + tombstone guard; T-497 shared DB-recovery helper + FK debug downgrade; T-499 acceptance tests; gates passed 2026-06-10)

### Batch B-01 — D-006: resume checkpoint guard (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-495 | `session_orchestrator.py`: before resuming, verify the thread has a checkpoint with a pending interrupt — `graph.aget_state(config)` in `answer_ask_user` (and `resume`); if no checkpoint or no pending `wait_for_answer`/approval interrupt, raise a typed exception (e.g. `NoPendingInterruptError` in the orchestrator module). Defensive: `_node_classify_intent` reads `state.get("session_id")` and raises a descriptive `RuntimeError` if absent (never a bare KeyError). `apps/api/routers/sessions.py` `submit_ask_user_answer`: catch the typed error pre-dispatch (or check before creating the background task) and return HTTP 409 with detail "No pending question for this session — it may have been lost on a server restart. Re-send your message."; emit no `resume_failed` SSE for this case. | Done |

Dependencies: none

### Batch B-02 — D-007: run cancellation on delete + DB recovery (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-496 | Track background run task handles per session (e.g. `session_tasks: dict[str, asyncio.Task]` in `apps/api/state.py`, registered by `post_message`/`submit_ask_user_answer`). `delete_session` and `delete_all_sessions`: cancel the session's task (await suppression of `CancelledError`), then remove broadcaster, ready-event, and run-id entries before deleting the DB row. `_run_and_signal`/`_run_resume_and_signal` must tolerate cancellation (no `done` broadcast, no persists after cancel). | Done |
| T-497 | DB-recovery consistency: extract `post_message`'s recover-from-DB block into a shared helper (e.g. `get_or_recover_session(session_id)`) and use it in `update_session_title`, `get_messages`, `set_message_feedback`, and `submit_ask_user_answer`; 404 only when the session exists in neither the dict nor the DB. Event persister: skip writes once the session has been deleted (guard in `make_event_persister` against the tracked session set) and downgrade the FK-violation log to debug with a single-line message. | Done |

Dependencies: none (parallel-eligible with B-01; B-01 runs first to keep `sessions.py` edits sequential)

### Batch B-03 — Tests + gate (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-498 | Unit tests for D-006 acceptance: ASGITransport POST `/answer` with no pending interrupt → 409 + no graph invocation; `answer_ask_user` on empty thread raises the typed error; happy-path ask_user resume unaffected (existing tests). | Done |
| T-499 | Unit tests for D-007 acceptance: delete-cancels-run (stub-blocked run task is cancelled; no event persist after); DB-recovery for `update_session_title`/`get_messages`/`submit_ask_user_answer` (dict cleared, DB row present → success; both absent → 404); event persister skip-after-delete. | Done |
| T-500 | Gate: `make test-unit && make lint && make typecheck && make build && make test-playwright` — proof-of-execution (command, exit code, output tail per gate). Mark D-006 and D-007 Resolved on pass. | Done |

Dependencies: B-01, B-02

---

## P80 — Verifier Blocked-Path UX — In Progress

**Goal:** Resolve D-008. The P61 rule-based findings verifier blocks legitimate
no-tool answers stochastically (Rule 1 regex `\d|no\b|none\b|なし` fires on any digit —
e.g. SQL-writing responses), and a blocked run surfaces as a hard failure with a
**misattributed** error ("run blocked by tool-loop guard" — the `runtime.py:1405`
fallback string) instead of the already-prepared soft fallback text. Third misleading
error-surface incident on 2026-06-10.

#### Defect: D-008

- Discovered: 2026-06-10, live user session 22:47 UTC (same query that passed at 22:30 — content lottery)
- Symptom: lookup query answered without tool calls → `verify_findings rule-based result: blocked` ×2 (initial + goal-loop refinement) → UI shows "Agent control failed: run blocked by tool-loop guard"
- Root causes: (1) `_rule_based_verify` Rule 1 matches ANY digit in a no-tool response — legitimate code-writing answers fail stochastically; (2) `blocked_error` fallback at `packages/agent/runtime.py:1405` misattributes every verifier block to the tool-loop guard; (3) `run_status == "blocked"` maps to `specialist_status = "failed"`, so the prepared soft text ("Could not verify findings…") is displaced by a hard SSE error (`orchestrator/runtime.py:128`)
- Status: Resolved (T-501–T-503 fixes + T-504 tests; gates passed 2026-06-10)

### Batch B-01 — Truthful block reason + soft-fail + Rule 1 refinement (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-501 | `packages/agent/runtime.py`: carry a truthful `blocked_reason` in graph state — set by each blocking site (`verify_findings` rule result → "findings verifier: response not grounded in tool results"; degenerate final response → "degenerate response after revision"; loop-guard-forced path retains "tool-loop guard"). `blocked_error` uses `blocked_reason`; remove the misattributing default string. | Done |
| T-502 | Soft-fail blocked runs: map `run_status == "blocked"` to `specialist_status = "completed"` with the existing fallback text ("Could not verify findings. Please rephrase your question or try again.") as the reply, keeping `blocked_reason` in output meta (e.g. `output["verification"]["blocked_reason"]`) for trace UI; no `agent_failed` SSE error for verifier blocks. Genuine `error` status path unchanged. | Done |
| T-503 | `_rule_based_verify` Rule 1 refinement: strip fenced code blocks (``` … ```) and inline code spans from the conclusion before applying `_FABRICATED_NO_DATA_RE`, so digits/keywords inside code (SQL answers) do not trigger the fabrication heuristic; prose-level digits still do. Rules 1b/2 unchanged. | Done |

Dependencies: none

### Batch B-02 — Tests + gate (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-504 | Unit tests: Rule 1 passes a no-tool SQL-fenced answer containing digits, still blocks prose digit claims without tools; blocked run returns completed SpecialistResult with fallback text + blocked_reason meta, no agent_failed SSE; blocked_reason strings per blocking site. Update existing tests asserting blocked→failed mapping or the old default error string. | Done |
| T-505 | Gate: `make test-unit && make lint && make typecheck && make build && make test-playwright` — proof-of-execution. Mark D-008 Resolved on pass. | Done |

Dependencies: B-01

---

## P81 — Tool Scenario Modal Content Refresh — Done (2026-06-10)

**Goal:** Fix 9 broken and 3 partially-broken scenarios in `ToolScenarioModal.tsx` so every
prompt, description, and category reflects the actual schema (post-0009 migration table names),
seed data (WH-001/WH-002 only), and tool registry (train_forecast not LLM-callable; job_dispatch
not user-facing; nl_query is the sole Text2SQL tool). Remove the "Job Dispatch (HITL)" category.
Standardize all user-visible prompts to English (AGENTS.md §Language Convention).
Update the Playwright spec that asserts category names and prompt text.

Dependencies: P80 Done

### Batch B-01 — Modal content fixes (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-506 | Data Query / "schema": fix prompt from `inventoryテーブルのスキーマを確認して` → English, using `inventory_snapshot`. Update title/description to English. | Done |
| T-507 | Data Query / "quality": fix prompt from `inventoryテーブルのデータ品質をチェック…` → English, using `inventory_snapshot`. | Done |
| T-508 | Data Query / "sql": update title to "Natural Language Query", description to reflect `nl_query` (not raw SQL since P55). Prompt rewritten to English. | Done |
| T-509 | Forecasting / "demand-forecast": remove invalid "DC West" location and location param (forecast tool takes sku_id + horizon_days only). Rewrite to SKU-001, 30-day horizon, English. | Done |
| T-510 | Forecasting / "multi-sku": rewrite to realistic scope — a few named SKUs, expect a tabular answer in chat (no CSV file output). English. | Done |
| T-511 | Forecasting / "train-model": remove scenario entirely (train_forecast not LLM-callable since P64 registry cleanup). | Done |
| T-512 | Ask User / "au-fully-specified": replace "DC West" with WH-001 or WH-002 so the fully-specified premise holds with real data. | Done |
| T-513 | Ask User / "au-mostly-specified": replace past "Q3 2025" with "next quarter". | Done |
| T-514 | Ask User / "au-warehouse-given": replace "DC West" with WH-001 for consistency with real seed data. | Done |
| T-515 | Supply Chain / "sc-order-delay": replace unresolvable "#ORD-1042" prompt with a question answerable by real tools (e.g. delayed supply orders for a SKU or supplier, using get_delayed_supply_orders / analyze_supply_risk). | Done |
| T-516 | Remove "Job Dispatch (HITL)" category (all 3 scenarios: job-simulate, job-optimize, job-forecast). Standardize all remaining scenario prompts to English throughout the CATEGORIES array. | Done |

Dependencies: none

### Batch B-02 — Playwright spec update + quality gate (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-517 | `tests/e2e/playwright/tool_scenario_modal.spec.ts`: remove "Job Dispatch (HITL)" assertion from the "all 6 category tabs" test (now 5 categories); update the SQL card click test locator `/在庫テーブル/` to match the new English prompt text; remove any assertion on "Train Forecast Model" if present. | Done |
| T-518 | Gate: `make test-unit && make lint && make typecheck && make test-playwright` — proof-of-execution (command + exit code + output tail). | Done |

Dependencies: B-01

---

## P82 — Seed Data Staleness & list_stockout_risk missing_data Fix — Done (2026-06-10)

**Goal:** Resolve the Judge-reported FAIL (aggregate 0.72, completeness 0.4) caused by
two separate defects: (1) demand_history seed data is anchored to 2025 — every re-seed
after 2026-01-01 generates demand rows outside the tool's 30-day rolling window, making
`avg_daily=0` for all 30 SKUs and `list_stockout_risk` always returning `count=0`; (2)
`list_stockout_risk` returns `missing_data: []` even when demand history is absent, so the
agent cannot distinguish "no stockout risk" from "evaluation impossible due to missing data".
The verifier blocking (pre-P80 symptom) is already resolved; this phase fixes the root
causes so the question "Which products are at stockout risk this week?" returns a truthful,
data-grounded answer.

Dependencies: P81 Done

### Batch B-01 — Relative-date seed script (Infra) — Done

| Task | Description | Status |
|---|---|---|
| T-519 | `scripts/generate_sample_data.py`: replace all fixed calendar dates with expressions relative to `date.today()`. Specific changes: `START_DATE = date(2025, 1, 1)` → `date.today() - timedelta(days=365)`; `snapshot_date = date(2026, 5, 19)` → `date.today() - timedelta(days=22)` ("today minus ~3 weeks"); `base_order_date = date(2026, 4, 1)` → `date.today() - timedelta(days=70)` ("today minus ~10 weeks"); supply-order status cutoffs `date(2026, 5, 19)` (delivered threshold) → `date.today() - timedelta(days=22)` and `date(2026, 6, 1)` (in_transit threshold) → `date.today() - timedelta(days=9)`; `period_start = date(2025, 1, 1)` → `date.today() - timedelta(days=365)` and `period_end = date(2025, 12, 31)` → `date.today() - timedelta(days=1)`. All `START_DATE` references in `generate_forecast_history` must also use the relative value. Confirm re-seed procedure: `uv run python scripts/generate_sample_data.py && make seed` (or equivalent). | Done |

Dependencies: none

### Batch B-02 — list_stockout_risk missing_data population (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-520 | `packages/tools/list_stockout_risk_tool.py`: in `handle()`, after the per-SKU loop, collect all SKU IDs where `avg_daily == 0` into a `no_demand_skus` list. If non-empty, append one `missing_data` entry per SKU: `"no demand history in last 30 days: {sku_id}"` (matching the format already used by `calculate_stockout_risk`). Return `missing_data` populated in the `ToolResult` output instead of always `[]`. Update `output_schema` if needed (already has `missing_data: array` — confirm type is `array of string`). | Done |

Dependencies: none

### Batch B-03 — Tests + gate (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-521 | Unit test for `list_stockout_risk` (new): when `_fetch_all_stockout_risk` returns rows with `avg_daily=0` for all SKUs (no demand history), `missing_data` in the output is non-empty with one entry per SKU; `items` is `[]` and `count` is 0. Add a second parametrized case: when some SKUs have `avg_daily > 0` and some have `avg_daily == 0`, only the zero-demand SKUs appear in `missing_data`, and only the positive-demand SKUs appear in `items` (if their risk level meets the threshold). | Done |
| T-522 | Gate: `make test-unit && make lint && make typecheck` — proof-of-execution (command, exit code, output tail). | Done |

Dependencies: B-01, B-02

---

## P83 — LLM Usage Recording Restoration — Done (2026-06-10)

**Goal:** Restore `llm_usage` row writes for every real LLM call. The P54 LangChain migration
(commit ccfdb54) replaced `create_llm_client(usage_writer=_real_usage_writer)` with
`create_model_registry()`, which has no usage hook — since 2026-06-07 no LLM call writes to
`llm_usage`, so `GET /sessions/{id}/usage`, admin `list_llm_usage`, and the web `/llm-calls`
and `/usage` pages show no new data. Done when: every ChatModel invocation (intent
classification, planner, ReAct loop, final response, groundedness verifier, nl_query, history
summarization) produces an `llm_usage` row with model, token counts, latency, and
prompt/response capture (per the 2026-06-04 decision), attributable to its session via
`agent_step_id`, for all three providers (anthropic/ollama/openai); recording failures must
never break the agent run (fire-and-forget, log-on-error, matching `_real_usage_writer`
semantics).

Dependencies: P82 Done

### Batch B-01 — Usage recording callback handler + registry wiring (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-523 | New module `packages/agent/llm/usage_recording.py`: `UsageRecordingCallbackHandler(AsyncCallbackHandler)` accepting a `UsageWriter` (reuse the existing type in `packages/agent/llm/__init__.py`; signature unchanged). `on_chat_model_start` records start time and serialized prompt messages keyed by `run_id`; `on_llm_end` extracts model name, `usage_metadata` (input/output/cache tokens when present), response text, and tool calls from the `LLMResult` generation, computes `latency_ms`, and invokes the writer with `session_id` / `agent_step_id` / `specialist_role` read from the run's metadata (LangChain invoke `config={"metadata": ...}` propagates to callbacks; LangGraph `astream_events` propagates graph config metadata to child model calls). Writer invocation must be non-blocking for the caller and exception-safe (log warning, never raise). `total_cost_usd`: 0.0 for ollama/openai; anthropic may be 0.0 in this phase (cost computation deferred — record tokens; no pricing table required). | Done |
| T-524 | Wiring: `create_model_registry()` gains an optional `usage_writer: UsageWriter \| None = None` parameter; when provided, attach a `UsageRecordingCallbackHandler` to every constructed ChatModel via the `callbacks` constructor field (all providers). Default `None` keeps current behavior (no handler) for tools/tests. `apps/api/state.py get_orchestrator`: pass `usage_writer=_real_usage_writer` (already defined at `state.py:156`, currently orphaned). `_real_usage_writer` must create an `agent_steps` row via `make_step(session_id, step_type="llm_call", specialist_role=...)` when `agent_step_id` is None but `session_id` is available, so rows from sites without an existing step (nl_query, history summarization, verifier) still join to the session in `get_session_totals`; skip the write only when both are None. Call sites that already create steps (`classify_intent`, `select_execution_mode` in `session_orchestrator.py`) must stop discarding the `make_step` return value and pass it via invoke config metadata; `AgentRuntime` nodes pass `ctx.agent_step_id` / `ctx.session_id` / role through graph config metadata. | Done |

Dependencies: none

### Batch B-02 — Tests + gate (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-525 | Unit tests for `UsageRecordingCallbackHandler`: (1) `on_chat_model_start` + `on_llm_end` with a fake `LLMResult` carrying `usage_metadata` → writer called once with correct model, token counts, non-None latency, serialized prompt and response; (2) metadata propagation — `session_id`/`agent_step_id`/`specialist_role` from run metadata reach the writer; (3) writer raising an exception does not propagate to the caller; (4) `on_llm_end` without a prior start event does not crash. Zero-network rule applies — fake `LLMResult`/metadata objects only, no real model calls. | Done |
| T-526 | Unit tests for wiring: `create_model_registry(usage_writer=...)` attaches the handler to each model's `callbacks`; default call without `usage_writer` attaches nothing; `_real_usage_writer` step-fallback — `agent_step_id=None` + `session_id` present → `make_step` called and row created with the returned id (mock `LlmUsageRepository`/`make_step`); both None → no write. Update any existing tests broken by the `classify_intent`/`select_execution_mode` step-id propagation. | Done |
| T-527 | Gate: `make test-unit && make lint && make typecheck && make build && make test-playwright` — proof-of-execution (command, exit code, output tail per gate). | Done |

Dependencies: B-01

---

## P84 — Demo Data Risk Distribution Fix — Done (2026-06-10)

**Goal:** Modify `scripts/generate_sample_data.py` so that re-seeding the database causes
the demo query "Which products are at stockout risk this week?" to return a realistic risk
distribution (2 critical + 2 high + 3 medium SKUs) instead of zero matches. The fix uses
deterministic days-of-cover overrides for a fixed set of SKU IDs; all other SKUs remain
ample (current behaviour). Incoming supply for risk SKUs is pushed beyond the 7-day horizon
so it does not inadvertently rescue the risk classification.

Dependencies: P82 Done

### Batch B-01 — Seed script risk distribution (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-528 | `scripts/generate_sample_data.py`: add a `SKU_RISK_BANDS` mapping at module level — `{"SKU-001": "critical", "SKU-002": "critical", "SKU-003": "high", "SKU-004": "high", "SKU-005": "medium", "SKU-006": "medium", "SKU-007": "medium"}`. In `generate_inventory`, when `sku_id` is in `SKU_RISK_BANDS`, bypass the random `normal_on_hand` / stochastic branches and set `on_hand` deterministically: critical → `int(daily_demand * 2)` total across both warehouses (split evenly); high → `int(daily_demand * 7.4)` total; medium → `int(daily_demand * 9.0)` total. For single-warehouse splits, assign `on_hand = total // 2` to WH-001 and `total - total // 2` to WH-002; `on_order = 0` for all risk SKUs. In `generate_supply`, when `sku_id` is in `SKU_RISK_BANDS`, force all non-delivered order arrivals to `date.today() + timedelta(days=10)` (outside the 7-day tool horizon) so incoming supply cannot rescue the classification; orders with `arrival_date < _delivered_cutoff` are kept as delivered (already arrived, not counted). Seed value 42 is preserved; all other SKUs are generated by the existing random path unchanged. **Fix iteration (2026-06-10):** real-DB verification showed SKU-005/006 classified as "low" (nominal demand used for on_hand, but tool uses actual 30-day rolling average → effective DOC > 9 → ratio ≥ 0.5). Corrected: new `compute_recent_avg` helper mirrors the tool SQL; `generate_demand_history` returns per-SKU recent averages; `generate_inventory` uses `round(actual_avg * DOC)` for risk-band on_hand. | Done |

Dependencies: none

### Batch B-02 — Tests + gate (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-529 | Unit tests: add a parametrized test in `tests/unit/` (new file or append to `test_generate_sample_data.py` if it exists) covering: (a) `generate_inventory` for a critical-band SKU produces `on_hand_qty` < `daily_demand * 7` (net of incoming=0 → projected < 0 → critical); (b) `generate_inventory` for a high-band SKU produces `0 ≤ projected_ending_stock < 0.1 * demand_forecast`; (c) `generate_inventory` for a medium-band SKU produces `0.1 * demand_forecast ≤ projected_ending_stock < 0.5 * demand_forecast`; (d) `generate_supply` for a risk-band SKU has no non-delivered orders with `expected_arrival ≤ date.today() + timedelta(days=7)`. Existing unit tests for `list_stockout_risk` use mocked DB rows — confirm they are unaffected. Tests appended to `tests/unit/test_sample_data.py`. **Fix iteration (2026-06-10):** tests updated to use `_actual_recent_avg` (calls `gen.compute_recent_avg` on generated demand_history.csv) instead of nominal `_sku_demand`; assertions now use the same demand figure the tool uses at runtime; `_sku_demand` helper removed. | Done |
| T-530 | Gate: `make test-unit && make lint && make typecheck` — proof-of-execution (command, exit code, output tail). Confirm no existing tests reference concrete on_hand values from the seed data (they use mocked rows). **Executed 2026-06-10:** unit 921 passed / 11 skipped exit 0, ruff clean, mypy 161 files clean. DB reseeded; live `list_stockout_risk(horizon_days=7, min_risk_level="medium")` returned count=7: SKU-001/002 critical (ratio −0.72), SKU-003/004 high (0.057/0.078), SKU-005/006/007 medium (0.287–0.293). | Done |

Dependencies: B-01

---

## P85 — Agents & Tools Registry: Tool Execution Stats Restoration — In Progress

**Goal:** The Tools tab on `/agents` shows live execution counts and last-call timestamps again.
Root cause (two-part): (1) commit d0977b8 (P20, 2026-06-03) replaced the legacy `tool_completed`
SSE event with `graph_node` events, but `get_registry` in `apps/api/routers/admin.py` still
aggregates `session_events WHERE event_type = 'tool_completed'` — 0 rows ever since; (2) the
replacement tool `graph_node` events are put directly on the raw SSE queue by `AgentRuntime`
(`packages/agent/runtime.py:775/798/815`), bypassing `SessionOrchestrator._push` and its
`_event_persister`, so they are streamed to the client but never written to `session_events`
(DB confirmed 2026-06-11: 90 graph_node rows, all kind=orchestrator/agent, 0 kind=tool, while
`llm_usage` shows 89 calls with tool_calls). Done when: an agent run that executes tools
produces `session_events` rows with `event_type='graph_node'`, `payload->>'kind'='tool'`, and
`payload->>'name'` = tool name; and `GET /api/v1/admin/registry` returns non-zero
`execution_count` / non-null `last_executed_at` for those tools.

Dependencies: P84 Done

### Batch B-01 — Tool event persistence + registry query fix (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-531 | Persist tool `graph_node` events to `session_events`. `SessionOrchestrator._push` persists via `self._event_persister`, but `AgentRuntime`'s tool-event emission sites (`packages/agent/runtime.py` `_run_single_read_only_tool` and `_execute_tools_node`, plus `awaiting_approval`/`session_paused` sites) `await sse_queue.put(...)` on the raw queue obtained from graph `configurable["sse_queue"]` — events reach the live SSE stream but never the persister. Fix by making the persister reachable from the runtime event path: recommended approach is to pass the persister through graph `configurable` alongside `sse_queue` (all three config-build sites in `session_orchestrator.py` ~L815/877/924) and emit via a small shared helper that both puts to the queue and fire-and-forgets the persister; an equivalent queue-wrapper approach is acceptable. Constraints: persister failures must never break the run (existing `make_event_persister` in `apps/api/state.py` is already exception-safe and fire-and-forget — do not double-wrap with new error handling that raises); no change to `SessionOrchestrator.__init__` or any public interface; events must keep the exact payload shape currently streamed (frontend depends on it). | Done |
| T-532 | `apps/api/routers/admin.py get_registry`: replace the dead `tool_completed` aggregation with `SELECT payload->>'name' AS tool_name, COUNT(*)::int AS execution_count, MAX(created_at) AS last_executed_at FROM session_events WHERE event_type = 'graph_node' AND payload->>'kind' = 'tool' AND payload->>'event' = 'end' AND payload->>'name' IS NOT NULL GROUP BY payload->>'name'`. Count `end` events only (one per completed tool call; error-status ends count as executions). Response models and frontend contract unchanged. | Done |

Dependencies: none

### Batch B-02 — Tests + gate (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-533 | Unit tests for the persistence wiring: (1) an `AgentRuntime` tool execution with both an SSE queue and a persister wired through graph config produces persisted tool `graph_node` start+end events (assert event_type/kind/name/event fields); (2) persister absent (None) → queue still receives events, no crash; (3) persister raising → run completes, queue events unaffected. Build on existing patterns in `tests/unit/test_session_orchestrator_persistence.py` and `tests/unit/test_sse_queue_injection.py`; zero-network rule applies (stub LLM / fake tools). Also cover `get_registry` aggregation if an existing unit/integration test exercises it (mocked pool rows: tool end events counted, start events excluded). | Done |
| T-534 | Gate: `make test-unit && make lint && make typecheck && make build` — proof-of-execution (command, exit code, output tail per gate). | Done |

#### Defect: D-009

- Status: Resolved (2026-06-11 — test-side fix: stub registries aligned with P78 deterministic routing; `make test-integration` 16 passed exit 0)
- Severity: Medium
- Repro: `make test-integration` (fails: `tests/integration/test_ask_user_hitl_variants.py::test_fully_specified_request_does_not_raise_graph_interrupt`, `tests/integration/test_prompts_mock_llm.py::test_ask_user_resume_via_answer_returns_session_response`)
- Observed: Both tests fail with `RuntimeError: AgentRuntime requires model_registry — _lc_model is not set` (raised in node `call_model`). Pre-existing, NOT introduced by P85 — reproduced identically at baseline commit d05b122 (pre-P85) via worktree.
- Expected: Both tests pass. Latent since P78 (Deterministic Routing Completion, 2026-06-10): `select_execution_mode` now maps `domain_analysis` → `single_agent`/`["control"]` deterministically (`packages/agent/orchestrator/routing.py _INTENT_MODE_MAP`); the tests still assume LLM-driven routing can return their stubbed `AgentRoute(mode="direct_chat")`, so execution reaches `ControlAgent`'s `AgentRuntime`, whose `make_stub_registry`/`_direct_registry` stub provides only an `"orchestrator"`-role model → no `"control"` model → `_lc_model is None`. P78's gate did not include `make test-integration`, so the break went undetected.
- Area: tests/integration (test-side; production routing behavior is correct per P78 design)
- Owner: Test/Review
- Acceptance: `make test-integration` exit 0 with both tests passing, preserving their original behavioral intent (no-interrupt for fully-specified request; ask_user resume returns a complete SessionResponse).

Dependencies: B-01
