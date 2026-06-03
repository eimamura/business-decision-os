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

---

## Active Phase

**P9 — LangGraph Migration** (Not Started — tasks defined 2026-06-02)
ADR: `docs/adr/2026-06-02-langgraph-migration.md`
Tasks: T-063 – T-075

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

P9-B2 T-068/T-069/T-072 (parallel) — App Builder — acquired 2026-06-02

## Last Completed Batch

P9-B1 complete (2026-06-02): T-065 (AgentRuntime → StateGraph with call_model/execute_tools/verify_findings nodes), T-066 (HITL via interrupt(): prepare_hitl+wait_for_approval nodes, HITLPause removed). 470 unit tests pass.

## Last Validation

2026-06-02: uv run pytest tests/unit/ → 472 passed. make lint → exit 0. make typecheck → exit 0. P9-B0 complete.

## Blockers

None.
