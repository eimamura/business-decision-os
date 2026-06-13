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

### Batch B-02 — Job monitoring UI + streaming diagnosis/fix (App Builder) — Not Started

| Task | Description | Status |
|---|---|---|
| T-603 | Job monitoring in chat UI: after approval, render a job status element (testid `job-status-card`) showing job type + live status (poll `GET /api/v1/jobs/...` or consume job SSE events — match existing patterns); completion report message renders as a normal assistant message; user can send other messages while the job runs. | Not Started |
| T-604 | Streaming UX: diagnose where chunk streaming breaks E2E (backend emits per-chunk `text_delta` already — measure: SSE wire timing via curl, Next.js proxy buffering, client render batching in ChatStateContext) and fix the actual bottleneck so replies paint incrementally. Document the root cause in the task note. Acceptance: a typical reply produces ≥5 visually distinct paints spread over the generation time, in the real browser against the real backend. | Not Started |

Dependencies: B-01

### Batch B-03 — Tests + live verification + phase sign-off (Test/Review) — Not Started

| Task | Description | Status |
|---|---|---|
| T-605 | Tests: unit — dispatch path (approval-gated, background task scheduling, status transitions, completion-report persistence, failure path); Playwright — mock-SSE specs for job status card + completion message + streaming paint cadence (multiple text_delta renders); integration — real-DB job lifecycle (dispatch→completed row + persisted report message). | Not Started |
| T-606 | Live verification (gemma4:12b): full scenario — heavy-job request → approval card → approve → status card running → send another chat message mid-run (responsiveness proof) → completion report appears in chat; streaming: visible incremental rendering against the real backend. Evidence: session events, jobs row, report message, timing. | Not Started |
| T-607 | Phase sign-off (full mandatory set — NO skips this phase): `make test-unit && make test-integration && make test-playwright && make build && make lint && make typecheck` — proof-of-execution per gate. | Not Started |

Dependencies: B-02
