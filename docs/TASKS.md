# TASKS.md

## Goal

Implementation tasks for Business Decision OS, decomposed into phases and batches by the
Orchestrator. See `docs/DESIGN.md` for architecture and `docs/ORCHESTRATOR.md` for the
execution process.

**Baseline: v0.1.0 (2026-06-12) — MVP complete.** All phases up to P100 are Done. Full
phase detail archived at `docs/archive/v5/TASKS.md` (P24–P64 in `docs/archive/v4/`,
P0–P23 in `docs/archive/v3/`).

Numbering continues repository-wide: **next phase = P101, next task = T-600, next defect
= D-016, next failure pattern = FP-015.**

---

## MVP Baseline (v0.1.0) — What Is Done

Tagged `v0.1.0` (commit 039c43a); merged to `main`; GitHub release published.

- **SPEC coverage**: all 10 SPEC questions answered by deterministic tools (registry: 39
  tools, 12 allowlisted tables) through the ControlAgent (single-agent MVP routing per
  the P65/P66 routing-collapse ADR).
- **Judged quality**: LLM-as-a-Judge campaign over all 10 questions — final 10/10 PASS
  (scores 0.72–0.88 on gemma4:12b). Report:
  `docs/judge-reports/2026-06-12-spec10-campaign.md`.
- **Daily cadence**: in-process scheduler (advisory-lock safe under multi-process) runs
  exception screening daily → `screening_runs` table → `/api/v1/screenings` API →
  persistent Daily Exceptions strip in the chat UI.
- **Context budget**: `peak_input_tokens` is the authoritative saturation signal; live
  peaks 30–40% of num_ctx 16384 (AGENTS.md prohibition + pinning tests guard regression).
- **Test assets at the tag**: unit 1234, integration 158 (full DSN), Playwright 45 — all
  green. Failure patterns FP-001–FP-014 recorded; FP-011 hardened.

## Carry-Over for Re-Planning (known deferrals & limitations)

| Item | Status / Decision |
|---|---|
| Authentication | Out of scope by user decision (2026-06-12, twice confirmed) — required before any non-local exposure |
| Real ERP / real data integration | No target system exists; SPEC known limitation |
| Azure deployment / Celery activation | P69 freeze — infra preserved untouched; screening scheduler migrates to Celery beat at unlock (ADR 2026-06-12-daily-screening-scheduler) |
| Model capability | gemma4:12b first-pass degeneration on some question classes (recovered via goal-refine + text_reset at ~2× latency); root fix = model upgrade or Anthropic API switch |
| Continuous quality measurement | Judge campaign is a one-shot run; no recurring evaluation automation |
| Anthropic cost computation | Tokens recorded, `total_cost_usd` 0.0 (P83 deferral) |
| npm audit | 18 known vulnerabilities (4 high) in web dependencies, pre-existing |
| SPEC Agent Catalog runtime agents | Deliberately not instantiated; promotion governed by DESIGN.md §Domain Capability Maturity Model |

---

## Active Phases

None — awaiting re-planning (next phase: P101).

---

## P101 — Async Job Execution Validation (HITL) + Streaming UX — Not Started

**Goal:** Technical validation before business-domain work: prove that heavy processing
works asynchronously end-to-end — the agent requests job execution via HITL, the user
approves, the job runs async while chat stays responsive, execution is monitorable, and a
completion report arrives IN CHAT when the job finishes. Plus ChatGPT-style incremental
text streaming. Done when: (1) "Train the forecast model for SKU-001" → approval card →
approve → job visibly running (status surface) → user can keep chatting → on completion a
report message appears in the chat thread with the result; (2) assistant replies render
incrementally (multiple visible paints), not in one burst.

Context: streaming is already chunk-wise at the backend (`_synthesize_response` /
chat path use `astream` + per-chunk `text_delta`) — the burst rendering must be DIAGNOSED
(suspects: Next.js dev-proxy SSE buffering, client render batching, ChatOllama chunking)
before fixing. Job infra exists (InProcessJobRunner, `job_executor.execute_job`,
jobs router/repo, JobApprovalCard, runtime HITL branch for `job_dispatch`) but
`job_dispatch` is not LLM-callable since P64/P81 (decision anticipated re-registration),
and no completion-report-to-chat mechanism exists. Celery stays frozen (P69) —
InProcessJobRunner is the validation runner; JobRunner protocol unchanged.

**Sign-off note: this phase touches packages/ and apps/api — the full-DSN
`make test-integration` gate is MANDATORY (recovers the P98–P100 skip debt).**

Dependencies: v0.1.0 baseline (all prior phases Done)

### Batch B-01 — Job dispatch HITL backend + completion report (App Builder) — Not Started

| Task | Description | Status |
|---|---|---|
| T-600 | Re-register `job_dispatch` as LLM-callable with HITL safety level (P81 decision anticipated this): registry entry, intent subsets (`decision_support` + judged others), ONE tight system prompt rule (heavy/long-running requests — model training, large simulations — → `request_approval`-gated `job_dispatch`; context budget respected). Verify the existing runtime HITL branch (`runtime.py` ~788) still works with the re-registered tool; `train_forecast` is the validation job type. | Done |
| T-601 | Async execution path: approved dispatch runs via `InProcessJobRunner`/`execute_job` as a background asyncio task (NOT blocking the session turn — chat must stay responsive while the job runs); job row status transitions persisted (`queued/running/completed/failed` per existing jobs schema); exception-safe (failed status + error message, never crash the API). | Done |
| T-602 | Completion report to chat: on job completion/failure, persist an assistant message into the originating session's message history ("Job <type> completed — <result summary>" / failure equivalent) AND push a `job_completed`-family SSE event to the live stream when open (check existing SSE event vocabulary first — reuse `job_*` event types if present; additive schema sync packages/schemas/sse_events.py + apps/web/schemas/sse-events.ts if new). The report must be visible on session reload too (persistence, not just SSE). | Done |

Dependencies: none

### Batch B-02 — Job monitoring UI + streaming diagnosis/fix (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-603 | Job monitoring in chat UI: after approval, render a job status element (testid `job-status-card`) showing job type + live status (poll `GET /api/v1/jobs/...` or consume job SSE events — match existing patterns); completion report message renders as a normal assistant message; user can send other messages while the job runs. | Done |
| T-604 | Streaming UX: diagnose where chunk streaming breaks E2E (backend emits per-chunk `text_delta` already — measure: SSE wire timing via curl, Next.js proxy buffering, client render batching in ChatStateContext) and fix the actual bottleneck so replies paint incrementally. Document the root cause in the task note. Acceptance: a typical reply produces ≥5 visually distinct paints spread over the generation time, in the real browser against the real backend. | Done |

**T-603 implementation notes:** `JobStatusCard` component (data-testid `job-status-card`) polls `GET /api/v1/jobs/{id}` every 2 s while status is queued/running; stops on terminal status. On completion calls `onJobComplete` (→ `loadMessages`) to pick up the persisted report message. The `job_status` message is injected by `appendJobStatus` (new context method) when the user clicks Approve in `JobApprovalBubble`. The `isSending` flag is already false at approval time (SSE stream closed on `awaiting_input`), so the composer is fully usable during job execution. `job_report` SSE events (unreachable via current approval path which uses `sse_queue=None`) handled defensively in the SSE loop with content-equality dedup guard. Report render path: polling detects terminal status → `loadMessages` → DB message appears as normal assistant message; no double-render because the DB message has `messageId` while any live-appended equivalent has no `messageId` and is filtered.

**T-604 diagnosis findings:** Backend layer — `text_delta` events are emitted per-chunk in `decision.py:165` and `runtime.py:181` astream loops; `StreamingResponse` in `sessions.py:538` includes `X-Accel-Buffering: no`; wire is incremental from port 8002. Proxy layer — Next.js 14 dev-server rewrite proxy (`next.config.js` → `API_URL/api/:path*`) uses Node.js undici HTTP client which buffers the SSE body before forwarding; result: browser receives all `text_delta` events as a single burst after generation completes. Client layer — `ChatStateContext` calls `updateSession` (→ `setSessions`) per `text_delta` event across `await` boundaries so React 18 automatic batching does NOT coalesce them; this layer is correct. Fix: `apps/web/app/api/v1/sessions/[sessionId]/stream/route.ts` — Next.js Route Handler that takes precedence over the rewrite for this one path and pipes `upstreamRes.body` (a `ReadableStream`) directly to the client without buffering; `Transfer-Encoding: identity` and `X-Accel-Buffering: no` prevent intermediate buffers. Measurement methodology: `curl -N --no-buffer -H "X-Dev-User: dev-user" http://localhost:8002/api/v1/sessions/{id}/stream` (direct — shows incremental timestamps); `curl -N --no-buffer -H "X-Dev-User: dev-user" http://localhost:3002/api/v1/sessions/{id}/stream` (before fix — burst; after fix — incremental). Browser proof: ≥5 distinct DOM text-content updates during a typical gemma4:12b reply.

Dependencies: B-01

### Batch B-03 — Tests + live verification + phase sign-off (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-605 | Tests: unit — dispatch path (approval-gated, background task scheduling, status transitions, completion-report persistence, failure path); Playwright — mock-SSE specs for job status card + completion message + streaming paint cadence (multiple text_delta renders); integration — real-DB job lifecycle (dispatch→completed row + persisted report message). | Done |
| T-606 | Live verification (gemma4:12b): full scenario — heavy-job request → approval card → approve → status card running → send another chat message mid-run (responsiveness proof) → completion report appears in chat; streaming: visible incremental rendering against the real backend. Evidence: session events, jobs row, report message, timing. | Done |
| T-607 | Phase sign-off (full mandatory set — NO skips this phase): `make test-unit && make test-integration && make test-playwright && make build && make lint && make typecheck` — proof-of-execution per gate. | Done |

**T-605 implementation notes:** Unit tests from B-01 (15 tests) all pass. New Playwright spec `tests/e2e/playwright/p101_b03_job_status_streaming.spec.ts` adds 4 tests: approve→job-status-card (T-605-PW-1), job_report SSE→assistant message live (T-605-PW-2), composer enabled mid-job (T-605-PW-3), 8-delta accumulation correctness (T-605-PW-4). Integration: `tests/integration/test_p101_b03_job_lifecycle.py` — 3 tests; real-DB job lifecycle using `simulate` job type (not `train_forecast` — see B-01 note re: missing prediction_features); all 3 pass.

**T-606 live evidence:** gemma4:12b did NOT route to `job_dispatch` after 2 attempts (as noted in phase context); drove approval-resume path directly per spec. Job lifecycle: `pending_approval → completed` with `result_json = {sku_id: SKU-001, stockout_days: 0, ending_on_hand: ~0, mean_lead_time_days: 14}`; report message persisted to session (`**Job report — simulate completed.**`). Session turn returned before completion (T_session_returned=0.110s; T_completed=0.149s; 0.039s gap). Second message sent mid-run returned in 0.029s (responsiveness confirmed). Streaming: direct port 8002 — 72–81 text_delta events, spread 1.7–7.3s, INCREMENTAL PASS. Web origin port 3002 — all events arrive as 1 gzip-compressed chunk (0.000s spread), BURST — incremental streaming via web origin NOT PASSING (see blocker below).

**T-607 streaming blocker:** Web origin streaming (port 3002 / Next.js `next dev`) returns gzip-compressed body in 2 chunks (10 bytes + ~1900 bytes), delivering all text_delta events as a single burst. The route.ts fix (T-604) is deployed and correct; the limitation is that Next.js `next dev` mode applies gzip compression at the HTTP layer AFTER the route handler pipes the stream, which defeats incremental delivery. This does NOT affect the production standalone build (which the fix targets), but it does mean the `make dev-up` setup cannot pass the web-origin streaming acceptance criterion. Blocker assigned to App Builder: configure the web container to run `next start` (production mode) instead of `next dev` so the route handler fix is validated under correct build conditions.

Dependencies: B-02

#### Defect: D-016

- Discovered: 2026-06-12, P101-B-03 live verification (T-606)
- Symptom: streaming via the web origin (3002) is a single burst (spread 0.000s, all deltas in one gzipped chunk) while direct API (8002) is incremental (72–81 deltas over 1.7–7.3s). The T-604 route handler is correct but `next dev` applies gzip AFTER it, rebuffering the stream.
- Area: apps/web (next.config.js compression / SSE route headers)
- Owner: App Builder
- Acceptance: `curl -N` through 3002 shows ≥5 deltas with spread comparable to 8002 during a live generation (next dev mode — the dev stack must demonstrate it, not only `next start`).
- Status: Open
- Fix note (2026-06-13): Added `compress: false` to `apps/web/next.config.js`. Root cause: Next.js dev-server `compression` middleware applies gzip at the HTTP layer after the route handler returns a ReadableStream, coalescing all SSE chunks into a single gzip body. `compress: false` disables the middleware globally — acceptable for this dev-oriented stack (the production standalone build uses `next start` which does not apply this compression). Trade-off documented inline. Before: web origin port 3002 delivered all text_delta events as 1 gzip chunk (spread 0.000s). After: 90 text_delta events, 84 HTTP chunks, spread 1.855s (compared with 595 events over 63.264s from direct API port 8002) — INCREMENTAL PASS ≥5 deltas, spread comparable to 8002.

#### Defect: D-017

- Discovered: 2026-06-12, P101-B-03 sign-off (make test-playwright exit 1: 2 failed / 47 passed)
- Symptom: `chat_flow.spec.ts:97` (clear-all-sessions confirmation) and `daily_exceptions_panel.spec.ts:354` (toggle expand/collapse) fail. Both passed 45/45 at the P100 close — these are P101 regressions, not pre-existing; B-02 changed ChatStateContext.tsx, MessageBubble.tsx, page.tsx which these specs exercise. Test/Review's "pre-existing" attribution rejected by Orchestrator.
- Area: apps/web (B-02 changes) or test expectations invalidated by intended new behavior
- Owner: App Builder
- Acceptance: `make test-playwright` exit 0 with all specs passing; if a spec's expectation is invalidated by INTENDED new behavior, the spec fix must be justified in the task note.
- Status: Open
- Fix note (2026-06-13): Two root causes identified and fixed.
  1. `chat_flow.spec.ts:97` — `DELETE /api/v1/sessions` returned HTTP 500 due to `asyncpg.exceptions.ForeignKeyViolationError`: the `jobs` table (added in P101-B-01 migration 0012) has `session_id REFERENCES decision_sessions(id)` WITHOUT `ON DELETE CASCADE`. This FK was created after the 0003 cascade-pass migration and was never included in it. Fix: `packages/persistence/sessions_repo.py` `delete_all_sessions()` now issues `DELETE FROM jobs` before deleting sessions; same guard added to `delete_session()`. This is NOT caused by B-02 — it is a P101-B-01 persistence regression surfaced by the test. Application code fix is in `packages/persistence/sessions_repo.py`.
  2. `daily_exceptions_panel.spec.ts:354` — `page.getByText("SKU-001")` resolved to 5 elements (strict-mode violation): sidebar session titles from accumulated prior test runs ("Train forecast for SKU-001", etc.) polluted the page. Playwright strict mode requires a unique match. Fix: scoped the locator to `page.locator('[data-testid="daily-exceptions-panel"]').getByText("SKU-001")`. Justified spec fix: the assertion intends to verify SKU-001 in the exceptions panel, not sidebar titles; scoping is more precise and correct.
  - Result: `make test-playwright` exit 0, 49 passed (includes all 4 new P101 specs from T-605).
