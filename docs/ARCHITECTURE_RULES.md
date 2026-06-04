# ARCHITECTURE_RULES.md

## Purpose

Define what each layer MAY and MUST NOT do.
These rules are the enforcement complement to DESIGN.md's structural description.
When a code review or arch test fails, this file is the authoritative source.

---

## Rule format

Each rule uses one of:
- `MAY` — explicitly permitted (resolves ambiguity)
- `MUST` — required
- `MUST NOT` — forbidden; violation is a defect, not a style issue

---

## Orchestration Layer

**`packages/agent/orchestrator/`**

- Orchestrator MAY route, plan, aggregate results, detect conflicts, score decisions, and generate responses.
- Orchestrator MUST receive user-facing work as `SessionUserQuery` and return `SessionResponse`; `SessionGoal` is internal and only used when a clear decision or analytical goal exists.
- Orchestrator MUST delegate specialized domain analysis to Domain Agents or Analytical Agents.
- Orchestrator MUST NOT own domain-specific calculations, supply chain thresholds, or business rules.
- Orchestrator MUST NOT call the database directly; data access goes through Tools.
- Orchestrator MUST NOT call the LLM provider SDK directly; all LLM calls go through `packages/agent/llm/`.

---

## Agent Layer — Domain Agents

**`packages/agent/specialists/` — domain-scoped agents (demand, inventory, replenishment, procurement, supplier, production, logistics)**

- Domain Agents MAY reason over their domain context and invoke Tools to retrieve data or run calculations.
- Domain Agents MAY hold domain-specific business rules as reasoning input (not as executable code).
- Domain Agents MUST NOT implement data access directly; all reads go through Tool Layer.
- Domain Agents MUST NOT route requests between agents or aggregate multi-domain results.
- Domain Agents MUST NOT call the LLM provider SDK directly.

---

## Agent Layer — Analytical Agents

**`packages/agent/specialists/` — cross-domain agents (exception, scenario, ranking, root_cause)**

- Analytical Agents MAY operate across domain boundaries by invoking Tools.
- Analytical Agents MUST NOT own domain-specific business rules; they consume domain data, not domain logic.
- Analytical Agents MUST NOT route or aggregate in a way that duplicates Orchestrator responsibilities.

---

## Tool Layer

**`packages/tools/`**

- Tools MAY execute data access, calculations, external API calls, simulations, and audit writes.
- Tools MUST expose a clear input/output schema conforming to the `Tool` base class in `packages/tools/base.py`.
- Tools MUST raise `RuntimeError` on missing configuration (API keys, DB connection); never silently degrade to a no-op or stub.
- Tools MUST NOT decide business strategy or routing; they are execution primitives, not decision-makers.
- Tools MUST NOT route requests between agents.
- Tools MUST NOT bypass `LLMClient` to call the provider SDK directly.

---

## Memory Layer

**`packages/memory/`**

- Memory MUST be accessed through typed store classes: `ShortTermMemory`, `WorkingMemory`, `LongTermMemory`, `DecisionMemory`, `UserMemory`, `DomainMemory`.
- Agents MUST NOT pass raw dicts as "memory" between components; use the Memory Layer API.
- Agents MUST NOT read or write memory belonging to another agent's domain without going through the Memory Layer API.
- Memory MUST NOT be used solely as raw conversation history; it holds state, context, and decision records.

---

## Guardrail Layer

- All external actions (database writes with business impact, notifications, approval requests) MUST pass through Guardrail before execution.
- Guardrail logic MUST NOT be scattered as ad-hoc `if permission` or `if approval` checks inside Agent or Tool code.
- Guardrail MUST expose a stable API: `can_execute()`, `needs_approval()`, `audit_required()`.
- Agents MUST surface low-confidence or high-risk decisions to Guardrail; never silently degrade or self-approve.
- Approval rows in terminal states (`approved`, `rejected`, `needs_revision`, `expired`) MUST NOT be mutated by any layer.

### SQL Read Guardrail

- `SqlQueryTool` and `NlQueryTool` MUST validate SQL through `packages/tools/sql_guardrail.py:validate_read_sql()` before calling any persistence repository function.
- SQL read guardrail policy MUST stay in the Tool Layer. `packages/persistence/` executes validated queries and MUST NOT become the policy owner for table allowlisting or SQL safety.
- User- or LLM-provided SQL MUST be a single `SELECT` statement, reference at least one allowlisted table, and avoid non-read operations or dangerous database features.
- SQL guardrail tests MUST cover direct SQL, generated SQL, quoted identifiers, schema-qualified names, joins, comma joins, CTEs, subqueries, and `UNION` references.

---

## Cross-cutting Rules

These apply everywhere, regardless of layer:

| Rule | Rationale |
|------|-----------|
| Only `packages/agent/llm/` may call the LLM provider SDK | Centralizes rate limiting, cost tracking, and failover |
| Only `packages/tools/` and `packages/persistence/` may hold SQLAlchemy models or execute queries | Prevents hidden data access paths |
| `data/sample/ground_truth/` MUST NOT be read by any agent or tool | Test-data isolation |
| Public interfaces (`LLMClient`, `Tool`, `JobRunner`, `MemoryStore`, `Orchestrator`, `Specialist`) MUST NOT change without an ADR | Preserves integration contracts |
| Orchestrator interface changes are governed by `docs/adr/2026-05-21-user-query-orchestrator-flow.md` | Records the accepted `SessionUserQuery` → `SessionResponse` flow |
| No smart stubs: stubs MUST conform to schema, not approximate real behavior | Prevents false-passing tests |
| No fail-silent fallbacks: missing config raises `RuntimeError` at the call site | Prevents silent degradation in production |

---

## API Behavioral Contracts

Behaviors that must survive every refactoring phase. If a change would break one of these,
file an ADR before proceeding.

### HTTP API Routes

| Route | Method | Guaranteed behavior |
|---|---|---|
| `/healthz` | GET | 200 `{"status": "ok"}` |
| `/readyz` | GET | 200 when DB reachable; 503 when not |
| `POST /api/v1/sessions` | POST | Creates session; returns `session_id` (UUID, stable across restarts) |
| `GET /api/v1/sessions` | GET | Returns list of sessions for caller |
| `GET /api/v1/sessions/{session_id}` | GET | Returns session or 404 |
| `DELETE /api/v1/sessions/{session_id}` | DELETE | 204; cascades to messages |
| `GET /api/v1/sessions/{session_id}/messages` | GET | Returns ordered message list |
| `POST /api/v1/sessions/{session_id}/messages` | POST | Enqueues user message; returns job handle |
| `GET /api/v1/sessions/{session_id}/stream` | GET | SSE stream (see `packages/schemas/sse_events.py`) |
| `POST /api/v1/sessions/{session_id}/messages/{message_id}/answer` | POST | Submits AskUser answer; resumes orchestrator |
| `POST /api/v1/decisions` | POST | Triggers async decision job; returns `job_id` |
| `GET /api/v1/decisions/{job_id}/status` | GET | Returns job status; never blocks |
| `GET /api/v1/approvals/{approval_id}` | GET | Returns approval or 404 |
| `POST /api/v1/approvals/{approval_id}/decision` | POST | Applies state transition; 422 on illegal transitions |

### Auth Contracts

| Condition | Behavior |
|---|---|
| `APP_ENV=dev` | `user_id` is `None`; all routes accessible without token |
| `APP_ENV != dev` | Auth middleware enforces identity; unauth → 401 |

- Missing/invalid credentials → **401** (not 403, not 200)
- Insufficient permissions → **403**
- These codes MUST NOT be swapped during refactoring.

### Error Contracts

| Situation | Required behavior |
|---|---|
| Request validation failure | 422 (FastAPI default; MUST NOT change to 400) |
| Internal / unexpected error | 500 with error envelope; never silent 200 with error in body |
| Missing `ANTHROPIC_API_KEY` | `RuntimeError` at call site; never stub or no-op |
| Missing external service config | `RuntimeError` at call site; never silently degrade |
| Illegal approval state transition | 422 |

### Persistence Contracts

The following data MUST survive a service restart:

| Entity | Repository | Guarantee |
|---|---|---|
| Sessions | `persistence.sessions_repo` | `session_id` stable; messages preserved |
| Approvals | `persistence.approvals_repo` | Status and all transitions preserved |
| Audit log | `persistence.audit_log_repo` | Append-only; no rows ever deleted |
| LLM usage | `persistence.llm_usage_repo` | Cost/token records preserved |

Approval state machine (enforced at domain layer, not just DB):

```
pending → approved | rejected | needs_revision | expired
approved / rejected / needs_revision / expired → (terminal — no further transitions)
```

### SSE Stream Contract

The SSE event schema is the code: `packages/schemas/sse_events.py` is SSoT.

**Guaranteed invariants (independent of event type):**
- Every stream ends with `done` or `error` — never silently terminates mid-sequence.
- `done.reply` is always populated with the final user-facing text.

---

## What These Rules Do NOT Govern

- Internal naming conventions within a file (style guide concern)
- Number of files or classes within a layer (implementation detail)
- Test structure (see `.claude/rules/testing.md`; How-to: `docs/TESTING.md`)
- Migration order (see archive/v2/MIGRATION_PLAN.md — archived)
- Which decisions are deferred (see archive/v2/DEFERRED.md — archived)
