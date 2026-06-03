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

### T-020: Add prompt integration test tier — **Done**
- **File:** `tests/integration/test_prompts_mock_llm.py` (new)
- **What:** Run 5–10 representative prompts with a mock LLM and real DB. Confirm
  intent classification, routing, and tool execution behave as expected without
  incurring real LLM API costs.
  Pattern reference: `~/projects/agentic-system-mvp/apps/api/tests/integration/test_prompts_mock_llm.py`
- **Test:** This IS the test. Mock LLM, real DB, zero API cost.

### T-021: Adopt structlog for structured logging — **Done**
- **Files:** `packages/agent/runtime.py`, `packages/agent/orchestrator/*.py`, `apps/api/`
- **What:** Replace `logging.getLogger(__name__)` with `structlog.get_logger()`.
  Bind `session_id`, `agent_role`, and `tool_name` as structured fields. Configure
  JSON output so logs are consumable by external observability platforms.
- **Test:** Captured stdout log output is valid JSON with the expected fields present.

### T-022: Integrate MLflow tracing — **Done**
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

### T-023: Light mode support — **Done**
- **File:** `apps/web/` (Tailwind config, layout, global CSS)
- **What:** Add light/dark mode toggle to the web UI. Use Tailwind's `dark:` variant
  strategy (`class` mode). Persist preference to `localStorage`. Default to system
  preference via `prefers-color-scheme`. Apply tokens consistently — no hardcoded
  color values outside the design token layer.
- **Test:** Toggle switches `<html class="dark">` on/off; preference survives page reload.

### T-024: Suppress health-check logs in local development — **Done**
- **File:** `apps/api/app/main.py` (or middleware layer)
- **What:** Add a logging filter that drops access log entries for `GET /health` and
  `GET /api/v1/health` at `INFO` level when `ENV=development`. This prevents the
  Docker health-check poll from flooding local logs. Do not suppress in production or
  staging.
- **Test:** In dev mode, repeated `GET /health` calls produce no access log lines;
  other routes still log normally.

### T-025: Job list — pagination, generated files, and file-centric view — **Done**
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

### T-027: Add copy-to-clipboard button to SQL query bubbles in chat UI — **Done**
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

### T-028: Fix session list flicker when navigating between sessions — **Done**
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

### T-029: Persist left navigation sidebar across all pages — **Done**
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

---

## P4 — Job Execution & HITL Flow

Goal: Close the gap between "agent proposes a job" and "job actually runs with human approval."
End-to-end flow: user asks agent → agent dispatches job via tool → HITL pause with inline approve/reject card in chat → on approval the job executes → result + file links returned in chat → history visible in Jobs page.

### Batch P4-B1

#### T-030: Extend `jobs` table schema — **Done**
- **File:** `apps/api/alembic/versions/0013_jobs_execution.py` (new migration)
- **What:** Add columns to the existing `jobs` table:
  - `params_json JSONB` — input parameters the executor will consume
  - `result_json JSONB` — output written by the executor after completion
  - `approval_id UUID REFERENCES approvals(id)` — the approval record that gates this job
  - `error TEXT` — error message when status is `failed`
  - `input_tokens INT`, `output_tokens INT`, `cost_usd NUMERIC(12,6)` — LLM cost attribution
- **Test:** Migration runs up/down cleanly against the real DB.

---

### Batch P4-B2 (after T-030)

#### T-031: Add write methods to `JobsRepository` — **Done**
- **File:** `packages/persistence/jobs_repo.py`
- **What:** Add:
  - `create(session_id, job_type, params, approval_id) -> dict` — INSERT a new job row with `status="pending_approval"`
  - `update_status(job_id, status, result=None, error=None) -> dict` — UPDATE status + result/error + sets `completed_at` when terminal
  - `add_file(job_id, file_name, file_size_bytes, mime_type, download_url) -> dict` — INSERT into `job_files`
  - `get_by_approval_id(approval_id) -> dict | None` — used by the approval webhook to find the associated job
- **Test:** Unit tests (mock DB): `create` returns row with correct defaults; `update_status` with terminal status sets `completed_at`; `get_by_approval_id` returns `None` for unknown ID.

---

### Batch P4-B3 (after T-031 — T-032 and T-034 run in parallel)

#### T-032: Implement `JobDispatchTool` — **Done**
- **File:** `packages/tools/job_dispatch_tool.py` (new)
- **What:**
  - `safety_level = "hitl"` — `AgentRuntime` will intercept before `handle()` runs and raise `HITLPause`
  - `input_schema`: `job_type: str`, `params: object`, `description: str` (human-readable summary for the approval card)
  - `handle()`: calls `JobsRepository.create()`, returns `{"job_id": ..., "approval_id": ..., "status": "pending_approval"}`
  - Ensure `HITLPause.tool_input` includes `job_id` and `description` so the chat UI can render a rich card
  - Register in `packages/tools/__init__.py`
- **Note:** `AgentRuntime` (runtime.py:251–281) already intercepts `safety_level == "hitl"` before calling `handle()`. The intercept must be updated to call `JobsRepository.create()` with the tool input **before** raising `HITLPause` so the job row exists when the approval is later processed.
- **Test:** Unit: mock `JobsRepository`; calling `handle()` directly creates a job row and returns the expected dict. Unit: `AgentRuntime` with a `hitl` tool raises `HITLPause` and the `tool_input` contains `job_id`.

#### T-034: Implement job executor — **Done**
- **File:** `packages/agent/job_executor.py` (new)
- **What:** `async def execute_job(job_id: UUID, sse_queue: Any | None = None) -> dict`
  - Loads job row via `JobsRepository.get_job()`
  - Routes by `job_type` to existing tools: `"simulate"` → `SimulationTool`, `"optimize"` → `OptimizerTool`, `"forecast"` → `ForecastTool`, `"train_forecast"` → `TrainForecastTool`
  - On success: calls `JobsRepository.update_status(status="completed", result=...)` and `add_file()` for each output file
  - On failure: calls `JobsRepository.update_status(status="failed", error=str(exc))`
  - Pushes `job_completed` or `job_failed` SSE event if `sse_queue` is provided
- **Test:** Unit: mock `JobsRepository` + tool; verify `update_status("completed")` called on success and `update_status("failed")` called on exception.

---

### Batch P4-B4 (after P4-B3 — T-033, T-035, T-037 run in parallel)

#### T-033: Register `job_dispatch` in `_ROLE_TOOL_ALLOWLIST` — **Done**
- **File:** `packages/tools/base.py`
- **What:** Add `"job_dispatch"` to the allowlist for `"orchestrator"` and `"simulation_optimizer"` roles.
- **Depends on:** T-032 (tool name must exist)
- **Test:** `ToolRegistry.list_for_role("orchestrator")` includes `job_dispatch`; `list_for_role("data_engineer")` does not.

#### T-035: Wire approval decision → job execution — **Done**
- **Files:** `apps/api/routers/approvals.py`, `packages/persistence/jobs_repo.py`
- **What:** In `POST /approvals/{id}/decision`, after updating the approval record:
  - `approved` → call `JobsRepository.get_by_approval_id(approval_id)` to find the associated job; if found, call `execute_job(job_id, sse_queue)` as a background task
  - `rejected` → call `JobsRepository.update_status(job_id, "cancelled")` if job exists
  - `needs_revision` → leave job in `pending_approval`; no execution
- **Depends on:** T-032, T-034
- **Test:** Integration: create approval + job row; POST `approved` decision; verify job status transitions to `completed`.

#### T-037: HITL job-approval card in chat UI — **Done**
- **Files:** `apps/web/components/JobApprovalCard.tsx` (new), `apps/web/app/chat/[sessionId]/page.tsx` (or `MessageBubble.tsx`)
- **What:** When the chat receives an SSE `awaiting_approval` event where `tool_input` contains `job_type` and `description`:
  - Render `<JobApprovalCard>` inline in the chat message list showing: job type badge, description, params summary
  - Two buttons: **Approve** and **Reject** — each `POST /api/v1/approvals/{approval_id}/decision`
  - On click: button enters loading state; on response, card updates to `Approved ✓` or `Rejected ✗` (non-interactive)
  - If SSE `job_completed` arrives while card is visible, append file links below the card
- **Depends on:** T-032 (needs `job_id` + `description` in SSE payload)
- **Test:** Render `<JobApprovalCard>` with mock approval_id; click Approve → fetch called with `{"decision": "approved"}`; card shows approved state after response.

---

### Batch P4-B5 (after P4-B4 — T-036, T-038, T-039 run in parallel)

#### T-036: Post-execution SSE event + chat reply with file links — **Done**
- **Files:** `packages/agent/job_executor.py`, `packages/agent/orchestrator/result_builder.py`
- **What:**
  - Executor pushes `{"type": "job_completed", "job_id": ..., "files": [{"file_name": ..., "download_url": ...}]}` SSE event on success
  - Extend `result_builder.py`: when `SessionResponse` is built after a HITL resume, include job result summary and file links in `reply` text (e.g. `"Simulation complete. 3 files generated: [report.csv](...)"`)
- **Depends on:** T-034, T-035
- **Test:** Unit: `build_response()` with a job result containing files produces a reply string with at least one download URL.

#### T-038: Jobs page — sort order, session link, approval status, result panel — **Done**
- **File:** `apps/web/app/(shell)/jobs/page.tsx`
- **What:**
  - Sort jobs by `created_at DESC` (update `JobsRepository.list_jobs` ORDER BY)
  - Add columns: **Session** (link to `/chat/<session_id>` when present), **Approval** (badge: pending / approved / rejected / — )
  - Expandable row / side drawer: show `result_json` summary and generated files inline with download links
  - Status filter dropdown: All / pending_approval / running / completed / failed / cancelled
  - Update `GET /api/v1/jobs` to accept `?status=<value>` filter
- **Depends on:** T-030, T-034 (result_json column must exist; executor must populate it)
- **Test:** Filter `?status=completed` returns only completed jobs. Row expansion shows `generated_files` for a job that has them.

#### T-039: Tests — Job execution & HITL flow — **Done**
- **Files:** `tests/unit/test_job_dispatch_tool.py`, `tests/unit/test_job_executor.py`, `tests/integration/test_job_hitl_flow.py`, `tests/e2e/test_job_approval.py`
- **What:**
  - Unit: `JobDispatchTool.handle()` creates job row with correct `job_type` and `params_json`
  - Unit: `execute_job()` routes by `job_type`, calls correct tool, updates status
  - Integration: full HITL sequence — dispatch tool call → `HITLPause` raised → `POST /approvals/{id}/decision approved` → job status `completed` → `job_files` row present
  - Playwright E2E (`@pytest.mark.e2e`): send chat message → `JobApprovalCard` renders → click Approve → Jobs page shows job as `completed` with file link
- **Depends on:** T-030–T-038

---

## P5 — Test Infrastructure & Cost Reduction

Goal: Eliminate accidental real LLM API calls from the unit tier, add vcrpy cassette
infrastructure so integration tests can record once and replay at zero cost, enable
cheap Haiku override for CI, and expose cache-hit metrics so prompt-caching
effectiveness (T-008) is measurable.

### Batch P5-B1 (all tasks independent — run in parallel)

#### T-040: Add vcrpy cassette infrastructure for integration-tier LLM calls — **Done**
- **Files:** `pyproject.toml` (add `vcrpy` to test deps), `tests/integration/conftest.py`
  (new or extend), `tests/cassettes/` (committed directory, not gitignored)
- **What:**
  - Add `vcrpy` to `[project.optional-dependencies] test` in root `pyproject.toml`
  - Add a `vcr_config` pytest fixture in `tests/integration/conftest.py` that configures:
    - Cassette storage: `tests/cassettes/`
    - Request matching: URI + method + body hash
    - Filter headers: scrub `Authorization` / `x-api-key` so cassettes contain no secrets
  - Document in `docs/TESTING.md`: add `@pytest.mark.vcr` to any integration test that
    calls the real Anthropic API; cassettes are committed (no credentials after scrubbing)
- **Test:** An integration test decorated with `@pytest.mark.vcr` passes on first run
  (records cassette) and on a subsequent run with `--vcr-record=none` (replays, no
  network traffic).

#### T-041: Add `TEST_MODEL` env var override to `create_llm_client()` — **Done**
- **File:** `packages/agent/llm/__init__.py` — `create_llm_client()`, `.env.example`
- **What:** Read `TEST_MODEL` env var at `create_llm_client()` call site; when set,
  pass it as `model=` to `ClaudeClient` instead of `DEFAULT_MODEL`. This lets CI
  use `claude-haiku-4-5-20251001` (≈10× cheaper than Sonnet) without touching
  production configuration. No changes to the `LLMClient` Protocol.
  Add to `.env.example`:
  ```
  # Set to claude-haiku-4-5-20251001 to cut integration test costs ~10×
  # TEST_MODEL=claude-haiku-4-5-20251001
  ```
- **Test:** Unit: `create_llm_client()` with `TEST_MODEL=claude-haiku-4-5-20251001`
  env var set returns a `ClaudeClient` whose `_model` attribute equals the Haiku
  model ID.

#### T-042: Expose cache-hit aggregates in `get_session_totals()` — **Done**
- **File:** `packages/persistence/llm_usage_repo.py`
- **What:** The `llm_usage` table already stores `cache_read_tokens` and
  `cache_write_tokens` (T-009). `get_session_totals()` currently returns only
  `input_tokens`, `output_tokens`, `total_cost_usd`. Extend the SQL query to also
  return `cache_read_tokens`, `cache_write_tokens`, and a derived `cache_hit_rate`
  (computed as `cache_read / (input + cache_read)`, clamped to `0.0` when the
  denominator is zero). This makes T-008 prompt-caching effectiveness measurable.
- **Test:** Unit: mock pool returns known token counts; verify `cache_hit_rate`
  computed correctly. Edge case: all zeros → `cache_hit_rate == 0.0` (no
  division-by-zero).

#### T-043: Enforce zero-network rule in `tests/unit/` conftest — **Done**
- **File:** `tests/unit/conftest.py` (new)
- **What:** Add an autouse fixture that monkeypatches
  `anthropic.AsyncAnthropic.messages.create` and `httpx.AsyncClient.send` to
  raise `AssertionError("unit tests must not make real network calls — use
  StubClaudeClient or a mock")`. Scope is `tests/unit/` only; integration and
  E2E tiers are unaffected.
  - Audit all existing `tests/unit/` files to confirm none currently call the real
    API; fix any that do by injecting `StubClaudeClient`.
- **Test:** A synthetic test that calls `anthropic.AsyncAnthropic.messages.create`
  raises `AssertionError`; other unit tests using `StubClaudeClient` pass without
  change.

---

### Batch P5-B2 (after P5-B1 — T-044 and T-045 run in parallel)

#### T-044: Implement HITL integration tests — **Done**
- **Files:**
  - `tests/integration/test_hitl_integration.py` — fill the 3 existing scaffold stubs
  - `tests/integration/test_job_hitl_flow.py` (new) — job-level dispatch → approve →
    execute sequence
- **Context:** `test_hitl_integration.py` has 3 `pass`-body tests promised by T-026.
  `test_job_hitl_flow.py` was listed as a T-039 deliverable but never created.
  Both use `httpx.AsyncClient` against a live API server (`localhost:8000`), same
  pattern as `tests/e2e/test_chat_flow.py`.
- **What:**
  - `test_hitl_integration.py` — implement the 3 scaffold tests:
    1. `test_hitl_session_transitions_to_awaiting_approval`: POST `/api/v1/decisions`
       with a prompt that triggers a hitl tool; poll `GET /api/v1/sessions/{id}`
       until status is `awaiting_approval`.
    2. `test_hitl_approve_transitions_to_completed`: call `POST
       /api/v1/approvals/{id}/decision` with `{"decision": "approved"}`; verify
       session status reaches `completed`.
    3. `test_hitl_reject_transitions_to_failed`: same flow with `"rejected"`;
       verify session produces a fallback reply.
  - `test_job_hitl_flow.py` — new file, 2 tests:
    1. `test_job_dispatch_creates_pending_job`: trigger `job_dispatch` tool via
       the decisions endpoint; verify a job row exists with `status=pending_approval`.
    2. `test_job_approve_executes_and_completes`: approve the job; verify job
       transitions to `completed` and `job_files` row is present.
- **Depends on:** P5-B1 (T-043 must pass; network guard confirms unit tier is clean)
- **Test:** All 5 tests pass with `docker compose up -d` + `uvicorn` running.
  Auto-skip when `localhost:8000` is unreachable.

#### T-045: Add Playwright E2E spec for job approval card — **Done**
- **File:** `tests/e2e/playwright/job_approval.spec.ts` (new)
- **Context:** `@playwright/test` is already in `apps/web/package.json`. The existing
  `tests/e2e/playwright/chat_flow.spec.ts` establishes the pattern (TypeScript, page
  object locators, `data-testid` attributes). T-039 promised this test but it was never
  created.
- **What:** Add a Playwright spec covering the full job approval flow:
  1. Navigate to `/chat/<session_id>`; send a message that triggers a `job_dispatch` tool
  2. Assert `<JobApprovalCard>` renders in the chat (locator: `[data-testid="job-approval-card"]`)
  3. Click **Approve** button (`[data-testid="approve-btn"]`); assert card transitions to
     approved state (`[data-testid="approval-status"]` text contains `Approved`)
  4. Navigate to `/jobs`; assert the job row shows status `completed` and at least one
     file link is present
  - Also add a reject scenario (click **Reject** → card shows `Rejected`)
  - Add required `data-testid` attributes to `JobApprovalCard.tsx` if missing
- **Depends on:** T-044 (HITL integration must pass first to confirm backend is correct),
  T-037 (JobApprovalCard must exist — it does, from P4)
- **Test:** `npx playwright test job_approval.spec.ts` passes with both Next.js dev server
  and API server running.

---

## P6 — Chat UI Stability

Goal: Fix 10 concrete bugs and fragility points identified in the chat UI code review.
No public API changes — all fixes are in `apps/web/`.

### Batch P6-B1 (all independent — run in parallel)

Six trivial-to-medium fixes with no dependencies on each other or on B2/B3.

#### T-046: Fix SSE buffer split from `\n` to `\n\n` — **Done**
- **File:** `apps/web/lib/api.ts` — `streamSession()` (line ~170)
- **Root cause:** `buffer.split("\n")` splits on every newline; the SSE standard uses
  `\n\n` (double newline) as the event boundary. Multi-line `data:` fields are
  silently truncated.
- **What:** Replace the line-splitting loop with a proper SSE parser:
  1. Split `buffer` on `\n\n` to get complete event blocks
  2. Within each block, collect all `data:` lines and join them before JSON.parse
  3. Keep the final incomplete block in `buffer` (same as today)
- **Test:** Unit (Vitest): feed a `ReadableStream` with a multi-line `data:` event
  split across two chunks; assert the parsed payload is complete and correct.

#### T-047: Fix `creating` flag never reset on successful session creation — **Done**
- **File:** `apps/web/app/chat/layout.tsx` — `onNewSession` (line ~27)
- **Root cause:** `setCreating(true)` is called but `setCreating(false)` is only
  called in the `catch` branch. When `router.push` succeeds and App Router keeps the
  layout mounted, the New Session button stays disabled forever.
- **What:**
  ```ts
  // Before router.push:
  setCreating(false);
  router.push(`/chat/${data.session_id}`);
  ```
- **Test:** Vitest + React Testing Library: mock `createSession` to resolve; assert
  `creating` is `false` after `onNewSession` completes.

#### T-048: Add `isLoadingMessages` to eliminate empty-state flash — **Done**
- **Files:** `apps/web/app/chat/ChatStateContext.tsx`, `apps/web/app/chat/[sessionId]/page.tsx`
- **Root cause:** `SessionState` has no loading flag. Between mount and `loadMessages`
  completing, `messages.length === 0` is true, causing the empty-state UI to flash
  briefly on every session navigation.
- **What:**
  - Add `isLoadingMessages: boolean` to `SessionState` (default `true`)
  - Set to `true` at the start of `loadMessages()`, `false` on completion (success or error)
  - In `page.tsx`: when `isLoadingMessages` is `true`, render a skeleton (3 grey
    placeholder bars) instead of the "What do you want to analyze today?" header
- **Test:** Vitest: `loadMessages` sets `isLoadingMessages: true` before fetch and
  `false` after; page renders skeleton while loading, messages after.

#### T-049: Strengthen optimistic-delete rollback and surface errors — **Done**
- **File:** `apps/web/app/chat/layout.tsx` — `onDelete`, `onDeleteAll`
- **Root cause:** Both functions do `setSessions(prev => prev.filter(...))` before the
  API call. On failure, `fetchSessions().then(setSessions).catch(() => undefined)` is
  the only recovery — if that also fails (full network outage), the UI shows an empty
  session list with no feedback.
- **What:**
  - Snapshot the previous sessions before the optimistic update
  - On API failure, restore from snapshot immediately (no secondary fetch required)
  - Surface a brief inline error: add `deleteError: string | null` to
    `SessionsContext` and render it as a small error banner in `ChatSidebar`
- **Test:** Mock `deleteSession` to return `false`; assert session list is restored to
  the pre-delete snapshot and the error message is visible.

#### T-050: Remove redundant `fetchSession` call on chat page mount — **Done**
- **File:** `apps/web/app/chat/[sessionId]/page.tsx` — `useEffect` (line ~40)
- **Root cause:** `fetchSession(sessionId)` is called on every session mount solely to
  redirect on 404. `loadMessages()` already fetches from the same session; a 404 there
  returns `[]`. Two parallel GET calls to the same session endpoint fire on every navigation.
- **What:** Remove the `fetchSession` call. Instead, check the response status inside
  `loadMessages()` (or a thin wrapper): if the messages endpoint returns 404, call
  `router.replace("/chat")`. Alternatively, let `ChatStateContext.loadMessages` accept
  a `on404` callback.
- **Test:** Navigate to a non-existent session ID; assert redirect to `/chat` without
  a second fetch to `/api/v1/sessions/{id}`.

#### T-051: Classify SSE errors by type for user-facing messages — **Done**
- **File:** `apps/web/app/chat/ChatStateContext.tsx` — `sendMessage` catch block (line ~245)
- **Root cause:** All errors map to the same string:
  `"Error contacting the API. Please check the backend is running."`
  Network failures, 5xx errors, and timeouts are indistinguishable.
- **What:** Distinguish error categories in the catch block:
  - `TypeError` with message `"Failed to fetch"` → `"Network error — check your connection."`
  - `Error` where `status` is 5xx → `"Server error (500). The backend may be overloaded."`
  - `AbortError` → already handled (no message shown)
  - Fallback → keep current generic message
  - Expose `errorCode` field on the assistant `ChatMessage` for future Playwright
    assertions
- **Test:** Vitest: mock `postMessage` to throw `TypeError("Failed to fetch")`; assert
  assistant message content equals the network error string.

---

### Batch P6-B2 (independent of B1 — run in parallel with B1)

#### T-052: Memoize `onTitleGenerated` and fix `useEffect` exhaustive-deps — **Done**
- **File:** `apps/web/app/chat/[sessionId]/page.tsx`
- **Root cause (a):** `onTitleGenerated` at line ~31 is an inline arrow function — new
  reference every render. `useChat` includes it in `sendMessage`'s `useCallback` deps,
  so `sendMessage` is recreated on every render, defeating memoization.
- **Root cause (b):** `useEffect` at line ~48 lists `[sessionId]` as deps but not
  `loadMessages`, violating `react-hooks/exhaustive-deps`. This causes ESLint warnings
  and risks stale-closure bugs if `loadMessages` ever changes identity.
- **What:**
  - Wrap the `onTitleGenerated` callback in `useCallback` with `[sessionId, setSessions]`
    deps
  - Add `loadMessages` to the `useEffect` deps array (it is stable via `useCallback`
    in `ChatStateContext`, so this is safe)
- **Test:** Vitest: confirm `sendMessage` reference is stable across a parent re-render
  when `sessions` state changes but `sessionId` does not.

---

### Batch P6-B3 (after T-046 — T-053 and T-054 run in parallel)

Both tasks require the SSE parser to be correct (T-046) before implementing on top of it.

#### T-053: Fix `postMessage` → `streamSession` event-loss window — **Done**
- **File:** `apps/web/app/chat/ChatStateContext.tsx` — `sendMessage` (lines ~121–128)
- **Root cause:** `postMessage` completes first, then `streamSession` is called. If the
  backend starts emitting SSE events in the few milliseconds between those two calls,
  the client misses them. In practice the backend buffers events, but it is a fragile
  ordering assumption.
- **What:** Open the SSE stream **before** POSTing the message:
  1. Call `streamSession(sessionId, controller.signal)` to obtain the async iterator
  2. Then `await postMessage(sessionId, text)`
  3. Iterate over events as before
  This ensures the stream reader is established before any events are emitted.
  Confirm with the backend that `GET /stream` blocks until a message is posted (current
  behaviour); document this assumption with a one-line comment.
- **Depends on:** T-046 (SSE buffer must be correct)
- **Test:** Vitest: mock `streamSession` to return a pre-loaded async iterator; assert
  `postMessage` is called after the iterator is obtained.

#### T-054: SSE auto-reconnect with exponential backoff — **Done**
- **File:** `apps/web/lib/api.ts` — `streamSession()` and/or `ChatStateContext.tsx` —
  `sendMessage`
- **Root cause:** When the SSE stream ends without a `done` event (network drop,
  backend restart), the `for await` loop exits silently. The assistant message is
  unfrozen by the `finally` block (`isStreaming: false`) but no reply is ever shown;
  the session is stuck.
- **What:** In `sendMessage`, after the `for await` loop exits without a `done` event,
  attempt reconnection with exponential backoff (500 ms → 1 s → 2 s → 4 s, max 3
  retries). On each retry, call `streamSession` again and resume event processing.
  If all retries fail, set the assistant message to the classified error string from T-051.
  Use the existing `abortMap` `AbortController` to cancel retries when the user navigates
  away or sends a new message.
- **Depends on:** T-046 (SSE buffer), T-051 (error classification for the final failure
  message)
- **Test:** Vitest: mock `streamSession` to return one partial event then close without
  `done`; assert the hook retries up to 3 times; on all retries failing, assert error
  message is set on the assistant bubble.

---

## P7 — CI Quality & Memory Loop Validation

Goal: Restore CI to green (2 stale unit test assertions introduced by P4 implementation),
harden the pipeline with TypeScript type-checking, and validate the Memory Loop
end-to-end so prompt-cached memory retrieval is proven correct and zero-cost to replay.

All P7-B1 tasks are independent and can run in parallel.
P7-B2 tasks depend on P7-B1 (CI must be green before adding integration tests).

### Batch P7-B1 (all independent — run in parallel)

#### T-055: Fix stale assertion in `test_inprocess_run_train_forecast_no_db_raises` — **Done**
- **File:** `tests/unit/test_job_runner.py` (lines ~59–65)
- **Root cause:** Test was authored when `_run_train_forecast` was unimplemented; it expected
  `NotImplementedError | ModuleNotFoundError`. T-034 implemented train_forecast with a DB
  fallback path (`history = []` → constant prediction at `mean_val = 0.0`) — no exception
  is raised in a unit test because no DB is required for the fallback path.
- **What:** Replace the `pytest.raises` block. Assert instead that calling `runner.result()`
  returns a `JobResult` with `status == "completed"` and the payload contains a
  `predicted_units` list. This makes the test describe what the implementation actually does.
- **Test:** CI green; `uv run pytest tests/unit/test_job_runner.py -v` passes.

#### T-056: Fix stale assertion in `test_list_for_role_orchestrator_returns_empty` — **Done**
- **File:** `tests/unit/test_tool_isolation.py` (lines ~609–612)
- **Root cause:** T-033 registered `job_dispatch` in `_ROLE_TOOL_ALLOWLIST["orchestrator"]`.
  The test still asserts `tools == []`.
- **What:** Update the assertion to:
  ```python
  assert [t.name for t in tools] == ["job_dispatch"]
  ```
- **Test:** CI green; `uv run pytest tests/unit/test_tool_isolation.py::test_list_for_role_orchestrator_returns_empty -v` passes.

#### T-057: Add TypeScript type check to CI — **Done**
- **File:** `.github/workflows/lint-test.yml` — `node-lint` job
- **Root cause:** The Node CI job runs only `npm ci`. TypeScript regressions (e.g., from
  T-046–T-054) are invisible in CI.
- **What:** Extend the `node-lint` job with two additional steps after `npm ci`:
  1. `cd apps/web && npx tsc --noEmit` — full type check
  2. `cd apps/web && npm run build` — production build (catches import errors not caught by tsc)
  Keep the job name `node-lint`; no new job needed.
- **Test:** A deliberate type error in `apps/web/` breaks the CI job; the current codebase
  passes both steps.

---

### Batch P7-B2 (after P7-B1 — requires Docker Compose + cassette)

#### T-058: Memory Loop integration test with VCR cassette — **Done**
- **File:** `tests/integration/test_memory_loop.py` (new)
- **Pre-condition:** `PgVectorMemoryStore` is already wired in `apps/api/state.py`
  (`_build_memory_store()` returns real store when `DATABASE_URL` is set). The
  round-trip (write → embed → search → retrieve) has never been tested end-to-end.
- **What:** Integration test (`@pytest.mark.vcr`, real DB):
  1. Instantiate `PgVectorMemoryStore` against the real DB (via `DATABASE_URL`)
  2. Write a `Memory` with `type="decision"`, `content="reduce safety stock for SKU-001"`
  3. Call `store.search(MemoryQuery(query_text="safety stock reduction", k=1))`
  4. Assert `len(results) == 1` and `similarity > 0.7`
  5. Also call `_resolve_weights_with_memory(mock_orchestrator, goal)` with a
     semantically similar goal; assert `weight_source == "memory"` (memory path taken)
  - Decorate with `@pytest.mark.vcr` (records cassette on first run; replays for free)
  - Guard: `@pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="requires DB")`
  - The VCR cassette scrubs the `Authorization` header (OpenAI key) before commit
- **Depends on:** P7-B1 (CI must be green before adding new integration coverage)
- **Test:** This IS the test. Proves the full Memory Loop: write → embed → retrieve → influence.

## P8 — Mock Mode for Cost-Free UI Testing

Goal: Introduce a `MOCK_LLM=true` env var that replaces the real Anthropic client with a
schema-conforming stub, exposes mock status through the API, and renders a clear visual indicator
in the UI. Developers can exercise the full UI/UX flow — chat, HITL approvals, job dispatch —
without incurring any LLM API cost.

### Batch P8-B1 (T-059 and T-060 independent — run in parallel)

#### T-059: Upgrade `StubClaudeClient` to `ScenarioStubClaudeClient` — **Done**
- **File:** `packages/agent/llm/__init__.py`
- **What:** Add `ScenarioStubClaudeClient` (keep `StubClaudeClient` as an alias for
  backward compatibility with existing unit tests). `complete()` inspects system message
  content to detect the orchestrator call type and return schema-conforming JSON:
  - System prompt contains `"category"` or `"intent"` → `SessionIntent`-shaped JSON:
    `{"category": "lookup", "confidence": 0.95, "rationale": "Mock mode", "goal_text": "<last user message>"}`
  - System prompt contains `"route"` or `"primary_role"` → `AgentRoute`-shaped JSON:
    `{"mode": "single_agent", "primary_role": "data_engineer", "rationale": "Mock stub"}`
  - System prompt contains `"verify"` or `"findings"` → verification JSON:
    `{"status": "pass", "rationale": "Mock mode — no verification performed"}`
  - All other calls → return a plain text mock response so streaming works correctly.
  - `stream()` yields a `text_delta` event with `"Mock mode response — no LLM cost incurred."`.
  - `embed()` returns zero-vectors (unchanged from existing stub).
- **Test:** Unit per pattern: correct JSON returned for each detected system prompt type.
  Default case: `complete()` returns readable text; `stream()` yields one `text_delta` event.

#### T-060: Add `MOCK_LLM` env var to `create_llm_client()` — **Done**
- **File:** `packages/agent/llm/__init__.py`, `.env.example`
- **What:**
  - In `create_llm_client()`: check `os.environ.get("MOCK_LLM", "").lower() == "true"` first.
    When true, skip the `ANTHROPIC_API_KEY` check and return `ScenarioStubClaudeClient` (T-059).
    When false (default), existing behaviour unchanged.
  - Add to `.env.example`:
    ```
    # Set to true to disable real LLM calls — enables cost-free UI testing
    # MOCK_LLM=true
    ```
  - Note: `MOCK_LLM=true` is an explicit opt-in, not a silent fallback.
    The AGENTS.md prohibition applies to missing-config degradation, not intentional test overrides.
- **Depends on:** T-059 (`ScenarioStubClaudeClient` must exist)
- **Test:** Unit: `create_llm_client()` with `MOCK_LLM=true` returns `ScenarioStubClaudeClient`
  without raising. `create_llm_client()` with `MOCK_LLM` unset still requires `ANTHROPIC_API_KEY`.

---

### Batch P8-B2 (after P8-B1 — T-061 and T-062 run in parallel)

#### T-061: Add `GET /api/v1/status` endpoint — **Done**
- **File:** `apps/api/routers/health.py` (extend existing health router)
- **What:** Add `GET /api/v1/status` returning:
  ```json
  { "mock_mode": true, "version": "0.1.0", "environment": "development" }
  ```
  - `mock_mode` = `os.environ.get("MOCK_LLM", "").lower() == "true"`
  - `environment` = `os.environ.get("ENV", "production")`
  - `version` = constant or read from package metadata
  - Add `response_model` Pydantic schema `AppStatus` to `health.py`.
- **Depends on:** T-060 (`MOCK_LLM` env var must be wired before endpoint exposes it)
- **Test:** Unit: endpoint returns `mock_mode: true` when `MOCK_LLM=true`; `false` otherwise.
  Both cases return HTTP 200.

#### T-062: Add mock mode banner to UI — **Done**
- **Files:** `apps/web/components/MockModeBanner.tsx` (new),
  `apps/web/app/layout.tsx` (root layout — add `<MockModeBanner />`)
- **What:**
  - `MockModeBanner` is a Client Component that fetches `GET /api/v1/status` once on mount.
    If `mock_mode: true`, renders a fixed amber top bar:
    `"Mock Mode Active — LLM calls are stubbed. No API cost is incurred."`
    If `mock_mode: false`, renders nothing.
  - Mount `<MockModeBanner />` in the root `app/layout.tsx` so it appears on every page.
  - No user toggle — mock mode is server-side only (controlled by `MOCK_LLM` env var).
  - Style: `position: sticky; top: 0; z-index: 50` amber/yellow Tailwind bar with an info icon.
- **Depends on:** T-061 (`/api/v1/status` must exist)
- **Test:** Vitest + React Testing Library: mock `fetch` to return `{ mock_mode: true }`;
  assert banner text visible. `mock_mode: false` → banner not rendered.

---

## P9 — LangGraph Migration

**Goal:** Replace the custom `AgentRuntime` tool loop and `SessionOrchestrator` execution
routing with LangGraph `StateGraph`, enabling checkpoint-based session persistence and
resumption. `approvals` / `jobs` tables are retained as audit logs; LangGraph
`langgraph-checkpoint-postgres` becomes the execution state source of truth.

**ADR:** `docs/adr/2026-06-02-langgraph-migration.md`

**Critical rule (enforced in all batches):** Nodes that call `interrupt()` must contain
**zero DB side effects**. All writes to `approvals` / `jobs` must happen in a preceding
node whose state is checkpointed before `interrupt()` is reached.

### Batch P9-B0 — Dependencies & DB migration (Infra — prerequisite for all)

#### T-063: Add LangGraph dependencies — **Done**
- **File:** `pyproject.toml` (api workspace)
- **What:**
  - Add `langgraph==1.2.4` and `langgraph-checkpoint-postgres` to the API package
    dependencies.
  - Run `uv lock` to update the lockfile.
  - Confirm `import langgraph` succeeds inside the Docker container.
- **Test:** `uv run python -c "import langgraph; print(langgraph.__version__)"` exits 0.

#### T-064: DB migration — `langgraph_checkpoints` schema — **Done**
- **File:** `apps/api/app/main.py` (lifespan)
- **What:**
  - Call `await AsyncPostgresSaver.setup()` once inside the `@asynccontextmanager` lifespan
    function. This creates `checkpoints`, `checkpoint_writes`, and `checkpoint_blobs` tables
    idempotently on every startup — no separate Alembic migration file needed.
  - Rationale for lifespan approach: LangGraph's own CI uses `setup()` idiomatically;
    hand-writing the DDL risks drift if LangGraph updates its schema between versions.
  - Do NOT drop or alter existing `approvals`, `jobs`, or `agent_steps` tables.
- **Depends on:** T-063
- **Test:** `SELECT table_name FROM information_schema.tables WHERE table_name LIKE
  'checkpoint%'` returns at least 3 rows after startup.

---

### Batch P9-B1 — Specialist runtime (App Builder — after P9-B0)

#### T-065: Rewrite `AgentRuntime` as LangGraph `StateGraph` — **Done**
- **Files:** `packages/agent/runtime.py`
- **What:** Replace the `_run_tool_loop` / `_verify_findings` imperative loop with a
  `StateGraph` containing three nodes:
  - `call_model` — builds 3-block system prompt (preserve `cache_control` blocks), calls
    `LLMClient.complete()`, accumulates `input_tokens` / `output_tokens` / `cost_usd` in
    graph state.
  - `execute_tools` — iterates `response.tool_calls`, calls `tool.handle()`, pushes SSE
    events (`tool_started` / `tool_completed`), appends tool results to messages in state.
  - `verify_findings` — single LLM call; conditional edge: `pass` → END,
    `needs_revision` → `call_model` (one retry), `blocked` → END with error status.
  - Conditional edge `should_continue`: `finish_reason == "stop"` or no tool calls →
    `verify_findings`; otherwise → `execute_tools`.
  - `AgentBasedSpecialist.run()` public signature unchanged — it compiles and invokes the
    graph with a `MemorySaver` checkpointer (unit tests) or the Postgres checkpointer
    (production).
  - Token accumulation: use a reducer on the state field, not a nonlocal variable.
  - Retry logic (was `_run_specialist_with_retry`): implement as a `try/except` with
    `for attempt in range(3)` inside `call_model`; exponential backoff with
    `asyncio.sleep(delays[attempt])`.
  - **Cleanup:** Remove `_run_specialist_with_retry()` from
    `packages/agent/orchestrator/runtime.py` — retry is now inside the `call_model` node.
    The orchestrator layer calls the graph directly via `specialist.run(task, ctx)` without
    the retry wrapper.
- **Depends on:** T-063, T-064
- **Test:** All existing `tests/unit/test_agent_runtime.py` assertions pass with the new
  graph structure. Use `MemorySaver` as checkpointer in tests.

#### T-066: Rewrite HITL using `interrupt()` — **Done**
- **Files:** `packages/agent/runtime.py`, `packages/agent/orchestrator/hitl.py`
- **What:**
  - Remove `HITLPause` exception class.
  - Add `prepare_hitl` node to the `AgentRuntime` graph:
    - Detects HITL tool in current tool call.
    - Creates `approvals` row and `jobs` row in DB (side-effecting work).
    - Stores `approval_id` and `job_id` in graph state.
    - Returns normally (no exception).
  - Add `wait_for_approval` node immediately after `prepare_hitl`:
    - Calls `interrupt({"approval_id": state["approval_id"], "tool_name": ..., "tool_input": ...})`.
    - Contains **zero DB writes** — enforces the interrupt() isolation rule.
  - **Post-resume execution model (critical):** When the graph resumes after `interrupt()`,
    execution continues in `execute_tools`. For HITL tools, `execute_tools` must NOT call
    `tool.handle()` again — that would create a duplicate `jobs` row. Instead, `execute_tools`
    checks `state.get("pending_hitl_job_id")`: if set, call `execute_job(job_id, sse_queue)`
    directly using the `job_id` stored by `prepare_hitl` in graph state. Only non-HITL tools
    call `tool.handle()`.
  - **Compatibility with T-035:** The `asyncio.create_task(execute_job(...))` call in
    `apps/api/routers/approvals.py` is removed by T-071; job execution moves exclusively
    into the graph resume path.
  - `SessionOrchestrator.run()` removes the `except HITLPause` block; the `session_paused`
    SSE event and `awaiting_approval` status update are emitted from a post-`prepare_hitl`
    graph node or hook.
- **Depends on:** T-065
- **Test:** Unit: mock DB repos; confirm `approvals.create()` called once even when the
  graph is re-invoked after `interrupt()`. Confirm no duplicate rows. Confirm
  `execute_job()` is called (not `tool.handle()`) when `pending_hitl_job_id` is in state.

---

### Batch P9-B2 — Session orchestration (App Builder — after P9-B1)

**Internal sequencing within B2:** T-067 must complete first (all other B2 tasks depend on it).
After T-067 is done, T-068, T-069, and T-072 can run in parallel.

#### T-067: Rewrite `SessionOrchestrator` execution routing as `StateGraph` — **Done**
- **Files:** `packages/agent/orchestrator/session_orchestrator.py`,
  `packages/agent/orchestrator/runtime.py`
- **What:**
  - Build a top-level `StateGraph` with nodes:
    - `classify_intent` — wraps existing `classify_intent()` logic.
    - `select_mode` — wraps `select_execution_mode()` logic.
    - `handle_clarification` — wraps clarification check; routes to END (clarification
      response) or continues.
    - `run_direct_chat` — wraps `run_direct_chat()`.
    - `run_sequential` — wraps `_run_agents_in_order()`.
    - `run_planned` — wraps `run_planned_execution()`.
    - `run_dag` — wraps the **existing** `run_dag_execution()` as a bridge node;
      T-068 upgrades the internal DAG execution to the LangGraph Send API after T-067 is done.
    - `synthesize` — wraps `_synthesize_response()`.
  - Conditional edges from `select_mode`:
    - `"direct_chat"` → `run_direct_chat` → END
    - `"single_agent"` / `"sequential_agents"` → `run_sequential` → `synthesize` → END
    - `"planned_execution"` → `run_planned` → `synthesize` → END
    - `"dag_execution"` → `run_dag` → `synthesize` → END
  - `SessionOrchestrator.run()` compiles and invokes this graph with
    `config={"configurable": {"thread_id": str(session_id)}}`.
  - Public interface `Orchestrator` Protocol (`run()` / `resume()`) signatures unchanged.
- **Depends on:** T-066
- **Test:** All existing orchestrator unit tests pass. SSE events emitted in the same
  order as before.

#### T-068: Replace `run_dag_execution` with LangGraph `Send` API — **In Progress**
- **File:** `packages/agent/orchestrator/planning.py`
- **What:**
  - Replace the `while remaining` / `asyncio.gather` loop with LangGraph's `Send` API:
    - `create_task_nodes()` output maps to `Send` objects targeting a `run_dag_node` node.
    - Dependency resolution: use `conditional_edges` to fan out ready nodes; a `merge`
      node collects results.
  - Preserves the same output structure (`completed: dict[str, SpecialistResult]`).
- **Depends on:** T-067 (parallel with T-069 and T-072 after T-067)
- **Test:** Unit: DAG with 3 nodes (A, B→depends on A, C→depends on A) executes A first,
  then B and C in parallel (verify timing via mock).

#### T-069: Rewrite `SessionOrchestrator.resume()` — **In Progress**
- **File:** `packages/agent/orchestrator/session_orchestrator.py`
- **What:**
  - `resume(session_id, approval_id)`:
    1. Always call `await graph.astream(None, config={"configurable": {"thread_id": str(session_id)}})`
       to resume the paused LangGraph thread from checkpoint. The `execute_tools` node finds
       `pending_hitl_job_id` in graph state (stored by `prepare_hitl`), calls `execute_job()`,
       and produces the job result as part of the graph output.
    2. Build `SessionResponse` from the graph's final output (job result, files).
  - Remove the current shortcut that returns early when a job is already `completed`
    (current: `if job.get("status") == "completed": return SessionResponse(...)`).
    In the LangGraph model the graph always drives the response, including for completed jobs.
  - Remove the fallback `await self.run(...)` path that re-classified intent from scratch.
- **Depends on:** T-067 (parallel with T-068 and T-072 after T-067)
- **Test:** Integration: pause a graph via `interrupt()`; call `resume()`; confirm
  execution continues from the paused node without re-running `classify_intent`.

#### T-072: Port history compression into a LangGraph pre-processing node — **In Progress**
- **File:** `packages/agent/runtime.py`
- **What:**
  - Add a `compress_history` node that runs before `call_model` when
    `len(state["messages"]) > SUMMARY_THRESHOLD` (30).
  - Logic unchanged: summarize oldest messages with Haiku, keep recent 10, prepend
    summary as a system message.
  - Node is a no-op when message count ≤ threshold.
- **Depends on:** T-065 (parallel with T-068 and T-069 after T-067 is done; does not
  touch SessionOrchestrator graph)
- **Test:** Unit: inject 35 messages into graph state; confirm `call_model` receives ≤ 11
  messages (10 recent + 1 summary).

---

### Batch P9-B3 — Integration layer (App Builder — after P9-B2)

#### T-070: Adapt SSE streaming to LangGraph `stream_mode="custom"` — **Not Started**
- **Files:** `packages/agent/runtime.py`, `packages/agent/orchestrator/session_orchestrator.py`,
  `apps/web/lib/api.ts` — `streamSession()`, `apps/web/app/chat/ChatStateContext.tsx`
- **What:**
  - Replace `await self._push({...})` calls with LangGraph's custom stream mode.
  - Use `stream_mode="custom"` and emit existing event dicts
    (`tool_started`, `tool_completed`, `agent_started`, `agent_completed`,
    `awaiting_approval`, `session_paused`, `intent_classified`, etc.) via `astream_events`
    or `astream` with `stream_mode=["custom", "updates"]`.
  - The `asyncio.Queue` SSE bridge cannot be stored in graph state; inject it via
    `RunnableConfig` (preferred — LangGraph-idiomatic) rather than a module-level
    context variable.
  - Frontend `EventSource` handler: verify all existing event types are still emitted;
    update field paths if LangGraph wraps them in an envelope.
- **Depends on:** T-067 (parallel with T-071 after T-069)
- **Test:** Integration: stream a mock session; assert `tool_started` and `tool_completed`
  events are received by the SSE client in the correct order.

#### T-071: Update `POST /approvals/{id}/decision` to trigger LangGraph resume — **Not Started**
- **File:** `apps/api/routers/approvals.py`
- **What:**
  - `approved` path (replacing the current `asyncio.create_task(execute_job(...))` call):
    - Look up `session_id` from the updated `approvals` row.
    - Fire `asyncio.create_task(orchestrator.resume(session_id, approval_id))` — non-blocking.
      This calls `graph.astream(None, ...)` which resumes the graph; the graph's `execute_tools`
      node runs `execute_job(job_id)` from checkpoint state.
    - Remove the `asyncio.create_task(execute_job(...))` background task call entirely —
      job execution now happens exclusively inside the LangGraph graph resume.
  - `rejected` path: still calls `JobsRepository.update_status(job_id, "cancelled")` directly
    (no graph resume; graph is abandoned).
  - `needs_revision` path: no change.
  - The `approvals` row update (audit log write) is unchanged.
- **Depends on:** T-069 (parallel with T-070 after T-069)
- **Test:** Integration: approve a pending HITL; verify the agent resumes and the job
  transitions to `running` then `completed` without re-running the intent classification.
  Verify `execute_job` is NOT called directly from the approvals router — only via the graph.

---

### Batch P9-B4 — Tests (Test/Review — after P9-B3)

#### T-073: Update unit tests for LangGraph graph structure — **Not Started**
- **Files:** `tests/unit/test_agent_runtime.py`, `tests/unit/test_agent_reclassification.py`,
  `tests/unit/test_session_orchestrator*.py`
- **What:**
  - Replace direct `AgentRuntime` instantiation with graph compilation using `MemorySaver`.
  - Assert graph node execution order via mock call counts.
  - Verify `SpecialistResult` shape is unchanged after graph execution.
  - Parametrize verify_findings retry: `needs_revision` triggers second `call_model` call.
  - Update `tests/unit/test_session_orchestrator*.py`: compile the new StateGraph-based
    `SessionOrchestrator` with `MemorySaver`; verify all 5 execution modes route through
    the correct conditional edge. No LLM calls — use `ScenarioStubClaudeClient`.
- **Depends on:** T-072

#### T-074: Integration test — HITL interrupt/resume via LangGraph — **Not Started**
- **Files:** `tests/integration/test_hitl_langgraph.py`
- **What:**
  - Full HITL cycle against real DB:
    1. Invoke a session that triggers a HITL tool.
    2. Confirm graph is paused at `wait_for_approval` node (checkpoint exists).
    3. Confirm `approvals` row created **once** (not twice).
    4. Call `resume()`.
    5. Confirm tool executes, `jobs` row transitions to `completed`.
  - Use `AsyncPostgresSaver` with test DB (not `MemorySaver`).
- **Depends on:** T-071

#### T-075: Integration test — session persistence and resumption — **Not Started**
- **Files:** `tests/integration/test_session_persistence.py`
- **What:**
  - Simulate a mid-session pause (not HITL — e.g., process restart):
    1. Start a planned_execution session, advance past `classify_intent`.
    2. Discard the in-memory orchestrator instance.
    3. Reconstruct `SessionOrchestrator` from scratch (simulates server restart).
    4. Call `run()` with the same `session_id`.
    5. Confirm the graph resumes from the last checkpointed node, not from
       `classify_intent`.
- **Depends on:** T-074
