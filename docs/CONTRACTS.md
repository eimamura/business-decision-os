# CONTRACTS.md

## Purpose

Define external behavior that must survive every refactoring phase.
These contracts are not aspirational — they describe the current system's guaranteed behavior.
If a refactoring phase would break a contract here, it must be explicitly negotiated and this file updated first.

This document is the input to Phase 0 of MIGRATION_PLAN.md.
Every item here should have a corresponding contract test in `tests/`.

---

## API Contracts

### Health

| Route | Method | Guaranteed response |
|-------|--------|-------------------|
| `/healthz` | GET | 200 `{"status": "ok"}` |
| `/readyz` | GET | 200 when DB is reachable; 503 when not |

### Sessions (`/api/v1/sessions`)

| Route | Method | Guaranteed behavior |
|-------|--------|-------------------|
| `POST /api/v1/sessions` | POST | Creates a session; returns `session_id` (UUID, stable across restarts) |
| `GET /api/v1/sessions` | GET | Returns list of sessions for caller |
| `GET /api/v1/sessions/{session_id}` | GET | Returns session or 404 |
| `DELETE /api/v1/sessions/{session_id}` | DELETE | 204 on success; cascades to messages |
| `GET /api/v1/sessions/{session_id}/messages` | GET | Returns ordered message list |
| `POST /api/v1/sessions/{session_id}/messages` | POST | Enqueues a user message; returns job handle |
| `PATCH /api/v1/sessions/{session_id}/messages/{message_id}/feedback` | PATCH | 204; records feedback without altering message content |
| `GET /api/v1/sessions/{session_id}/stream` | GET | SSE stream; emits typed events (see SSE Events below) |

### Decisions (`/api/v1/decisions`)

| Route | Method | Guaranteed behavior |
|-------|--------|-------------------|
| `POST /api/v1/decisions` | POST | Triggers async decision job; returns `job_id` |
| `GET /api/v1/decisions/{job_id}/status` | GET | Returns job status; never blocks |

### Recommendations (`/api/v1`)

| Route | Method | Guaranteed behavior |
|-------|--------|-------------------|
| `GET /api/v1/recommendations/{recommendation_id}` | GET | Returns recommendation with `reasoning` field populated |
| `GET /api/v1/sessions/{session_id}/recommendations` | GET | Returns recommendations scoped to session |

### Approvals (`/api/v1/approvals`)

| Route | Method | Guaranteed behavior |
|-------|--------|-------------------|
| `GET /api/v1/approvals` | GET | Returns list of approvals |
| `GET /api/v1/approvals/{approval_id}` | GET | Returns approval or 404 |
| `POST /api/v1/approvals/{approval_id}/decision` | POST | Applies a status transition; rejects illegal transitions with 422 |
| `POST /api/v1/approvals` | POST | Creates a new approval in `pending` state |

**Approval state machine** (enforced at domain layer, not just DB):

```
pending → approved | rejected | needs_revision | expired
approved → (terminal — no further transitions)
rejected → (terminal)
needs_revision → (terminal)
expired → (terminal)
```

Any attempt to transition a terminal-state approval raises 422.

### Audit (`/api/v1/audit`)

| Route | Method | Guaranteed behavior |
|-------|--------|-------------------|
| `GET /api/v1/audit` | GET | Returns audit log entries |

Audit log is append-only. No delete endpoint is exposed at any route.

### Scenarios, KPI, Notifications, Policies, Settings

| Route prefix | Guaranteed behavior |
|---|---|
| `GET /api/v1/sessions/{session_id}/scenarios` | Returns scenarios scoped to session |
| `GET /api/v1/scenarios/{scenario_id}` | Returns scenario or 404 |
| `GET /api/v1/kpi/trends` | Returns KPI trend data |
| `GET /api/v1/kpi/llm-cost` | Returns LLM cost aggregates |
| `GET /api/v1/notifications` | Returns notifications list |
| `GET /api/v1/policies` | Returns current policies |
| `PUT /api/v1/policies` | Replaces policies; returns updated policies |
| `GET /api/v1/settings/budgets` | Returns budget settings |
| `PATCH /api/v1/settings/budgets` | Partial-updates budget settings |
| `GET /api/v1/settings/weights` | Returns scoring weights |
| `PATCH /api/v1/settings/weights` | Partial-updates scoring weights |

---

## SSE Event Contracts

The `/api/v1/sessions/{session_id}/stream` endpoint emits a sequence of typed events.
The event schema is defined in `packages/schemas/sse_events.py`.

**Guaranteed event types and their invariants:**

| Event type | Invariant |
|---|---|
| `tool_called` | Emitted before tool execution begins |
| `tool_completed` | Emitted after tool execution; `executed_query` field is populated for SQL tools |
| `recommendation_ready` | Emitted when a recommendation is ready; includes `risk_level` and `requires_approval` |
| `awaiting_approval` | Emitted when approval is required before execution; includes `approval_id` |
| `error` | Emitted on recoverable or fatal errors; never silently swallowed |
| `done` | Always the final event in a stream; includes `reply` |

**Guaranteed stream termination**: every stream ends with either `done` or `error`. A stream never terminates silently mid-sequence.

---

## Auth Contracts

The current auth model is `DevUserMiddleware` (see `apps/api/middleware.py`).

| Condition | Behavior |
|---|---|
| `APP_ENV=dev` | `user_id` is set to `None`; all routes accessible without a token |
| `APP_ENV != dev` | Auth middleware enforces identity; unauth requests → 401 |

Auth response codes:
- Missing or invalid credentials → **401** (not 403, not 200)
- Insufficient permissions → **403**

These codes must not be swapped during refactoring.

---

## Persistence Contracts

The following data survives a service restart:

| Entity | Persisted in | Guarantee |
|---|---|---|
| Sessions | `state.sessions_repo` | session_id stable; messages preserved |
| Approvals | `state.approvals_repo` | status and all transitions preserved |
| Audit log | `state.audit_log_repo` | append-only; no rows ever deleted |
| Tool calls | `state.tool_calls_repo` | historical record preserved |
| LLM usage | `state.llm_usage_repo` | cost/token records preserved |
| Notifications | `state.notifications_repo` | delivery state preserved |

**Approval immutability**: approval rows in a terminal state (`approved`, `rejected`, `needs_revision`, `expired`) must not be mutated. This is enforced at the domain layer (`packages/persistence/approvals.py`), not just by convention.

---

## User-Visible Flow Contracts

These are the behaviors a user can observe. They must not regress.

1. User sends a message → receives a streaming response via SSE
2. Tool executions are visible in the chat stream (`tool_called`, `tool_completed` events)
3. The SQL query executed by NlQueryTool/SqlQueryTool is shown in the chat (`executed_query` field on `tool_completed`)
4. Recommendations appear in the chat stream (`recommendation_ready` event) and are retrievable via `/api/v1/recommendations/{id}`
5. Approvals requiring human action surface as `awaiting_approval` events with a stable `approval_id`
6. Every message flow ends with a `done` event; users never see a stream that hangs indefinitely

---

## Error Contracts

| Situation | Required behavior |
|---|---|
| Request validation failure | 422 (FastAPI default; must not be changed to 400) |
| Internal / unexpected error | 500 with error envelope; never a silent 200 with error buried in body |
| Missing LLM config (ANTHROPIC_API_KEY not set) | `RuntimeError` raised at call site; never a silent stub or no-op |
| Missing external service config | `RuntimeError` at call site; never silently degrade |
| Illegal approval state transition | 422 |

---

## Out of Scope for This Document

The following are intentionally NOT contracted here:

- Internal module structure, class names, file layout
- Agent routing decisions (which specialist handles a request)
- LLM response content or quality
- Performance SLAs or response time targets
- Database schema column details (beyond what is documented in persistence contracts)

These are internal concerns that refactoring is allowed to change freely.
