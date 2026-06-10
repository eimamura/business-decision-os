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

## P71 — Goal Evaluation Loop — Not Started

**Goal:** Make the goal first-class and close the outer loop: derive GoalSpec, evaluate the
answer against it, allow exactly one refinement pass with optional intent re-route.

Dependencies: P70 Done

### Batch B-01 — ADR (Orchestrator) — Done

| Task | Description | Status |
|---|---|---|
| T-451 | ADR `docs/adr/2026-06-10-autonomy-loops.md` — goal loop, grounded verification, feedback learning; invariants (SSE schema, protocols, additive-only changes); bounded LLM budget. | Done |

Dependencies: none

### Batch B-02 — GoalSpec + evaluate_goal node + refinement loop (App Builder) — Not Started

| Task | Description | Status |
|---|---|---|
| T-452 | `packages/agent/orchestrator/models.py` — add `GoalSpec {goal_text: str, success_criteria: list[str] (≤3)}` and `GoalEvaluation {satisfied: bool, missing: str|None, reroute_category: str|None}` Pydantic models; add additive-optional `goal_evaluation: dict | None = None` to `SessionResponse`. `OrchestratorState` gains `goal`, `goal_eval`, `refine_count` keys. | Not Started |
| T-453 | `session_orchestrator.py` — new node `set_goal` (after classify_intent, non-chat only: one structured-output call, orchestrator role, fail-open to `GoalSpec(goal_text=query, success_criteria=[])`); new node `evaluate_goal` (after run_sequential: structured GoalEvaluation verdict; fail-open to satisfied=True); conditional edge: satisfied or refine_count≥1 → END, else refine path → re-enter run_sequential with `missing` appended to instruction and intent updated when `reroute_category` is a valid different category. direct_chat bypasses entirely. | Not Started |
| T-454 | SSE: `set_goal`/`evaluate_goal` emit standard `graph_node` events (kind="orchestrator", meta includes satisfied/missing for evaluate_goal); populate `SessionResponse.goal_evaluation`. Event schema unchanged. | Not Started |

Dependencies: B-01

### Batch B-03 — Tests + gate (Test/Review) — Not Started

| Task | Description | Status |
|---|---|---|
| T-455 | Unit tests: satisfied verdict → single run; unsatisfied → exactly one refinement then END (cap enforced); chat intent bypasses set_goal/evaluate_goal; fail-open on verdict parse failure. | Not Started |
| T-456 | Unit test: reroute_category updates intent and tool subset on the refinement pass; invalid category ignored. | Not Started |
| T-457 | `make test-unit && make lint && make typecheck` — all pass (proof-of-execution). | Not Started |

Dependencies: B-02

---

## P72 — Grounded Runtime Evaluator — Not Started

**Goal:** Reconnect the dead `add_revision_message → call_model_final` self-correction path
behind a real LLM groundedness verdict, keeping rule-based checks as pre-filter.

Dependencies: P71 B-01 (ADR); parallel-eligible with P71 B-02 (disjoint files)

### Batch B-01 — Groundedness verdict + revision rewire (App Builder) — Not Started

| Task | Description | Status |
|---|---|---|
| T-458 | `packages/agent/runtime.py` — add `GroundednessVerdict {grounded: bool, unsupported_claims: list[str]}`; in `_verify_findings_node`, after rule-based pre-filter passes, run one structured-output groundedness call (control role via model_registry) gated by: intent ∈ {domain_analysis, cross_domain_analysis, decision_support, supply_chain} AND tool_results non-empty AND model_registry present; fail-open to rule-based result on any verifier error. | Not Started |
| T-459 | Wire `needs_revision`: `_after_verify` returns "add_revision_message" when verdict is ungrounded; revision message embeds the specific `unsupported_claims`; existing one-retry `call_model_final` path preserved (no second verify). | Not Started |
| T-460 | Verdict surfaced in run output meta (e.g., `verification: {grounded, revised}`) for observability; no SSE schema change. | Not Started |

Dependencies: P71 B-01

### Batch B-02 — Tests + gate (Test/Review) — Not Started

| Task | Description | Status |
|---|---|---|
| T-461 | Unit tests: grounded verdict → END no revision; ungrounded → exactly one revision retry with claims in message; verifier exception → falls back to rule-based; gating (chat/lookup intents and empty tool_results skip the LLM verdict). | Not Started |
| T-462 | `make test-unit && make lint && make typecheck` — all pass (proof-of-execution). | Not Started |

Dependencies: B-01

---

## P73 — Feedback Learning Loop — Not Started

**Goal:** Close decide → observe(feedback) → recall: user feedback lands on the decision
record and changes how past decisions are injected into future context.

Dependencies: P71 B-01 (ADR)

### Batch B-01 — Migration (Infra) — Done

| Task | Description | Status |
|---|---|---|
| T-463 | Alembic migration `0018_decision_log_outcome.py` — add `outcome SMALLINT NULL` to `decision_log` (additive; +1/−1/NULL). | Done |

Dependencies: none

### Batch B-02 — Outcome write path + context annotation (App Builder) — Not Started

| Task | Description | Status |
|---|---|---|
| T-464 | `packages/memory/decision.py` — add `set_latest_outcome(session_id: str, outcome: int) -> bool` (updates latest `record_type='decision'` row of the session); `search()` includes `outcome` in returned rows. | Not Started |
| T-465 | `apps/api/routers/sessions.py` feedback endpoint — after successful `set_message_feedback`, best-effort call `DecisionMemoryStore.set_latest_outcome` (try/except log-warning; never fails the request). | Not Started |
| T-466 | `packages/agent/control/control_agent.py` — Past Decisions block annotates entries with `[user feedback: positive|negative]` when outcome present; `_SYSTEM_PROMPT` gains one instruction to avoid approaches that previously received negative feedback. | Not Started |

Dependencies: B-01

### Batch B-03 — Tests + gate + programme sign-off (Test/Review) — Not Started

| Task | Description | Status |
|---|---|---|
| T-467 | Unit tests: `set_latest_outcome` SQL path (mock pool); endpoint non-fatal on store failure; Past Decisions annotation rendering; prompt instruction present. | Not Started |
| T-468 | Integration test (real DB): write decision record → PATCH feedback → decision_log.outcome updated → search returns outcome. | Not Started |
| T-469 | Programme sign-off: `make test-unit && make lint && make typecheck && make test-integration && make build && make test-playwright` — all pass (proof-of-execution). | Not Started |

Dependencies: B-02, P71 Done, P72 Done
