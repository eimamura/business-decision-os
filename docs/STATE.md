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
| P10 — Web UI Server State Standardisation (T-076 – T-080) | 2026-06-03 |
| P11 — AskUser: Pre-execution Information Gathering (T-083 – T-085) | 2026-06-03 |
| P12 — Test Session Pollution Fix (T-086 – T-087) | 2026-06-03 |
| P13 — AskUser: interrupt()-based Mid-Execution Gathering (T-088 – T-099) | 2026-06-03 |
| P14 — Agent Node Cards (T-100 – T-108) | 2026-06-03 |
| P15 — Text Streaming / text_delta SSE (T-109 – T-116) | 2026-06-03 |
| P16 — Backward Compat Removal (T-117 – T-119) | 2026-06-03 |
| P17 — Orchestrator Cost Reduction (T-120 – T-123) | 2026-06-03 |
| P18 — Tool Scenario Coverage (T-124) | 2026-06-03 |
| P19 — SSE Consumer Consolidation (T-125 – T-127) | 2026-06-03 |

---

## Active Phase

None.

---

## Last Completed Phase

**Phase: Access Control & HITL Foundation**

Started: 2026-06-02
Completed: 2026-06-02

Goal: Introduce DB-backed user authentication and role-based tool access control,
classify tools by safety level, add approval idempotency, refactor routing and
response assembly into pure/testable modules, add the clarification flow for
unknown intents, and wire the full end-to-end HITL pause-and-resume loop.

### Tasks in Scope

| Task | Description | Status |
|---|---|---|
| T-012 | Add `authorize_user` with DB-backed role lookup | Done |
| T-013 | Implement 2-layer role × intent tool access control | Done |
| T-014 | Add approval idempotency guard | Done |
| T-015 | Refactor routing into pure functions | Done |
| T-016 | Adopt IntentRegistry pattern | Done |
| T-017 | Add `result_builder` response structuring | Done |
| T-018 | Classify tools as `read_only` / `write` / `hitl` in ToolRegistry | Done |
| T-019 | Add `ask_clarification` flow for unknown intents | Done |
| T-026 | HITL end-to-end flow | Done |

### Dependency Order

```
T-012 (independent)  ─┐
T-018 (independent)  ─┴─→  T-013 (depends on T-012, T-018)
                                     │
                                     ↓
T-014 (depends on T-005 ✓)           │
T-019 (depends on T-005 ✓)           │
                                     ↓
                            T-026 (depends on T-013, T-014, T-018, T-019)

Parallel (no dependencies, can run concurrently with the above):
  T-015 — independent
  T-016 — independent
  T-017 — independent
```

Batch execution order:
1. Batch 1 (parallel): T-012, T-018, T-015, T-016, T-017
2. Batch 2: T-013 (after T-012 + T-018 Done)
3. Batch 3 (parallel): T-014, T-019 (T-005 already Done — pre-condition met)
4. Batch 4: T-026 (after T-013, T-014, T-018, T-019 all Done)

## Active Lease

None.

## Last Completed Batch

P19 (2026-06-03): T-125–T-127 Done. eventsToSteps() moved to apps/web/lib/sse-steps.ts; ChatStateContext extended with processingSteps/sessionStartedAt/sessionEndedAt; AgentActivityPanel EventSource removed; EvidenceSources adapted to AgentStep[]; 56 Vitest pass, 533 pytest pass, typecheck + lint exit 0.

## Previous Completed Batch

P14 Batch 3 (2026-06-03): T-106–T-108 Done. useAgentProgress.test.ts (5 tests), AgentNodeCard.test.tsx (5 tests), ExecutionProgressPanel.test.tsx (10 tests). All 20 Vitest pass. pytest 525 pass, 11 skipped.

## Last Validation

2026-06-03: P19 SSE consumer consolidation. cd apps/web && npx vitest run → 56 passed (8 files). uv run pytest tests/unit/ -q → 533 passed, 11 skipped. npx tsc --noEmit -p apps/web/tsconfig.json → exit 0. make lint → all checks passed.

## Blockers

None.
