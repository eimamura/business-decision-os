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

None

## Active Lease

None

## Blockers

None

## Last Completed

P117 — RAG Documentation & Schema Context Refactor (2026-06-13). Created docs/RAG.md; moved DB schema context from system prompt to task.instruction via _inject_schema_context(). Sign-off: unit 1428/15 skipped, integration 16/153 skipped, e2e 10 skipped, build OK, lint clean, typecheck 185 files — all exit 0. — Context Engineering Pipeline: Bug Fixes & Field Activation (2026-06-13). Fixed 7 bugs/gaps across 3 batches: (B-01) system_prompt propagation to AgentRuntime._system_prompt + prohibited_tools enforcement via _narrow_tools(); (B-02) ContextPack.routing_hint injected into system prompt, skill_keys used in _inject_skills() via SkillLoader.load_by_keys(), context trace logging activated via get_pool() in ContextBuilder.build(); (B-03) render_routing_policy() guards rules 6–11,14 by tool presence with sequential re-numbering, _USE_CASE_KEYWORDS expanded with paraphrases for all Q1–Q10, past-decisions search key changed to task.instruction. 13 new unit tests. Sign-off: unit 1426/15 skipped, integration 16/153 skipped, e2e 10 skipped, build OK, lint clean, typecheck 185 files — all exit 0.

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

## Blockers

None
