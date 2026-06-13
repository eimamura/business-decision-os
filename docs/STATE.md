# STATE.md

Orchestrator execution state. Written only by bdos-orchestrator.

Full history archived at `docs/archive/v5/STATE.md` (earlier: `docs/archive/v3/STATE.md`).

---

## Baseline

**v0.1.0 — MVP complete (2026-06-12).** Tag `v0.1.0` (commit 039c43a) = `main` = GitHub
release. P0–P100 all Done. SPEC 10-question coverage with judged quality 10/10 PASS;
daily screening cadence live; context budget hardened. See `docs/TASKS.md` §MVP Baseline
for the capability summary and §Carry-Over for re-planning inputs.

## Completed Phases

P0–P100 all Done (T-001–T-599; D-001–D-015 all Resolved; FP-001–FP-014 recorded,
FP-011 hardened). Per-phase detail: `docs/archive/v5/STATE.md`.

---

## Active Phase

P103 — Job File Generation

## Active Lease

P103/B-02 + P103/B-03 (parallel)

## Blockers

None

## Last Completed

P102 — Job Dispatch Modal + Routing Reliability (2026-06-12). Restored "Job Dispatch (HITL)"
modal category (P81 clean-up gap); tightened ControlAgent system prompt rule 12 with explicit
trigger phrases for gemma4:12b. Sign-off: unit 1249, integration 161 (full-DSN), playwright
52+1-flaky — all exit 0. New Playwright spec: 4 tests (category tab, 2 prompt injection,
1 full mock E2E).

Previously:

P101 — Async Job Execution Validation (HITL) + Streaming UX (2026-06-12). First post-MVP
phase (user-defined technical validation). Proven end-to-end: agent dispatches heavy work
via `job_dispatch` (re-registered LLM-callable behind HITL approval); approved jobs run as
background asyncio tasks (session turn returned 0.11s, second message answered mid-run);
job rows queued→running→completed/failed; completion/failure report persisted as an
assistant message (reload-visible) + `job_report` SSE live append; JobStatusCard in chat.
Streaming: backend already chunked — bottleneck was the Next.js layer (rewrite proxy, then
`next dev` gzip rebuffering after the new SSE route handler). Fixed (route handler +
`compress: false`): web-origin measured 90 deltas / 1.855s spread vs 0.000s burst before.
Defects: D-016 (gzip negated inner fix — FP-015, verify at the wire not by inspection) and
D-017 (B-01 regression: jobs.session_id FK without CASCADE broke session deletes — FP-016;
repo-layer fix, schema cascade migration is carried over) both Resolved. Sign-off PASS
(independent re-run, NO skips): unit 1249 exit 0, full-DSN integration 161 exit 0,
playwright 48+1-flaky exit 0, build 0, lint 0, typecheck 0 — P98–P100 integration debt
recovered. Known: gemma4:12b did not route to job_dispatch from natural language in 2
attempts (approval-resume path driven directly; model-limitation, consistent with P100
residuals).

Previously:

v0.1.0 release closure (2026-06-12): P96–P100 MVP hardening programme Done; judge
campaign re-evaluation flipped Q1/Q6/Q8 to PASS (final 10/10); tag v0.1.0 created,
fast-forward merged to main (443 commits, SHAs preserved), GitHub release published.

## Blockers

None
