# STATE.md

Orchestrator execution state. Written only by bdos-orchestrator.

---

## Completed Phases

| Phase | Completed |
|---|---|
| Domain Integrity (T-001 – T-011) | 2026-06-02 |
| Access Control & HITL Foundation (T-012 – T-019, T-026) | 2026-06-02 |
| P3 — Observability & UX (T-020 – T-025, T-027 – T-029) | 2026-06-02 |
| P4 — Job Execution & HITL Flow (T-030 – T-039) | 2026-06-02 |
| P5 — Test Infrastructure & Cost Reduction (T-040 – T-045) | 2026-06-02 |
| P6 — Chat UI Stability (T-046 – T-054) | 2026-06-02 |
| P7 — CI Quality & Memory Loop Validation (T-055 – T-058) | 2026-06-02 |
| P8 — Mock Mode for Cost-Free UI Testing (T-059 – T-062) | 2026-06-02 |
| P9 — LangGraph Migration (T-063 – T-075) | 2026-06-02 |
| P10 — Web UI Server State Standardisation (T-076 – T-082) | 2026-06-03 |
| P11 — AskUser: Pre-execution Information Gathering (T-083 – T-085) | 2026-06-03 |
| P12 — Test Session Pollution Fix (T-086 – T-087) | 2026-06-03 |
| P13 — AskUser: interrupt()-based Mid-Execution Gathering (T-088 – T-099) | 2026-06-03 |
| P14 — Agent Node Cards (T-100 – T-108) | 2026-06-03 |
| P15 — Text Streaming / text_delta SSE (T-109 – T-116) | 2026-06-03 |
| P16 — Backward Compat Removal (T-117 – T-119) | 2026-06-03 |
| P17 — Orchestrator Cost Reduction (T-120 – T-123) | 2026-06-03 |
| P18 — Tool Scenario Coverage (T-124) | 2026-06-03 |
| P19 — SSE Consumer Consolidation (T-125 – T-127) | 2026-06-03 |
| P20 — LangGraph-Native SSE Pipeline Rebuild (T-128 – T-134) | 2026-06-03 |

---

## Active Phase

None.

---

## Last Completed Phase

**Phase: P20 — LangGraph-Native SSE Pipeline Rebuild**

Started: 2026-06-03
Completed: 2026-06-03

Goal: Replace 8 manual SSE progress event types with a single `GraphNodeEvent` covering
orchestrator/agent/tool lifecycle. Introduce `graphRun: GraphRunNode[]` as frontend single
source of truth, eliminating dual state management and O(n²) `eventsToSteps()` recomputation.
EvidenceSources now shows real tool output data instead of hardcoded defaults.

### Tasks in Scope

| Task | Description | Status |
|---|---|---|
| T-128 | Add `GraphNodeEvent` + `TokenCost` to schema; remove 8 legacy event types | Done |
| T-129 | Migrate `_execute_tools_node` to `graph_node` SSE format | Done |
| T-130 | Migrate `_run_agent()` to `graph_node` SSE format | Done |
| T-131 | Replace `ainvoke`/`astream` with `_astream_run()` in `SessionOrchestrator` | Done |
| T-132 | Remove `plan_created` pushes from `planning.py` | Done |
| T-133 | Introduce `graphRun: GraphRunNode[]` as frontend single source of truth | Done |
| T-134 | Rewrite frontend tests; add `graph_node` assertions to integration test | Done |

## Active Lease

None.

## Last Completed Batch

P20 (2026-06-03): T-128–T-134 Done. GraphNodeEvent + TokenCost added to schema; 8 legacy progress event types removed; AgentRuntime._execute_tools_node emits graph_node tool events with agent_run_id parent linking; _run_agent() emits graph_node agent events with token_cost; SessionOrchestrator._astream_run() drives astream_events(v2) for orchestrator nodes; plan_created pushes removed; graphRun: GraphRunNode[] replaces processingSteps + agentNodes + executionMode in ChatStateContext; AgentActivityPanel and EvidenceSources migrated; sse-steps.ts deleted; 42 Vitest pass, typecheck exit 0.

## Previous Completed Batch

P19 (2026-06-03): T-125–T-127 Done. eventsToSteps() moved to apps/web/lib/sse-steps.ts; ChatStateContext extended with processingSteps/sessionStartedAt/sessionEndedAt; AgentActivityPanel EventSource removed; EvidenceSources adapted to AgentStep[]; 56 Vitest pass, 533 pytest pass, typecheck + lint exit 0.

## Last Validation

2026-06-03: P20 LangGraph-native SSE pipeline rebuild. cd apps/web && npx vitest run → 42 passed (8 files). npx tsc --noEmit -p apps/web/tsconfig.json → exit 0. Python files AST-valid; full pytest suite requires Docker.

## Blockers

None.
