# TASKS.md

## Goal

Eliminate AGENTS.md prohibited violations, fix the three critical design gaps
identified in the 2026-06-02 evaluation, and adopt low-cost patterns from reference
projects that improve correctness without changing public interfaces.

---

## P0 — Prohibited Violation (fix before any other work)

### T-001: Remove stub candidate fallback in `_rank_candidates` — **Done**
- **File:** `packages/agent/orchestrator/decision.py`
- **What:** Delete the `else` branch (~lines 106–116) that synthesizes 3 fake candidates
  when `simulation_optimizer` returns nothing. Replace with an explicit error or an
  empty `SessionResponse` with a `reply` explaining that no candidates were generated.
- **Rule violated:** AGENTS.md "smart stubs that approximate real behavior"
- **Test:** Unit test that `_rank_candidates([])` raises or returns a defined empty state,
  not synthetic MOQ-multiple candidates.

---

## P1 — Critical Design Gaps

### T-002: Fix DAG parallel execution — **Done**
- **File:** `packages/agent/orchestrator/planning.py` — `run_dag_execution()`
- **What:** Replace sequential `for node in ready: await _run_agent(...)` with
  `await asyncio.gather(*[_run_agent(...) for node in ready])`.
  Merge results from all concurrent nodes before proceeding.
- **Test:** Unit test with a mock `_run_agent` confirming that two dependency-free
  nodes are launched concurrently.

### T-003: Replace fake embeddings with real embedding API — **Done**
- **File:** `packages/memory/__init__.py`
- **What:** Delete `_make_embedding()`. Replace with a real embedding call
  (Anthropic or OpenAI). Requires an ADR before changing `MemoryStore`
  public interface (embedding dimension changes from 192 to 1536/3072).
- **ADR required:** Yes — embedding model selection + MemoryStore interface impact.
- **ADR written:** `docs/ADR/2026-06-02-embedding-model.md` — OpenAI `text-embedding-3-small` selected.
- **Implementation done:** `_make_embedding()` deleted; `_get_embedding()` added using OpenAI SDK;
  `PgVectorMemoryStore.write()` and `.search()` updated; `openai>=1.0.0` added to `packages/memory/pyproject.toml`;
  migration `0010_memories_vector_1536.py` created as named checkpoint.
- **Pending:** Integration test (Test/Review owned) — write a Memory, search with semantically similar query,
  confirm similarity > 0.7.
- **Test:** Integration test: write a Memory, search with a semantically similar query,
  confirm similarity > 0.7.

### T-004: Strengthen Guardrail risk classification — **Done**
- **File:** `packages/tools/guardrail.py`
- **What:**
  - `classify_risk()`: incorporate multiple KPI dimensions beyond `service_level`
    (e.g. `total_supply_chain_cost`, `stockout_rate`). Define thresholds in a config
    dict, not inline comparisons.
  - `_resolve_role()`: replace hardcoded user ID list with a DB lookup via
    `packages/persistence/` repository layer.
- **Test:** Parametrize unit tests over KPI combinations; test that DB-backed role
  lookup returns correct role for known users.

### T-005: Persist session state to database — **Done**
- **Files:** `packages/agent/orchestrator/session_orchestrator.py`,
  `packages/persistence/sessions_repo.py`
- **What:** Replace `self._sessions: dict[UUID, dict] = {}` with DB writes.
  Status transitions: `active` → `awaiting_approval` / `completed` / `failed`.
  Use an existing or new sessions repository in `packages/persistence/`.
- **Test:** Unit tests in `tests/unit/test_session_orchestrator_persistence.py`
  verify status transitions with a mocked repository.

---

## P2 — Architecture Improvements (no public interface changes)

### T-006: Extract domain logic from `_role_aware_output_builder` — **Done**
- **File:** `packages/agent/runtime.py`
- **What:** Remove the `if role == "simulation_optimizer"` / `if role == "data_engineer"`
  branches from `AgentRuntime`. Each specialist class should pass a custom
  `output_builder` at construction time or override a `build_output()` method.
  See `packages/agent/cross_domain/simulation_optimizer.py`.
- **Test:** Unit test that `AgentRuntime` with default builder produces `{"text": ...}`,
  and `SimulationOptimizerAgent` produces `{"candidates": [...]}`.

### T-007: Add `verify_findings` step to agent loop — **Done**
- **File:** `packages/agent/runtime.py` — `AgentRuntime.run()`
- **What:** After the tool loop exits, make one additional LLM call with a verifier
  prompt. Check that conclusions are grounded in tool results (not fabricated).
  Status: `pass | needs_revision | blocked`. On `needs_revision`, retry once.
  Pattern reference: `~/projects/agentic-system-mvp/apps/api/agent/nodes/verify_findings.py`.
- **Test:** Unit test with mock LLM returning `needs_revision`; confirm loop retries
  once then produces a final result.

### T-008: Adopt 3-block prompt caching in AgentRuntime — **Done**
- **File:** `packages/agent/runtime.py` — `AgentRuntime.run()`
- **What:** Split the system message into 3 content blocks:
  (1) static base prompt — `cache_control: ephemeral`,
  (2) schema context from `get_schema_context()` — `cache_control: ephemeral`,
  (3) dynamic context (role, tool count, task instruction) — no cache.
  `LLMMessage.content_blocks` (list-of-dicts) is already present in the model.
- **Test:** Unit test confirming the system `LLMMessage` has `content_blocks` with
  3 elements and correct `cache_control` values on the first call.

### T-009: Persist LLM usage to `llm_usage` table — **Done**
- **Files:** `packages/agent/runtime.py`, `packages/persistence/` (new repo)
- **What:** After each `_llm_client.complete()` call in `AgentRuntime`, write
  `(session_id, specialist_role, model, input_tokens, output_tokens, cost_usd, called_at)`
  to a `llm_usage` table. `BudgetGuard` remains for soft/hard limit enforcement;
  the DB write is additive and non-blocking.
- **Test:** Integration test: run one LLM call, verify a row appears in `llm_usage`.

---

## P3 — Domain Depth

### T-010: Differentiate domain agent tool allowlists and system prompts — **Done**
- **Files:** `packages/agent/domain/*.py`, `packages/tools/base.py`
- **What:** Expand `_ROLE_TOOL_ALLOWLIST` for each domain agent beyond
  `["sql_query", "nl_query"]` to include domain-appropriate analytical tools
  (e.g. `demand` gets `forecast`, `train_forecast`; `inventory` gets
  `simulate_inventory`; `replenishment` gets `simulate_inventory`,
  `optimize_replenishment`). Update each agent's `_SYSTEM_PROMPT` with
  domain-specific analysis guidance beyond the current one-liner.
- **Test:** Unit test per domain confirming `list_for_role(role)` returns
  the expected tool set.

### T-011: Add tool DB integration test tier — **Done**
- **File:** `tests/integration/test_tools_real_db.py` (new)
- **What:** Call each tool directly against the real DB with no LLM.
  Confirm correct column names and parameterized queries execute without error.
  Pattern reference: `~/projects/agentic-system-mvp/apps/api/tests/integration/test_tools_real_db.py`.
- **Test:** This IS the test. Run with real DB, no LLM, should complete in under 5 seconds.

---

## P1 — Critical Design Gaps (continued)

### T-012: Add `authorize_user` with DB-backed role lookup — **Done**
- **Files:** `packages/persistence/users_repo.py` (replace existing stub), `apps/api/` (dependency or middleware)
- **Pre-condition:** `packages/persistence/users_repo.py` already exists but is a smart stub that
  returns `"analyst"` for all users — this violates the AGENTS.md smart-stub prohibition. It must
  be replaced with a real DB-backed implementation.
- **What:**
  - New `users` table: `(user_id, role: "analyst"|"manager"|"admin", created_at)` — add migration `0011_users.py`
  - Replace `UserRepository.get_role()` stub body with a real asyncpg query against the `users` table
  - Resolve user role at API request entry and inject as `user_role: str` into `ToolContext`
  - Existing `DevUserMiddleware` stays for dev mode; production uses DB lookup
- **Interface note:** Adding `user_role` to `ToolContext` is used by `Tool.handle()` — all tool
  implementations receive it via context. Ensure `user_role` has a default (`"analyst"`) so existing
  tools remain compatible without changes.
- **Test:** Unit test: known user ID → correct role returned. Unknown ID → default `"analyst"`.

---

## P2 — Architecture Improvements (continued)

### T-018: Classify tools as `read_only` / `write` / `hitl` in ToolRegistry — **Done**
- **File:** `packages/tools/base.py`
- **What:** Add `safety_level: Literal["read_only", "write", "hitl"]` to the `Tool`
  protocol (complements existing `requires_approval: bool`). Add `list_read_only()`
  and `list_hitl_tools()` methods to `ToolRegistry`.
  Pattern reference: `~/projects/agentic-system-mvp/apps/api/shared/types.py::HITL_TOOLS, READ_ONLY_TOOLS`
- **ADR required:** `Tool` public interface change.
- **Test:** Each registered tool has the expected `safety_level`; `list_hitl_tools()`
  returns only HITL tools.

### T-013: Implement 2-layer role × intent tool access control — **Done**
- **Status:** Done
- **Files:** `packages/tools/base.py`, `packages/agent/runtime.py`
- **What:** Add a user-role axis to tool filtering alongside the existing agent-role axis.
  - Layer 1 (user role): `analyst` → read-only tools only; `manager` → includes HITL tools; `admin` → unrestricted
  - Layer 2 (agent role): existing `_ROLE_TOOL_ALLOWLIST` per specialist
  - Effective tools = intersection of both layers
  - `AgentRuntime.run()` reads user role from `ToolContext` and applies Layer 1 filter
- **Depends on:** T-012, T-018 (Layer 1 filtering uses `safety_level` defined in T-018)
- **Test:** Each user role returns the expected intersection of tools from `list_for_role`.

### T-014: Add approval idempotency guard — **Done**
- **Files:** `packages/persistence/approvals_repo.py`, `packages/agent/orchestrator/decision.py`
- **Pre-condition:** `ApprovalsRepository` at `packages/persistence/approvals_repo.py` currently stubs
  all methods with `NotImplementedError("Phase 1 — DB required")`. The repository must have functional
  `create()`, `get()`, and `list()` implementations before idempotency can be layered on top.
  Implement these as part of this task using the existing `approvals` table from migration `0001_initial.py`.
- **What:** Add `get_pending_approval_for_session(session_id) -> Approval | None` to `ApprovalsRepository`.
  Before creating an approval request in `decision.py`, call this method. If a pending record exists,
  reuse it instead of inserting a duplicate.
  Pattern reference: `~/projects/lang-graph-agent-mvp/app/services/approval_service.py::get_pending_approval_for_thread()`
- **Depends on:** T-005 (session persistence — session_id reliably stored before approval records reference it)
- **Test:** Two attempts to create an approval for the same session — second call returns
  the existing record without a new INSERT.

### T-015: Refactor routing into pure functions — **Done**
- **Files:** `packages/agent/orchestrator/routing.py` (new), `packages/agent/orchestrator/session_orchestrator.py`
- **What:** Extract the post-LLM routing decision logic from `select_execution_mode()`
  into pure functions in a new `routing.py` module:
  - `route_after_intent(intent: SessionIntent) -> ExecutionMode`
  - `validate_route(route: AgentRoute) -> None`
  - Pattern reference: `~/projects/lang-graph-agent-mvp/app/graph/edges.py`
  - The LLM call itself stays in `session_orchestrator.py`; only the branching logic moves
- **Test:** Unit tests for `route_after_intent` with no LLM dependency.

### T-016: Adopt IntentRegistry pattern — **Done**
- **Files:** `packages/agent/orchestrator/intent_registry.py` (new),
  `packages/agent/orchestrator/prompts.py`, `packages/agent/runtime.py`
- **What:** Introduce `IntentConfig` dataclass centralizing per-intent settings:
  ```python
  @dataclass
  class IntentConfig:
      description: str
      plan_prompt: str
      allowed_agent_roles: list[str]
      max_tool_calls: int = 10
      skip_tool_loop: bool = False
  ```
  Define `INTENT_REGISTRY` for the 5 existing categories (`chat`, `lookup`,
  `domain_analysis`, `cross_domain_analysis`, `decision_support`). Migrate
  `max_tool_calls` from the global `_MAX_ITERATIONS = 10` constant so each intent
  can have its own limit. Move plan-step guidance from `PLAN_SYSTEM` into each
  `IntentConfig.plan_prompt`.
  Pattern reference: `~/projects/agentic-system-mvp/apps/api/shared/intent_registry.py`
- **Test:** `get_intent_config(category)` returns correct `max_tool_calls` for each intent.

### T-017: Add `result_builder` response structuring — **Done**
- **Files:** `packages/agent/orchestrator/result_builder.py` (new),
  `packages/agent/orchestrator/decision.py`
- **What:** Extract response assembly from `_build_decision_response()` into a
  dedicated `result_builder.py`. `decision.py` handles candidate ranking, risk
  classification, and memory writes only; response formatting is delegated.
  Pattern reference: `~/projects/lang-graph-agent-mvp/app/services/result_builder.py`
- **Test:** `build_response(intent, candidates, risk_level)` returns expected
  structure without LLM calls.

### T-019: Add `ask_clarification` flow for unknown intents — **Done**
- **Files:** `packages/agent/orchestrator/clarification.py` (new),
  `packages/agent/orchestrator/session_orchestrator.py`
- **What:** When intent classification yields `"chat"` with no clear goal, generate
  a clarifying question and emit a `clarification_required` SSE event. On the next
  request, enrich `conversation_context` with the Q&A pair and re-classify. Cap at
  2 clarification rounds; fall back to `direct_chat` on the third unknown.
  Pattern reference: `~/projects/agentic-system-mvp/apps/api/agent/nodes/clarification.py`
  T-026 (HITL) reuses this same clarification mechanism for full pause/resume — implement
  T-019 first so T-026 can extend it rather than duplicate it.
- **Depends on:** T-005 (session persistence — T-005 is Done; documented for clarity)
- **Test:** Unknown intent → `clarification_required` SSE fires. Third consecutive
  unknown → falls through to `direct_chat`.

---

## P3 — Domain Depth (continued)

### T-020: Add prompt integration test tier
- **File:** `tests/integration/test_prompts_mock_llm.py` (new)
- **What:** Run 5–10 representative prompts with a mock LLM and real DB. Confirm
  intent classification, routing, and tool execution behave as expected without
  incurring real LLM API costs.
  Pattern reference: `~/projects/agentic-system-mvp/apps/api/tests/integration/test_prompts_mock_llm.py`
- **Test:** This IS the test. Mock LLM, real DB, zero API cost.

### T-021: Adopt structlog for structured logging
- **Files:** `packages/agent/runtime.py`, `packages/agent/orchestrator/*.py`, `apps/api/`
- **What:** Replace `logging.getLogger(__name__)` with `structlog.get_logger()`.
  Bind `session_id`, `agent_role`, and `tool_name` as structured fields. Configure
  JSON output so logs are consumable by external observability platforms.
- **Test:** Captured stdout log output is valid JSON with the expected fields present.

### T-022: Integrate MLflow tracing
- **File:** `apps/api/app/tracing.py` (new), `apps/api/app/main.py`
- **What:** Add `setup_mlflow_tracing(tracking_uri, experiment_name)` that calls
  `mlflow.langchain.autolog(log_traces=True)`. Read `MLFLOW_TRACKING_URI` from env;
  skip silently (do not raise) when unset.
  Pattern reference: `~/projects/agentic-system-mvp/apps/api/app/tracing.py`
- **Silent-skip rationale:** MLflow is an optional observability service, not a required
  dependency. Silently skipping when `MLFLOW_TRACKING_URI` is absent is intentional and
  does not violate the AGENTS.md "raise RuntimeError for missing config" rule, which applies
  to required env vars only (API keys, database URL, etc.).
- **Test:** App starts without error when `MLFLOW_TRACKING_URI` is set; also starts
  cleanly when the variable is absent.

---

## P3 — UX / Developer Experience

### T-023: Light mode support
- **File:** `apps/web/` (Tailwind config, layout, global CSS)
- **What:** Add light/dark mode toggle to the web UI. Use Tailwind's `dark:` variant
  strategy (`class` mode). Persist preference to `localStorage`. Default to system
  preference via `prefers-color-scheme`. Apply tokens consistently — no hardcoded
  color values outside the design token layer.
- **Test:** Toggle switches `<html class="dark">` on/off; preference survives page reload.

### T-024: Suppress health-check logs in local development
- **File:** `apps/api/app/main.py` (or middleware layer)
- **What:** Add a logging filter that drops access log entries for `GET /health` and
  `GET /api/v1/health` at `INFO` level when `ENV=development`. This prevents the
  Docker health-check poll from flooding local logs. Do not suppress in production or
  staging.
- **Test:** In dev mode, repeated `GET /health` calls produce no access log lines;
  other routes still log normally.

### T-025: Job list — pagination, generated files, and file-centric view
- **Files:** `apps/web/app/jobs/` (page, components), `apps/api/routers/jobs.py` (new)
- **Pre-condition:** No `GET /api/v1/jobs` endpoint or `jobs` router exists in `apps/api/routers/`.
  The router and a `jobs` table (or reuse of the Celery task metadata) must be created as part of
  this task. Also requires a new `job_files` table — add migration `0012_job_files.py`.
- **What:**
  - **Jobs router:** Create `apps/api/routers/jobs.py` with `GET /api/v1/jobs` and `GET /api/v1/jobs/{id}`
  - **Pagination:** Add cursor-based pagination to the `GET /api/v1/jobs` endpoint
    (`?cursor=<job_id>&limit=20`). Render a paginated table in the UI.
  - **Files per job:** Expose `generated_files` list on each job response (file name,
    size, MIME type, download URL). Show inline in the job detail view.
  - **File-centric view:** Add a "Files" tab/toggle on the jobs page that lists all
    generated files across jobs. Each row shows file name, size, created-at, and a
    link back to the source job. Implement as a separate `GET /api/v1/files` endpoint
    backed by the `job_files` table.
- **ADR required:** Only if a new public API resource (`/files`) is added — decide
  whether it warrants a separate router or lives under `/jobs/:id/files`.
- **Test:** Pagination: second page starts after the last item of the first. Files view:
  all files returned are linked to a valid job ID.

---

## P1 — HITL Integration (depends on T-005, T-013, T-014, T-018, T-019)

### T-026: HITL end-to-end flow — **Done**
- **Files:** `packages/agent/orchestrator/session_orchestrator.py`,
  `packages/agent/orchestrator/decision.py`, `apps/api/` (approvals router),
  `apps/web/app/approvals/` (UI)
- **Depends on:** T-005 (session persistence), T-013 (tool access layers),
  T-014 (approval idempotency), T-018 (tool safety levels), T-019 (clarification
  mechanism — T-026 extends the same pause/resume flow rather than duplicating it)
- **What:** Wire the full HITL pause-and-resume loop:
  1. When a `hitl`-classified tool is about to execute, the agent emits
     `awaiting_approval` SSE event and pauses execution (session status → `awaiting_approval`).
  2. A manager or admin user sees the pending approval in the UI (Approvals page),
     reviews the proposed action, and clicks Approve or Reject.
  3. On approval, the session resumes from the paused tool call; on rejection, the
     agent receives a `tool_rejected` signal and generates a fallback response.
  4. Approval records are immutable after close (enforced by T-014 idempotency guard).
  - The `ask_clarification` sub-flow (T-019) uses the same pause/resume mechanism.
- **Test:**
  - Integration: session reaches a HITL tool → status transitions to `awaiting_approval`
    → approve → session completes with tool result.
  - Integration: reject → session produces fallback response without tool output.
  - E2E (Playwright): full approve and reject flows via the Approvals UI.

---

## P3 — UX / Developer Experience (continued)

### T-027: Add copy-to-clipboard button to SQL query bubbles in chat UI
- **File:** `apps/web/components/MessageBubble.tsx` — `SqlQueryBubble`
- **What:** Inside `SqlQueryBubble` (line ~128), add a copy button in the header row
  alongside the existing label (`NL → SQL` / `SQL Query`). On click, write `message.sql`
  to the clipboard via `navigator.clipboard.writeText()`. Show a brief `"Copied!"` 
  confirmation that reverts to the copy icon after 2 seconds.
  - Button: small icon-only (`ClipboardIcon` from `lucide-react` or inline SVG)
  - Position: right side of the `flex` header row (`ml-auto`)
  - State: `"idle" | "copied"` — local `useState`, no external state needed
  - Only render when `message.sql` is present (already guarded by the existing `message.sql &&` check)
- **Test:** Click copy button → `navigator.clipboard.writeText` called with the SQL string.
  Use `userEvent` + mocked clipboard API in a unit test.

### T-028: Fix session list flicker when navigating between sessions
- **Files:** `apps/web/app/chat/[sessionId]/page.tsx`,
  `apps/web/app/chat/layout.tsx` (new)
- **Root cause:** `sessions` state is declared inside `[sessionId]/page.tsx` and
  initialized as `[]` on every mount. When the user clicks a session link, the new page
  mounts with an empty `sessions` array and calls `fetchSessions()`. The sidebar renders
  with zero items until the API response arrives (~100–300 ms), causing a visible flash.
- **Fix:** Extract `sessions` state and `fetchSessions` into a new
  `apps/web/app/chat/layout.tsx` that wraps both `/chat` and `/chat/[sessionId]`.
  Pass sessions and session-mutation callbacks down via props or a React context.
  The layout mounts once per chat section visit; navigating between sessions re-uses
  the already-loaded list without resetting to `[]`.
  - New file: `apps/web/app/chat/layout.tsx` — fetches sessions once, exposes
    `sessions`, `creating`, `onNewSession`, `onDelete` via a `SessionsContext`
  - `[sessionId]/page.tsx` — remove `sessions` state and `fetchSessions` call;
    consume from context instead
  - Keep the title-update callback (`setSessions` inside `useChat`) wired through
    context so optimistic title updates still work
- **Test:** Navigate from one session to another — sidebar session list must not
  disappear or re-render from empty between route changes. Verify with a
  Playwright E2E test: click two sessions in sequence, assert the sidebar item
  count stays constant throughout.

### T-029: Persist left navigation sidebar across all pages
- **Files:**
  - `apps/web/app/(shell)/layout.tsx` (new — route group layout)
  - `apps/web/components/NavSidebar.tsx` (new — nav-only sidebar)
  - `apps/web/app/(shell)/kpi/`, `(shell)/approvals/`, `(shell)/audit/`,
    `(shell)/agents/`, `(shell)/usage/`, `(shell)/settings/` (move existing pages)
  - `apps/web/app/chat/[sessionId]/page.tsx` — remove duplicated nav items from
    `ChatSidebar` (or keep as-is and suppress NavSidebar for chat routes)
- **Root cause:** `ChatSidebar` is rendered only inside `app/chat/[sessionId]/page.tsx`.
  All other pages (`/kpi`, `/approvals`, `/audit`, `/agents`, `/usage`, `/settings`)
  have no sidebar at all, so navigating away from chat causes the sidebar to unmount.
- **Fix using Next.js App Router route groups:**
  1. Extract the `NAV_ITEMS` navigation section from `ChatSidebar` into a standalone
     `NavSidebar` component (no sessions list — navigation links only).
  2. Create `apps/web/app/(shell)/layout.tsx` that renders
     `<NavSidebar /> + {children}` side by side. Route groups do not affect URLs.
  3. Move all non-chat pages into the `(shell)/` group:
     `kpi`, `approvals`, `audit`, `agents`, `usage`, `settings`.
  4. The `chat/[sessionId]/page.tsx` stays **outside** `(shell)/` and continues to
     render the full `ChatSidebar` (which includes both nav and the sessions list).
     This avoids double-rendering a sidebar on chat pages.
  5. Active-route highlighting in `NavSidebar` uses `usePathname()` — same logic as
     the existing `ChatSidebar` `isActive` check.
- **Test:** Navigate from `/chat/<id>` to `/kpi` and back — the nav sidebar must
  remain visible throughout. Each nav item highlights correctly for its route.
  Playwright E2E: assert `<aside>` is present on `/kpi`, `/approvals`, and `/audit`.
