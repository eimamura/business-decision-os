---
paths:
  - "packages/agent/**"
  - "packages/tools/**"
  - "packages/persistence/**"
  - "packages/schemas/**"
---
# Design Contract Watch List

Count=1 failure patterns with high recurrence risk in these packages.
SSoT: `docs/failure-patterns.md`. This file is a non-authoritative reminder — if it conflicts with `docs/failure-patterns.md`, the latter wins.

## FP-004 — Shared stub infrastructure (packages/agent/, packages/tools/)

When fixing a defect, do NOT duplicate test-stub infrastructure. If a second stub implementation diverges from the first, schema changes to one will silently break tests against the other.
**Check:** is there already a stub for this component? Extend it; do not copy it.

## FP-007 — Symmetric session lifecycle teardown (packages/agent/)

Every state store that is written on session CREATE must be torn down on session DELETE. If you add a new store (in-memory dict, task handle, broadcaster slot), verify that the delete path also removes it.
**Check:** after adding a store write in session creation, grep for the store reference in the delete handler.

## FP-008 — Blocked-path handling must not share the hard-failure path (packages/agent/)

Soft blocks (guardrail verdicts, verifier rejections) must use a distinct code path from hard failures (unhandled exceptions). Reusing `raise`/500-path for soft blocks misreports the block reason and discards the prepared fallback text.
**Check:** does the blocked condition set its own reason string and reach the soft-fallback branch?

## FP-010 — Lazy-resolving collections must hook ALL access paths (packages/tools/)

A lazy dict/mapping that overrides only `__getitem__` and `.get` leaves `.items()`, `.values()`, and `len()` delegating to the empty base. Any consumer that iterates (registry `get_registry`, tool discovery) will see an empty result until a `__getitem__` call has primed the cache.
**Check:** if your class overrides `__getitem__`, also override `__iter__`, `__len__`, `.items()`, `.values()`, `.keys()`.

## FP-016 — New FKs to `decision_sessions` must carry `ON DELETE CASCADE` (packages/persistence/)

Migration 0003 established a cascade convention for all session-child tables. Any new FK pointing at `decision_sessions(id)` must include `ON DELETE CASCADE`. Missing CASCADE forces caller code to manually delete child rows before deleting the session, leaking that responsibility outside the schema.
**Check:** does the new FK reference `decision_sessions(id) ON DELETE CASCADE`?

## FP-013 — SSE streaming protocol must include retraction semantics (packages/schemas/, packages/agent/)

The SSE protocol is append-only by default: once text is streamed, the client cannot distinguish a corrected second-invocation reply from the original degenerate text. When a second agent invocation produces a grounded reply, both segments appear sequentially with no signal to the client to discard the earlier one.
**Check:** if a new flow can trigger a second agent invocation that replaces earlier streamed content, add a `text_reset` event type (or equivalent retraction signal) to `packages/schemas/sse_events.py` before streaming the corrected segment.

## FP-014 — Language constraint must be enforced at every LLM output site (packages/agent/)

The English-only constraint was specified at the UI display boundary but not propagated to upstream LLM node prompts (set_goal, evaluate_goal). When those nodes produce non-English output, the strings flow into the control agent's context and leak into user-facing replies.
**Check:** every new or modified LangGraph node that produces text for the control agent's context or for user-visible output must include an explicit English-only instruction in its prompt.
