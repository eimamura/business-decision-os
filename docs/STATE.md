# Execution State

Orchestrator-only write. Specialists do not write to this file.
TASKS.md holds task definitions. This file holds runtime execution state.

---

## Current Phase

M11 Complete — Phase 11 Single-Page Chat Shell

## Active Lease

None

## Last Completed Batch

Phase 11 — M11 Complete (T-11001 through T-11003) — 2026-05-20

## Last Validation

command: `cd apps/web && npx tsc --noEmit && cd ../.. && uv run pytest tests/unit/ -q`
exit code: 0 (all pass)
timestamp: 2026-05-20
note: 206 unit tests PASS. M11 complete: T-11001 — ChatSidebar component extracted; T-11002 — /chat page rewritten as single-page shell with empty state; T-11003 — /chat/[sessionId] refactored to use ChatSidebar. tsc: 0 errors.: T-10001 — Alembic migration 0002 (session_messages + rate_limit_counters tables); T-10002 — DecisionSessionRepository + LlmUsageRepository implemented (no stubs), packages/state/db.py pool factory, real usage_writer wired in state.py; T-10003 — packages/agent/history.py compress_history() with SUMMARY_THRESHOLD=30, integrated into sessions.py post_message; T-10004 — packages/agent/rate_limiter.py per-user+global rate limiting, integrated into sessions.py; T-10005 — PATCH /api/v1/sessions/{sid}/messages/{mid}/feedback endpoint, GET messages returns feedback field; T-10006 — apps/web/types/chat.ts + apps/web/lib/api.ts typed API client with streamSession generator; T-10007 — apps/web/hooks/useChat.ts SSE streaming hook, page.tsx refactored (EventSource removed); T-10008 — apps/web/components/MessageBubble.tsx with react-syntax-highlighter (ssr:false), 👍👎 feedback UI; T-10009 — ReasoningPanel updated with SessionUsage props, Input/Output/cost token display. lint: 0 errors. typecheck: 0 errors. tsc: 0 errors.

## Blockers

None

## Scope Violations

None

---

## Field Definitions

| Field | Purpose |
|---|---|
| **Active Lease** | Batch ID currently being executed (e.g. `B01`). Set at turn start, cleared at turn end. Prevents concurrent writes if harness is re-entered mid-batch. |
| **Last Completed Batch** | Most recently finished batch ID + name. Used as re-entry point when `/goal` resumes. |
| **Last Validation** | Command run, exit code, and timestamp from the most recent Test/Review check. |
| **Blockers** | Structured blocker entries. Format: `B<batch>: <description>`. Cleared when resolved. |
| **Scope Violations** | Any out-of-scope action detected by Test/Review (e.g. specialist touching Phase 2 tasks). |

## Update Protocol

Orchestrator updates this file at the **end of every turn**, in this order:

1. Clear `Active Lease`
2. Set `Last Completed Batch`
3. Set `Last Validation` (from Test/Review output)
4. Update `Blockers` (add or remove)
5. Update `Scope Violations` if any

Orchestrator sets `Active Lease` at the **start of every turn** before spawning a specialist.
