# ADR: AskUser interrupt()-based Information Gathering

**Date:** 2026-06-03
**Status:** Accepted
**Supersedes:** DECISIONS.md entry 2026-06-03 "Replace clarification flow with proactive AskUser mechanism" (P11 design)

---

## Context

P11 introduced `AskUser`: when intent is classified as analytical and a critical parameter
is absent, `_node_ask_user` makes one LLM call and, if `needs_input=true`, emits an
`ask_user_required` SSE event and **completes the session** with the question as `reply`.
The user's answer arrives in the next request via `conversation_context`. A second LLM call
in `_node_ask_user` reads `conversation_context` to decide whether the question was already
answered and to skip asking again.

Three problems with this design were identified:

1. **Fragile answer detection.** The second LLM call must correctly infer "the user answered
   in this conversation_context" from free text. Misreads cause the question to repeat
   indefinitely.

2. **No state preservation.** Completing the session discards the intent classification
   result. The next `run()` call re-classifies intent from scratch, adding latency and cost.

3. **Not extensible to mid-execution.** If a specialist agent running inside the DAG needs
   to ask a clarifying question, the soft-completion model cannot pause mid-graph. A
   principled pause/resume mechanism is needed for that extension.

---

## Candidates Considered

### Option A — Keep soft-completion, fix answer detection with a state flag

Replace the LLM-based "was this answered?" check with a `ask_user_pending: bool` column
in `decision_sessions`. The second request flips the flag; no LLM call needed.

Rejected: still discards intent state; still not extensible to mid-execution. Adds a DB
column migration for a mechanism that will be replaced again in P14.

### Option B — LangGraph `interrupt()` (chosen)

Split `_node_ask_user` into:
- `prepare_ask_user` — LLM call, SSE emission (side effects allowed before `interrupt()`)
- `wait_for_answer` — calls `interrupt({"ask_user_id": ..., "question": ...})`; zero DB writes

The graph is checkpointed at `wait_for_answer`. A new `POST /sessions/{id}/answer` endpoint
calls `orchestrator.answer_ask_user(session_id, answer)` which resumes the graph via
`graph.astream(Command(resume={"answer": answer}), ...)`. The answer is injected directly
into graph state; no LLM call needed to detect it.

### Option C — New session on each answer round

Each question-answer pair creates a new session. Sessions are linked via `parent_session_id`.

Rejected: breaks the chat UX (users expect one session per conversation); requires frontend
changes to track lineage; no improvement on state preservation.

---

## Decision

Adopt **Option B**. Migrate `_node_ask_user` to the `prepare_ask_user` + `wait_for_answer`
two-node pattern using LangGraph `interrupt()`. Add `answer_ask_user(session_id, answer)`
to the `Orchestrator` Protocol.

---

## Rationale

- **Typed answer injection.** `Command(resume={"answer": "..."})` delivers the answer
  directly into graph state. No LLM interpretation needed.
- **Intent state preserved.** `classify_intent` ran in the first invocation; when the
  graph resumes, it continues from `wait_for_answer` → `select_mode` without re-running
  intent classification.
- **Consistent with existing HITL pattern.** `wait_for_approval` (T-066) uses the same
  `interrupt()` idiom. `answer_ask_user()` is structurally parallel to `resume()`.
- **Foundation for mid-execution ask_user (P14).** Once the pattern is established at the
  orchestrator level, specialist agents inside `AgentRuntime` can call `interrupt()` within
  the graph to request input mid-DAG.

---

## Consequences

### Interface change

`Orchestrator` Protocol gains a new method:

```python
async def answer_ask_user(self, session_id: UUID, answer: str) -> SessionResponse: ...
```

All implementations (`SessionOrchestrator`) must implement this method.

### interrupt() isolation rule (inherited from P9 ADR)

`wait_for_answer` must contain **zero DB side effects**. All writes (`approvals`, status
updates, SSE events) must happen in `prepare_ask_user` before `interrupt()` is reached.
On resume, `wait_for_answer` only unpacks the resume value and returns `{"ask_user_answer": answer}`.

### Schema changes

`AskUserRequiredEvent` gains `ask_user_id: str` and `suggestions: list[str]` fields.
`OrchestratorState` gains `ask_user_id`, `ask_user_question`, and `ask_user_answer` fields.
`make codegen` must be run after `sse_events.py` changes.

### P14 scope

Specialist-level (mid-execution) `ask_user` — where a running agent requests input during
DAG execution — is explicitly out of scope for P13 and will be addressed in P14. The graph
node pattern established here provides the extension point.

### Soft-completion tests (T-089)

The T-089 two-request flow unit tests become obsolete once T-092 removes `_node_ask_user`
and `_edge_after_ask_user`. Delete T-089 tests after T-092 lands; rely on T-096 instead.

---

## Implementation

Tracked as P13: T-090 (this ADR), T-091–T-097 (backend + frontend), T-098–T-099 (suggestions).
