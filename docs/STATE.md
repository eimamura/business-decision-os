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

P128 — Release Truth & Local Security Recovery

## Active Lease

P128-B-06

## Blockers

P128 sign-off attempt 1 FAIL (2026-08-24): D-023 (integration calendar-pinned seed
baselines, 4 tests), D-024 (e2e conftest hardcoded :8000 → vacuous tier skips), D-025
(stale create-session status assertion), D-026 (HITL/job-flow e2e non-deterministic under
live gemma4:12b NL routing). All four registered under P128-B-06; fix dispatches in
progress. Gates 1/4/5/6/7 exit 0; supplemental test-web exit 0; npm audit matches the
documented deferred-major set. P124 revalidation context: the failed gates exposed latent
pre-P128 defects — consistent with this phase's release-truth goal.

Previously: P124's recorded build sign-off was invalidated inside P128 (D-019/D-020): the
repository `make build` target had never compiled the web app. P128 restored release truth
— real `next build` / TypeScript / Vitest gates now run locally and in CI (D-020 Resolved),
all three dynamic pages satisfy the Next.js 15 page contract (D-019 Resolved), operational
routes are environment-scoped with no secret material in diagnostics (D-022 Resolved), and
unit-tier sample-data tests are hermetic (D-021/FP-018). Failure analyses FP-019–FP-021
recorded, all Count=1; no hardening escalation triggered.

## Last Completed

P128-B-05 — Release record and failure learning (2026-08-24). T-757: `/analyze-failure`
run for D-019/D-020/D-022 immediately after each Resolved mark → FP-019, FP-020, FP-021
(all `design-contract`, Count 1); no Count≥2 → no `/harden-system`. T-756: Carry-Over rows
reconciled (npm audit 3-high deferred-major state; four stale rows marked Resolved with
evidence), stale DESIGN.md §CI/CD Pipeline row re-synced via delegated bdos-infra edit,
prior no-op build-gate claims invalidated through the D-019/D-020 resolutions.

Previously:

P128-B-04 — Local-only operational routes (2026-08-24). T-754 gated `/api/v1/debug` and
the `/api/v1/admin/*` router behind `APP_ENV ∈ {dev, test}` per ADR
`2026-08-24-local-only-operational-routes.md` and removed API-key prefix disclosure from
the debug response; T-755 added 9 integration HTTP environment-matrix tests plus App
Builder's 16 unit tests, preserving all existing admin endpoint assertions. D-022 marked
Resolved: production/default-safe route inspection returns `[]`; batch check
`make test-unit` (1447 passed, 15 skipped) / `make lint` / `make typecheck` all exit 0;
supplementary `make test-integration` exit 0 (25 passed, 154 DB-tier skipped).

Previously:

P128-B-03 — Real web gates and dependency security (2026-08-24). T-751 made `make build`
run real `next build` behind a stamp-gated `npm ci`, added `tsc --noEmit` to
`make typecheck`, and introduced the named `make test-web` Vitest target; T-752 aligned
`.github/workflows/lint-test.yml`, `.claude/rules/testing.md`, and `docs/TESTING.md` to the
same Make-owned contract with frontend tests in CI. T-753 removed 7 unused direct deps and
applied non-breaking updates — npm audit now 3 high (prod & full), all fix-deferred behind
next@16 major. D-020 marked Resolved on Test/Review batch-check evidence: `make test-unit`
(1431 passed, 15 skipped), `make lint`, `make typecheck`, plus Infra's `make build` /
`make typecheck` / `make test-web` — all exit 0; smoke checks skipped (stack down).
Flagged for T-756: `docs/DESIGN.md §Deployment Design §CI/CD Pipeline` table row is stale.

Previously:

P128-B-02 — Next.js 15 page-contract recovery (2026-08-24). T-749 converted the three
dynamic routes (chat session, recommendation detail, scenario comparison) to async Server
Page wrappers awaiting `params` and delegating to colocated Client Components; T-750 added
`apps/web/app/__tests__/dynamic-route-page-boundaries.test.tsx` guarding the Next.js 15
page contract. D-019 marked Resolved on Test/Review evidence: `npm run build` exit 0
(all three routes server-rendered `ƒ`), `npx tsc --noEmit` exit 0, `npm test` exit 0
(14 files, 86 tests), plus `make test-unit` (1431 passed, 15 skipped), `make lint`,
`make typecheck` all exit 0. Specialist work executed via opencode subagents.

Previously:

P128-B-01 — Hermetic sample-data tests (2026-08-24). T-748 redirects generated
operational CSVs to pytest `tmp_path`; D-021 Acceptance confirmed by Test/Review:
`make test-unit` exit 0 (1431 passed, 15 skipped), `make lint` exit 0,
`make typecheck` exit 0 (186 files), and `git status --short -- data/sample` empty.
`/analyze-failure D-021` recorded new FP-018 (`design-contract`, Count 1); no
hardening escalation is required.
OpenCode completed the work; Orca recorded the task through manual recovery after the
OpenCode prompt acknowledgement returned `agent_prompt_stalled` and revoked lifecycle
messages.

Previously:

P127 — Harness Hygiene: Dead References, Gate Naming, SSoT Consolidation
(2026-07-09). Executed all findings of the 2026-07-09 /harness-engineering audit. B-03: forbidden-write
set canonicalized to five directories (SKILL HARD STOP = canonical statement;
ORCHESTRATOR.md §Write Authority = SSoT; AGENTS.md reduced to summary + pointer);
Defect Task trigger conditions SSoT-declared in ORCHESTRATOR.md §Defect Task Format.
B-04: STATE.md duplicate ## Blockers merged; TASKS.md duplicate P116 heading merged
and stale Not Started rows under Done phases reconciled (P125-B-02, P110-B-03,
P108 T-638, P119 B-02–B-05); DECISIONS.md P127 entry appended. B-01: dead-reference
repointing (§Stub Behavior → TESTING.md §Stub Conformance ×5 sites; §Phase Progression
removed from AGENTS.md; per-layer §Architecture Constraints references fixed) + unit
gate normalized to `make test-unit` in orchestrator SKILL step 8, ORCHESTRATOR.md
Design Improvement Loop, and test-review SKILL batch-check bullet (leftover caught at
batch check, fixed on first return). B-02: `docs/DESIGN.md §Deployment Design` authored
(local stack, compute platform, frozen Azure/Terraform state, DB conventions, CI/CD —
facts verified against live repo); bdos-infra SKILL slimmed to process + pointers.
B-05 sign-off: unit 1431/15 skipped, integration 16/154 skipped, e2e 10 skipped,
playwright 52 passed (dev stack was up; 1 flaky passed on retry), build OK, lint
clean, typecheck 186 files — all exit 0. Note: playwright passing with the stack up
suggests the P124 sign-off blocker is now resolvable by re-running its gate set.

Previously: P126 — Harness & Docs Integrity Fixes (2026-07-06). Executed all findings of the
2026-07-06 /harness-engineering audit. B-01 (docs layer): TOOLS.md stale 6-table
allowlist and frozen per-intent tool lists replaced with pointers to code SSoT
(sql_allowlist.py / _INTENT_TOOL_SUBSET); TESTING.md + .env.example Ollama model set to
gemma4:12b; DESIGN.md coding-agents table replaced with AGENTS.md pointer;
ORCHESTRATOR.md gained §Mandatory Gate Set (sign-off SSoT) and expanded §Write Authority;
failure-patterns.md line-number citation fixed; prevention-policy.md policy notes added
(one-sentence prohibitions + FP link; section-citations-only); AGENT_ARCHITECTURE.md
archived (orphaned ~P67 snapshot contradicting DECISIONS.md on job_dispatch). B-02
(harness layer): design-contract-watch.md FP IDs resynced (mislabeled FP-007/008 were
FP-008/009; real FP-007 added); 6 SKILL.md files deduped to pointers; bdos-infra smoke
checks fixed to make dev-smoke + configured ports; stale Sonnet 4.6 commit trailer
removed; AGENTS.md dead references removed and §References completed
(TOOLS/RAG/ORCHESTRATOR/SPEC); testing rules/docs ownership split. B-03: STATE.md
English fix, DECISIONS.md policy entries, memory watchlist FP resync + stale memory
deleted. B-04 sign-off: unit 1431/15 skipped, integration 16/154 skipped, e2e 10
skipped, build OK, lint clean, typecheck 186 files — all exit 0. New carry-over items:
npm audit HIGH (undici transitive), DESIGN.md §Deployment Design dead pointer,
test_sample_data.py CSV mutation side effect.

Previously: P125 — ControlAgent System Prompt Quality Improvements (2026-06-14). B-01: Applied 5 Judge-Report fixes — (1) render_response_format() prepends language instruction; (2) grounding_footer allows cost-impact tool after stockout-list call; (3) supply shortage rule replaced {schema_example} placeholder with explanatory prose; (4) job_dispatch integrated into rule_texts sequential numbering; (5) grounding_footer appends empty-result fallback. B-02 sign-off: unit 1431/15 skipped, integration 16/154 skipped, build OK, lint clean, typecheck 186 files — all exit 0.

Previously: P123 — Next.js 15 Upgrade (2026-06-14). B-01: Next.js 14→15 upgrade — `next@^15.5.19` in apps/web, Route Handler `await params` applied (route.ts), 5 HIGH CVEs resolved. D-018: fixed incorrect `use(params)` application in 3 Client Components (`chat/[sessionId]/page.tsx`, `recommendations/[id]/page.tsx`, `scenarios/[sessionId]/page.tsx`) — reverted to direct `params: { ... }` access.B-02 sign-off: unit 1431/15 skipped, integration 16/154 skipped, e2e 10 skipped, build OK, lint clean, typecheck 186 files, playwright 53/53 — all exit 0.

Previously: P122 — Technical Debt & Security Hardening (2026-06-14). B-01: Alembic migration 0025_jobs_session_cascade.py — jobs.session_id FK re-added with ON DELETE CASCADE (FP-016 residual closed). B-02: npm audit CVE remediation — eslint-config-next 14->15.5.19 (resolves GHSA-5j98-mcp5-4vw2 HIGH glob cmd injection); react-syntax-highlighter 15->16.1.1 (resolves GHSA-x7hr-w5r2-h6wg moderate prismjs DOM clobbering); 5 next@14.x HIGH CVEs and 1 AI SDK moderate CVE accepted with rationale in package.json securityAcceptedCVEs. Post-remediation: 12 vulnerabilities (6 low, 5 moderate, 1 high) down from 18. B-03 sign-off: unit 1431/15 skipped, integration 16/154 skipped, e2e 10 skipped, build OK, lint clean, typecheck 186 files — all exit 0.

Previously: P121 — Harness Defect Fixes (2026-06-13). B-01: Bash tool added to bdos-orchestrator and analyze-failure subagent definitions; ORCHESTRATOR.md Design Improvement Loop gate updated (make test-integration added, make build removed). B-02: analyze-failure and harden-system name slugs corrected; bdos-orchestrator agent description expanded to match SKILL.md. B-03: design-contract-watch.md expanded with FP-013+FP-014 (paths include packages/schemas/**); failure-patterns.md Pattern column translated to English; prevention-policy.md FP-011 lever log clarified with implemented test references. Sign-off: unit 1431/15 skipped, integration 16/154 skipped, e2e 10 skipped, build OK, lint clean, typecheck 185 files — all exit 0.

Previously: P120 — RAG Verification: DecisionMemoryStore Recency Fallback Fix (2026-06-13). B-01: DecisionMemoryStore.search() bare-string recency fallback implemented (non-JSON queries now return k most recent records); 3 new unit tests (test_decision_memory_store.py); integration test appended to test_memory_stores.py. Sign-off: unit 1431/15 skipped, integration 16/154 skipped, e2e 10 skipped, build OK, lint clean, typecheck 185 files — all exit 0.

Previously: P119 — Evaluation-Driven Hardening (2026-06-13). (B-01) ADR docs/adr/2026-06-13-memory-store-async-split.md — documents sync base / async implementation split decision. (B-02) _build_system_prompt() dead parameter schema_context removed. (B-03) ORCHESTRATOR.md DECISIONS.md scan → blocking gate; AGENTS.md + SKILL.md Orchestrator write boundary expanded to docs/ new files. (B-04) lint-test.yml python-integration-test job added (postgres:16 service + alembic + pytest tests/integration/). Sign-off: unit 1428/15 skipped, integration 16/153 skipped, e2e 10 skipped, build OK, lint clean, typecheck 185 files — all exit 0.

Previously: P118 — Failure Pattern Harness Hardening (2026-06-13). B-01: FP-NNN back-references added to AGENTS.md §Prohibitions (FP-003 × 2, FP-011). B-02: .claude/rules/design-contract-watch.md created (FP-004/007/008/010/016 watch points, path-scoped to packages/agent/**, packages/tools/**, packages/persistence/**). B-03: memory/project_failure_watchlist.md created with 9 high-risk Count=1 patterns; MEMORY.md indexed.

Previously: P117 — RAG Documentation & Schema Context Refactor (2026-06-13). Created docs/RAG.md; moved DB schema context from system prompt to task.instruction via _inject_schema_context(). Sign-off: unit 1428/15 skipped, integration 16/153 skipped, e2e 10 skipped, build OK, lint clean, typecheck 185 files — all exit 0. — Context Engineering Pipeline: Bug Fixes & Field Activation (2026-06-13). Fixed 7 bugs/gaps across 3 batches: (B-01) system_prompt propagation to AgentRuntime._system_prompt + prohibited_tools enforcement via _narrow_tools(); (B-02) ContextPack.routing_hint injected into system prompt, skill_keys used in _inject_skills() via SkillLoader.load_by_keys(), context trace logging activated via get_pool() in ContextBuilder.build(); (B-03) render_routing_policy() guards rules 6–11,14 by tool presence with sequential re-numbering, _USE_CASE_KEYWORDS expanded with paraphrases for all Q1–Q10, past-decisions search key changed to task.instruction. 13 new unit tests. Sign-off: unit 1426/15 skipped, integration 16/153 skipped, e2e 10 skipped, build OK, lint clean, typecheck 185 files — all exit 0.

Previously: P115 — Continuous Eval Runner (2026-06-13). Eval-driven Context Engineering refactor complete (P112–P115): golden cases dataset for SPEC Q1–Q10 (data/evals/spec10_golden_cases.yaml), EvalCase schema (packages/agent/evals/eval_case.py), ContextPack schemas + USE_CASE_PACKS (packages/schemas/context_packs.py), ContextBuilder with keyword-based use-case classification (packages/agent/control/context_builder.py), integrated into control_agent.py via tool_subset_override, context trace logging (context_log table migration 0024 + ContextLogRepository + GET /api/v1/admin/context-logs), EvalRunner with failure taxonomy (packages/agent/evals/runner.py), CLI runner script (scripts/run_evals.py) + make eval target. Sign-off: unit 1413/15 skipped, integration 16/153 skipped, e2e 10 skipped, build OK, lint clean, typecheck clean — all exit 0. ADR: docs/adr/2026-06-13-eval-driven-context-engineering.md.

Previously: P111 — control_agent.py System Prompt Improvements (Judge Report) (2026-06-13). Applied 5 Judge-Report fixes: (1) Rule 11 added for decision_support tools (optimize_replenishment/simulate_inventory/forecast/request_approval/evaluate_candidates); (2) {schema_example} moved to after synthesis instruction in Rule 3; (3) rules renumbered 1–14 sequentially (no 2b); (4) SPEC Q5/Q7/Q8/Q9/Q10 replaced with inline semantic labels; (5) _build_system_prompt(intent=...) now narrows render_routing_policy() subset; ControlAgent.run() rebuilds system_prompt after intent_category resolved. 5 new tests in test_control_prompt.py. Sign-off: unit 1308/15 skipped, integration 16/153 skipped, e2e 10 skipped, build OK, lint clean, typecheck clean (178 files) — all exit 0.

Previously: P110 — control_agent.py Cleanup (2026-06-13). Fixed 6 issues: (1) duplicate tool catalog removed from _build_system_prompt; (2) _make_schema_example now accepts schema: str param; (3) rules 11–12 moved from render_response_format to render_routing_policy; (4) ControlAgent.run() refactored into 6 private methods; (5) DecisionMemoryStore consolidated to 1 instantiation per run(); (6) _SYSTEM_PROMPT_TEMPLATE stub deleted, _ = intent/user_role replaced with noqa. Sign-off: unit 1303/15 skipped, integration 16/153 skipped, e2e 10 skipped, build OK, lint clean, typecheck clean (178 files) — all exit 0.

Previously: P109 — Context Engineering Refactor (2026-06-13). Extracted `render_business_guidelines()`, `render_response_format()`, `render_schema_context()` from `_SYSTEM_PROMPT_TEMPLATE`; `_build_system_prompt()` updated to signature `(intent, user_role, schema_context)` assembling sections via `"\n\n".join(filter(None, [...]))`; 2 new unit tests added. Sign-off: unit 1300/15 skipped, integration 16/153 skipped, e2e 10 skipped, build OK, lint clean, typecheck clean (178 files) — all exit 0.

Previously: P108 — render_routing_policy (2026-06-13). Added `render_tool_catalog()` and `render_routing_policy()` to `control_agent.py`; `_SYSTEM_PROMPT_TEMPLATE` routing section replaced with `{routing_policy}` placeholder populated from `_INTENT_TOOL_SUBSET`; `_make_schema_example()` derives table names from `ALLOWED_READ_TABLES` (not literals); 2 new unit tests added in `test_control_prompt.py`. Sign-off: unit 1298/15 skipped, integration 16/153 skipped, e2e 10 skipped, build OK, lint clean, typecheck clean (178 files) — all exit 0.

Previously: P107 — _SYSTEM_PROMPT Maintainability (2026-06-13). Hardcoded SQL schema strings removed from `_SYSTEM_PROMPT` in `control_agent.py`; replaced with `_make_schema_example()` / `_build_system_prompt()` using `get_schema_context()`. Table/column prose references genericized. New unit test `test_control_prompt.py` validates all backtick-quoted tool names in the prompt exist in `ToolRegistry`. Sign-off: unit 1296/15 skipped, integration 16/153 skipped, e2e 10 skipped, build OK, lint clean, typecheck clean (178 files) — all exit 0.

Previously: P106 — Fix Inline Chart Streaming (2026-06-13). Emits chart code fences as text_delta SSE events in _run_and_signal() so inline charts appear during streaming sessions, not only on page reload. 5 new unit tests in test_sessions_chart_streaming.py. Sign-off: unit 1295/15 skipped, integration 16/153 skipped, e2e 10 skipped, build OK, lint clean, typecheck clean (178 files) — all exit 0.

Previously: P105 — Chart Scenarios in ToolScenarioModal (2026-06-13). Added "Charts" category with Stockout Risk Chart and Demand Trend Chart scenarios. Sign-off: unit 1290, integration 16 passed/153 skipped, e2e 10 skipped, build OK, lint clean, typecheck clean — all exit 0.

Previously: P104 — Inline Charts in Chat Messages (2026-06-13). extract_chart_specs() builds ChartSpec dicts from list_stockout_risk and analyze_demand_trend tool outputs; sessions.py appends chart code fences to assistant reply; InlineChart.tsx renders recharts BarChart/LineChart inline in AssistantBubble. Sign-off: unit 1290, integration 16 passed/153 skipped, e2e 10 skipped, build OK, lint clean, typecheck clean — all exit 0.

Previously: P103 — Job File Generation (2026-06-13). SimulationTool/OptimizerTool/ForecastTool generate
CSV files via generated_files output; migration 0023 adds file_content BYTEA to job_files;
GET /api/v1/jobs/files/{id}/download serves bytes; JobStatusCard renders download links.
Sign-off: unit 1280, integration 165 (full-DSN), e2e 10 skipped (no server), build OK,
lint clean, typecheck clean — all exit 0. Pre-existing data-drift in T-589 assertion fixed.

Previously: Restored "Job Dispatch (HITL)"
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
