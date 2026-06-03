# ADR: LangGraph Migration

**Date:** 2026-06-02  
**Status:** Accepted  
**Supersedes:** DECISIONS.md entry 2026-06-02 "Do not adopt LangGraph at this time"

---

## Context

The prior decision (2026-06-02) deferred LangGraph adoption because domain logic was
incomplete and public interface changes would have created unacceptable scope risk.
That condition no longer holds: P1–P8 are complete, domain logic is stable, and the
`LLMClient`, `Tool`, `Orchestrator`, and `Specialist` Protocols are locked.

Two requirements are now confirmed as inevitable:

1. **Session resumption** — users must be able to reload the browser mid-session and
   continue from where the agent paused (e.g., after a HITL approval or a long-running job).
2. **Complex orchestration** — the `SessionOrchestrator` already implements 5 execution
   modes (direct_chat, single_agent, sequential_agents, planned_execution, dag_execution)
   with DAG dependency resolution, conditional branching, and HITL pause/resume. The
   current `HITLPause` exception and manual `while remaining` DAG loop are effectively
   a hand-rolled graph; a framework-level representation is warranted.

---

## Candidates Considered

### Option A — LangGraph standard checkpointer (chosen)

Use `langgraph-checkpoint-postgres` as the single source of truth for agent execution
state. The existing `approvals` and `agent_steps` tables are retained as **audit logs**
only; they are no longer queried to drive execution control.

### Option B — Custom Postgres checkpointer

Wrap `ApprovalsRepository` in a custom LangGraph `BaseCheckpointSaver` so that existing
DB tables remain the execution state source of truth.

Rejected: significant implementation surface, high coupling between LangGraph internals
and the application schema, and the main benefit (familiarity of existing SQL) does not
outweigh the maintenance burden.

---

## Decision

Adopt **Option A**. LangGraph with `langgraph-checkpoint-postgres` becomes the execution
state layer for `AgentRuntime` and `SessionOrchestrator`. The `approvals` and `jobs`
tables are written for audit and UI display but are not polled to gate execution resumption.

---

## Rationale

- **Session resumption is free**: checkpointing is LangGraph's core value proposition;
  implementing equivalent durability on a custom stack would require similar design work.
- **DAG execution fits Send API natively**: the current `asyncio.gather` fan-out in
  `run_dag_execution` is manually what LangGraph's `Send` API provides declaratively.
- **Stable migration surface**: all public Protocols (`LLMClient`, `Tool`, `Orchestrator`,
  `Specialist`) remain unchanged. LangGraph sits inside the `SessionOrchestrator`
  implementation; callers see the same `run()` / `resume()` interface.
- **Timing**: migration cost is lower now (P1–P8 complete, no in-flight phase work) than
  it would be once multi-Specialist conditional branching or long-session UX requirements
  land mid-phase.

---

## Trade-offs

| Benefit | Cost |
|---|---|
| Session resumption via checkpoints | `approvals` table is no longer the live execution state; must query LangGraph API for "who is paused" |
| DAG parallelism via Send API | `asyncio.Queue` (SSE) cannot be in graph state; must be injected via DI |
| Graph-level observability (node history) | LangGraph breaking-change history; version upgrades require monitoring |
| Cleaner HITL model via `interrupt()` | Nodes with `interrupt()` must never write to DB (re-run-on-resume risk) |
| 3-block prompt caching preserved | Must be hand-coded inside `call_model` node; LangGraph does not manage it |

---

## Mandatory Implementation Rule: interrupt() Node Isolation

LangGraph re-executes a node from its beginning when the graph resumes after `interrupt()`.
Any DB write inside an interrupt node will execute **twice** — once when pausing, once when
resuming.

**Rule**: nodes that call `interrupt()` must contain zero side effects. All side-effecting
work (DB writes for `approvals`, `jobs`) must happen in a **preceding node** whose output
is persisted in the checkpoint before `interrupt()` is reached.

Correct pattern:

```
prepare_hitl node   → writes approvals + jobs rows, stores approval_id in graph state
                      (this node is checkpointed; it will NOT re-run on resume)
        ↓
wait_for_approval   → calls interrupt() only; reads approval_id from state
        ↓
execute_tool node   → runs the approved tool
```

This rule must be documented in CLAUDE.md and enforced in code review.

---

## Affected Components

| Component | Change type |
|---|---|
| `packages/agent/runtime.py` | Full rewrite as `StateGraph` |
| `packages/agent/orchestrator/session_orchestrator.py` | Execution routing → `StateGraph` |
| `packages/agent/orchestrator/hitl.py` | `HITLPause` removed; `interrupt()` pattern |
| `packages/agent/orchestrator/planning.py` | `run_dag_execution` → `Send` API |
| `packages/persistence/approvals_repo.py` | Demoted to audit log; no longer drives resume |
| `apps/api/routers/approvals.py` | `PATCH` triggers LangGraph graph resume |
| Frontend SSE handler | Maps LangGraph custom stream events to existing UI types |
| `pyproject.toml` | Add `langgraph==1.2.4`, `langgraph-checkpoint-postgres` |
| DB migration | `langgraph_checkpoints` table (auto-created by LangGraph) |

---

## Reversibility / Re-evaluation Triggers

- If LangGraph introduces a breaking API change that requires > 2 days of migration work,
  evaluate whether to pin the current version or return to a custom runtime.
- If the `approvals` table observability loss causes operational problems (e.g., on-call
  cannot query pending approvals without LangGraph API), implement a read-through view
  that queries the checkpoint store and projects `approvals`-shaped rows.
