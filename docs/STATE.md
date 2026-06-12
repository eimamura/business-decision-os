# STATE.md

Orchestrator execution state. Written only by bdos-orchestrator.

Full history archived at `docs/archive/v3/STATE.md`.

---

## Completed Phases

P0–P38, P39–P48 all Done (T-001–T-271, T-273–T-339).

P32–P36 S&OP MVP (2026-06-04):
- P32 — SupplyPlanningAgent + 5 supply tools (T-210–T-223)
- P33 — FinanceImpactAgent + 4 finance tools (T-224–T-234)
- P34 — InventoryAgent enhancement + 4 inventory tools (T-235–T-243)
- P35 — SopAgent + "sop" intent (T-244–T-251)
- P36 — Tool Scenario prompts for S&OP agents (T-252–T-257)

P37 — Playwright E2E: Remove Mocks, Consolidate (2026-06-05; SSE-mock approach reversed by P44)
P38 — Architecture Realignment: deactivate specialist routing, clean up Tool Scenario UI (2026-06-06)
P44 — Playwright Tests: Revert to Mock SSE; 29 tests in 1.4 min (2026-06-06)
P52 — LangChain ChatModel 移行 Phase 1: ModelRegistry + Structured Output (2026-06-07)
P53 — LangChain ChatModel 移行 Phase 2: Planner + ControlAgent (2026-06-07)
P54 — LangChain ChatModel 移行 Phase 3: NlQueryTool + LLMClient Deletion (2026-06-07)
P55 — nl_query 単一 Text2SQL ツール化 + sql_query 削除 (2026-06-07)
P56 — nl_query クリーンアップ後処理 (2026-06-07)
P57 — nl_query 品質強化 (2026-06-07)
P59 — Control Agent Degenerate Response Guard (2026-06-07)
P60 — Control Agent Tool-Loop Guard (2026-06-07)
P61 — Quality Hardening: Degenerate Guard / Rule-Based Verifier (2026-06-07)
P62 — ControlAgent Groundedness Verifier Rule 1b (2026-06-07)
P63 — ControlAgent Intent-to-Tool Subset Alignment (2026-06-07)
P64 — Agent Architecture Gap Closure (5 Gaps) (2026-06-10)
P65–P70 — Full Refactoring Programme (2026-06-10): dead agent classes, routing collapse (ADR 2026-06-10-orchestrator-routing-collapse), tool allowlist rationalization, frontend dead code, dependency/config hygiene, test/docs consolidation

See `docs/archive/v3/STATE.md` for P0–P23 per-phase details.

---

## Active Phase

None

## Active Lease

None

## Last Completed

P100 — SPEC 10-Question Judge Evaluation Campaign (2026-06-12). All 10 SPEC questions run
live (gemma4:12b) and judged: initial 7 PASS / 3 FAIL; after the D-012–D-015 fixes the
three FAILs were re-judged (same methodology) and flipped — **final campaign result
10/10 PASS** (Q1 0.34→0.82, Q6 0.32→0.78, Q8 0.48→0.86; peaks 30–39% of num_ctx; report:
docs/judge-reports/2026-06-12-spec10-campaign.md incl. re-evaluation appendix). Known
model-limitation residuals (awareness only, no defect): Q1's first pass stays degenerate
on gemma4:12b (recovered via goal-refine + text_reset at ~2× latency); Q6 issues two
differently-parameterized nl_query calls (context 32%, harmless). The 3 FAILs produced four Defect Tasks,
all Resolved same-day (commit fb29591): D-012 — campaign's 104–154% context readings were
an operator.add SUM artifact (true per-call peaks 29–40%), but duplicate tool execution
was real (D-011 guard fired post-execution) → pre-execution dedupe + `peak_input_tokens`
as the authoritative saturation signal + minimal guard-synthesis prompt; D-013 — Q6 had
no routing rule and `calculate_supply_gap` is per-SKU-only → prompt rule 2b routes bulk
supply-shortage queries via nl_query; D-014 — goal-refinement concatenated degenerate
first-run text → `text_reset` SSE + web client clears in-progress text (both SSE loops,
vitest); D-015 — French bleed from goal nodes → English-only pinned in
SET_GOAL/EVALUATE_GOAL prompts. Live re-verification: Q1/Q5/Q6/Q8 grounded, peaks ≤40% of
num_ctx, no duplicates, no non-English fragments. Failure analysis: FP-011 Count→2
(escalated: /harden-system applied AGENTS.md prohibition on SUM-signal saturation checks +
2 pinning tests in test_peak_input_tokens_saturation_signal.py), FP-012/013/014 recorded.

Programme summary (P96–P100, all Done 2026-06-12): push_out relative lead-time window
(32/40→5/40 flagged), context saturation fixed at BOTH ends (synthesize payload slim
14080→222 tokens + loop pre-exec dedupe + authoritative peak signal), Daily Exceptions
persistent strip, scheduler advisory-lock hardening, judge campaign 7/10 PASS with all
FAIL root causes fixed. Unit suite 1170→1234, playwright 42→45. Gate deviation: full
integration suite skipped for P98–P100 sign-offs (user decision, DECISIONS.md 2026-06-12)
— next phase touching packages/ or apps/api MUST run `make test-integration` full-DSN.
Out of scope by user decision: auth, real ERP integration. New
`_run_scheduled_tick(triggered_by)` in apps/api/screening.py wraps schedule/startup runs
in `pg_try_advisory_lock(_SCREENING_ADVISORY_LOCK_KEY=0x73637265656E` — "screen" packed
int64`)` on a dedicated pool connection (unlock in finally, same connection) +
double-checked idempotency (latest_for_date re-checked inside the lock); manual POST /run
exempt. Live + integration concurrency proof: two concurrent ticks → exactly 1 new
completed row (no prior row) / 0 new rows (completed row exists). Sign-off PASS: unit
1207 exit 0, targeted integration (test_p99_concurrent_screening_tick.py) 2 passed exit 0,
playwright 45/45 exit 0, build 0, lint 0, typecheck 0; full integration suite SKIPPED per
user gate deviation (DECISIONS.md 2026-06-12).

Previously:

P98 — Daily Exceptions Persistent Surface (2026-06-12). DailyExceptionsPanel reworked
into a persistent collapsible strip docked between the chat header and message area —
`daily-exceptions-strip` (icon, label, run date, severity badges, toggle) mounted in BOTH
empty and active-conversation states; `defaultExpanded={isEmpty}`; all P93 testids kept;
quiet-fail unchanged; Investigate-in-chat works mid-conversation. Playwright 42→45
(active-conversation: collapsed default, toggle expand/collapse, investigate injects Q3
prompt). Sign-off PASS: unit 1199 exit 0, playwright 45/45 exit 0, build 0, lint 0,
typecheck 0; `make test-integration` SKIPPED by user decision (DECISIONS.md 2026-06-12 —
P98 is web-only; gate skip applies to P98–P100 sign-offs).

Previously:

P97 — Context Saturation Mitigation (2026-06-12). Forensics (T-591): the 14,080-token
(86% of num_ctx) call was the orchestrator-side `_synthesize_response` receiving raw
`tool_results` blobs verbatim (25,770 chars for analyze_forecast_deviation — 30 SKUs ×
weekly_breakdown). Fix: `_slim_agent_output` passes text/specialist/verification only
(+8,000-char text cap); `_OLLAMA_NUM_CTX` stays 16384 (RTX 4070 Ti 12GB: 1.8GB free <
~2GB KV-cache cost of 32768 — nvidia-smi evidence). Synthesize 14,080→222 tokens.
**D-011 (Resolved, FP-011 recorded):** stripping tool_results exposed a latent bug the
fat payload had been masking since ≥P94 — gemma4:12b duplicates tool calls → P60 loop
guard → verifier blocks on empty text → fallback; synthesize had been silently
re-grounding replies from raw tool data. Root-cause fix: new `synthesize_from_tools`
LangGraph node (duplicate-tool guard routes to ONE forced no-tools LLM call over
accumulated observations before verification) + bounded `tool_results_digest` (≤4,000
chars) in the slim payload when agent text < 50 chars. Re-verified (fresh sessions,
gemma4:12b): Q2 names SKU-001 pull-forward + SKU-027 push-out, Q3 names SKU-001/002
critical, Q1 grounded directional equivalent (SKU-015/016 from real tool data); max
input_tokens 6,152 = 37.5% of window; 0 errors; no saturation WARNING; P92 degenerate
soft-fail semantics regression-tested intact. Sign-off PASS (proof-of-execution): unit
1199 exit 0, full-DSN integration 156 exit 0, playwright 42/42 exit 0, build 0, lint 0,
typecheck 0. Note for P100 judge campaign: Q1 forecast-deviation answers skew toward
SKUs with zero forecast rows (sparse forecast_history coverage outside SKU-028/029) —
assess whether missing_data framing needs work.

Previously:

P96 — Supply Order Timing: push_out Signal Quality (2026-06-12). push_out classification
moved from flat `cover ≥ 30d` (32/40 orders flagged on seed) to a relative lead-time
window: future arrivals only AND doc_at_arrival ∈ [3×LT, 5×LT) (PUSH_OUT_K_FLOOR=3,
PUSH_OUT_K_CEIL=5, LT from sku_master.lead_time_days_mean; ≥5×LT = structurally
over-stocked → strategic review, not tactical flag; `lead_time_days` added to output
rows). Seeded result: 5/40 push_out (12.5%, all SKU-027 ranked #1 by |days_misaligned|),
pull_forward 8 unchanged vs P95 (SKU-001 +9d intact). Sign-off PASS (proof-of-execution):
unit 1177 exit 0, full-DSN integration 156 exit 0, playwright 42/42 exit 0, build 0,
lint 0, typecheck 0.

Previously:

P95 — Supply Order Timing Analysis (SPEC Q8) (2026-06-12). Final phase of the P93–P95 MVP
gap closure programme (user-approved 2026-06-12; supersedes the 2026-06-11 "Q8 partial
coverage accepted" decision). New tool `analyze_supply_order_timing` (registry 38→39): per
open supply order, projected_stockout_date from on_hand + 30d run-rate vs expected_arrival
→ pull_forward_candidate (arrival after projected stockout; precedence) /
push_out_candidate (days_of_cover_at_arrival ≥ PUSH_OUT_COVER_DAYS=30) / on_track, signed
days_misaligned, summary counts pre-cap, composite order_id sku:supplier:order_date,
hybrid contract. Wired 4 intent subsets + 3-line system prompt rule (context budget
respected — control calls measured 4208/16384 = 25.7%, no saturation; the P94 86% WATCH
applied to the orchestrator-side final call, not control). Seed: SKU-027 push_out
(today+5 arrival, ~198d cover); P84 risk-SKU orders yield 8 pull_forward (SKU-001 +9d).
All prior narratives re-verified intact (P84 2/2/3 bands, P94 SKU-028/029). Live
verification (gemma4:12b): modal prompt end-to-end — tool start+end events, reply names
SKU-001/003/006/007 pull-forward and SKU-027 push-out, 0 errors. Sign-off PASS
(proof-of-execution): unit 1170 exit 0, full-DSN integration 153 exit 0, playwright 42/42
exit 0, build 0, lint 0, typecheck 0.

Programme summary (P93–P95, all Done 2026-06-12): daily screening cadence live
(in-process scheduler + screening_runs + /api/v1/screenings + DailyExceptionsPanel; ADR
2026-06-12-daily-screening-scheduler), SPEC Q5 (analyze_forecast_deviation), SPEC Q8
(analyze_supply_order_timing). Registry 37→39 tools, migration 0021, unit suite
1080→1170, full-DSN integration 110→153, playwright 36→42. SPEC question coverage: all 10
questions now have dedicated or covering tools; modal scenarios exist for Q1–Q4, Q5, Q7,
Q8, Q9, Q10. Remaining deliberate deferrals: auth (out of scope per user 2026-06-12),
Celery activation (P69, Azure), Anthropic cost computation (P83), SPEC Agent Catalog
runtime agents (P65 routing collapse).

Previously:

P94 — Forecast Deviation Decomposition (SPEC Q5) (2026-06-12). New tool
`analyze_forecast_deviation` (registry 37→38): SKU × ISO-week forecast-vs-actual
decomposition over the last 4 complete weeks (DISTINCT ON latest-forecast dedupe,
is_missing actuals excluded, ±10% bias threshold over/under/mixed, rank total abs gap
desc / sku asc, ROW_CAP 100, hybrid contract). Wired into 4 intent subsets + system prompt
rule 6 (forecast-model quality stays with evaluate_forecast_accuracy; customer/region
attribution pairs with detect_demand_shift). Seed: SKU-028 over-forecast (24 vs 9),
SKU-029 under-forecast (16 vs 21), anchored to date.today(); P84 bands re-verified intact.
Live verification (gemma4:12b): modal prompt end-to-end — 3 control calls each selecting
analyze_forecast_deviation(weeks=4), tool events present, reply directionally correct,
0 errors. WATCH ITEM: final synthesize call hit input_tokens=14080 (86% of num_ctx 16384)
— approaching the P92 90% saturation warning; next prompt-growth phase should re-check.
Sign-off PASS (proof-of-execution): unit 1141 exit 0, full-DSN integration 134 exit 0,
playwright 41/41 exit 0, build 0, lint 0, typecheck 0. Process notes: orchestrator
committed B-01 after B-02 (ordering slip, content consistent); Test/Review self-committed
B-02 and App Builder self-set batch headers (boundary violations recorded, values correct).

Previously:

P93 — Daily Screening Job + Exceptions Surface (2026-06-12). The Screening Layer now runs
on the daily cadence per DESIGN.md §Operational Cadence: in-process asyncio lifespan
scheduler in `apps/api/screening.py` (startup catch-up run + daily `SCREENING_HOUR_UTC`
tick, `SCREENING_SCHEDULER_ENABLED` kill switch; Celery deliberately untouched per P69 —
ADR 2026-06-12-daily-screening-scheduler records the interim mechanism and Azure migration
trigger). `run_screening` invokes the `list_today_exceptions` tool handle directly (no LLM)
and persists to new `screening_runs` table (migration 0021; NOT in ALLOWED_READ_TABLES).
API: `GET /api/v1/screenings/today` (`{"run": ...|null}`), `POST /api/v1/screenings/run`
(manual, 201). Web: DailyExceptionsPanel on the chat empty state below QuickActionGrid —
severity badges, top-5 exceptions, "Investigate in chat" injects the Q3 prompt, "Run now",
quiet-fail on fetch error. Live smoke: completed row with exception_count=37
(21 critical / 3 high / 13 medium) on seeded data. Sign-off PASS (proof-of-execution):
unit 1099 exit 0, full-DSN integration 114 exit 0, playwright 40/40 exit 0, build 0,
lint 0, typecheck 0. Boundary note: App Builder self-set the B-03 batch header (value
correct; recorded for failure-pattern awareness, no defect).

Previously:

P92 — Ollama Context Window Fix + Degenerate Guard Surfacing (2026-06-12). Judge-FAIL
("Which products are at stockout risk this week?" → "Agent control failed: None", aggregate
0.00) root-caused via llm_usage forensics: `ChatOllama` had no `num_ctx`, so Ollama's
default 4096-token window silently truncated the control prompt once P86–P91 growth (tools
31→37, schema tables 8→12) pushed it past 4096 — every control call showed
input_tokens=4095/output_tokens=1, zero tool events, final text "**" → degenerate guard
hard-failed with error=None. Fixed: `num_ctx=16384` on both ChatOllama models
(`_OLLAMA_NUM_CTX` single source; 8192 accepted floor if VRAM-constrained) + ≥90%
input-context saturation WARNING; degenerate guard now soft-fails per P80 precedent
(completed + `_FALLBACK_DEGENERATE` + `verification.blocked_reason="degenerate_response"`,
no agent_failed SSE); genuine error paths default to "agent run failed (no error detail)"
so "failed: None" can never render. Live verification (T-568): exact failing query
end-to-end on gemma4:12b — control input_tokens 4112–4119 (~25% of window, no truncation
pattern), `list_stockout_risk` start+end tool events present, reply names SKU-001/002
critical, SKU-003/004 high, SKU-005/006/007 medium (P84 seed match), 0 error events.
Sign-off PASS (proof-of-execution): unit 1080 exit 0, canonical integration 16 exit 0,
full-DSN integration 110 exit 0, playwright 36/36 exit 0, build 0, lint 0, typecheck 0.

Previously:

P91 — Tool Scenario Modal: Q7 + Q9 Scenarios (2026-06-12). "Production Plan Adjustments"
(→ `analyze_production_plan_gap`, SPEC Q7) and "Customer & Region Demand Shifts"
(→ `detect_demand_shift`, SPEC Q9) added to the Supply Chain category with dedicated
Playwright tests. All seven SPEC questions with implemented tools now have modal scenarios.
Same turn: D-010 registered + Resolved (commit f625aa8) — `GET /api/v1/admin/registry`
returned `tools: []` on a fresh API process because P67's lazy `_RoleToolAllowlist` hooked
only `__getitem__`/`.get` while P85's `get_registry` iterates `.items()`/`.values()`;
fixed with iteration-path overrides + fresh-state regression tests; live-verified 37 tools
on first request after restart. FP-010 recorded (design-contract, record-only). Sign-off
PASS (proof-of-execution): unit 1075 exit 0, canonical integration 16 exit 0, full-DSN
integration 110 exit 0, playwright 36/36 exit 0, build 0, lint 0, typecheck 0.

Previously:

P90 — Tool Scenario Modal: Q10 Constraint Analysis Scenario (2026-06-12). "Biggest
Constraint Impact" scenario (id sc-biggest-constraint-impact, prompt "Which constraint is
having the biggest negative impact on sales or profit right now?") added to the Supply Chain
category of ToolScenarioModal, targeting P89's `identify_binding_constraint`; dedicated
Playwright test added (P86 precedent). Known remaining scenario gaps (deliberately out of
scope, user-request gated): Q7 `analyze_production_plan_gap`, Q9 `detect_demand_shift`.
Sign-off PASS (proof-of-execution): unit 1073 exit 0, canonical integration 16 exit 0,
full-DSN integration 110 exit 0, playwright 34/34 exit 0, build 0, lint 0, typecheck 0.

Previously:

P89 — Production Plan & Constraint Analysis (SPEC Q7 / Q10) (2026-06-11). Final phase of the
P86–P89 SPEC gap closure programme (ADR 2026-06-11-order-to-ship-and-production-data-domains).
Alembic 0020 adds `production_capacity` (16 rows: WH-001 2000/wk, WH-002 1500/wk × 8 weeks)
+ `production_plan` (264 rows) — allowlist now 12 tables. Deterministic seed scenarios:
SKU-026 overproduction (200/wk vs ~8 demand), SKU-001 underproduction (10/wk vs ~67 — ties
into P84 critical-risk narrative), WH-001 current week capacity-saturated (2460/2000,
utilization 1.23 — the intended binding constraint). New tools (registry 35→37):
`analyze_production_plan_gap` (±25% relative-gap threshold, forecast-else-run-rate demand
basis, summary counts computed pre-cap after review fix) and `identify_binding_constraint`
(3 constraint classes — capacity overload, supply gap, inventory stockout exposure — impact
= units × cost_master.stockout_cost, rank impact desc/subject asc, analytical output only
per DESIGN.md Cross-Domain constraint). Live-verified: SKU-026/SKU-001 classified correctly;
WH-001 capacity constraint ranked #1. Mid-batch review fixes: module docstring horizon
anchor (3rd docstring/code drift this programme — all caught by batch checks), summary
counts post-truncation. Sign-off PASS (proof-of-execution): unit 1073 exit 0, canonical
integration 16 exit 0, full-DSN integration 110 passed exit 0, playwright 33/33 exit 0,
build 0, lint 0, typecheck 0.

Programme summary (P86–P89, all Done 2026-06-11): SPEC Q3 (list_today_exceptions, 5
screens), Q4 (order-to-ship domain + list_unshipped_orders + analyze_shipment_delay_causes),
Q9 (detect_demand_shift customer/region), Q7/Q10 (production domain + 2 tools). Registry
31→37 tools, allowlist 8→12 tables, migrations 0019/0020, unit suite 930→1073, integration
full-DSN 82→110. Out of scope by settled decision: SPEC Agent Catalog runtime agents (P65
routing collapse ADR), Q8 (partial coverage accepted), scheduled daily screening job (P69
Celery decision).

Previously:

P88 — Demand Shift Detection by Customer / Region (SPEC Q9) (2026-06-11). New
`detect_demand_shift` tool: period-over-period `customer_orders` quantity comparison
(default last 28d vs prior 28d, contiguous windows; window_days/end_date_offset params),
grouped by customer AND region, growth/decline lists with pct/abs change + top contributing
SKUs, new_activity/full_decline flags, per-list truncated semantics, mandatory missing_data.
Registry 34→35; intents domain_analysis/cross_domain_analysis/decision_support; system
prompt rule 5 (customer/region axis → detect_demand_shift; segment_demand/
compare_demand_periods stay SKU-axis). Two mid-batch fixes from review: truncated flag now
per-list pre-cap (was combined-length false positive), and explicit `end_date_offset=0`
honored (was `0 or 1` coercion — regression test added). Live-verified: CUST-009 growth
50→150, CUST-010 decline 150→50, Kanto region growth. Sign-off PASS (proof-of-execution):
unit 1028 exit 0, canonical integration 16 exit 0, full-DSN integration 95 passed exit 0,
playwright 33/33 exit 0, build 0, lint 0, typecheck 0.

Previously:

P87 — Order-to-Ship Data Domain: Shipment Delay Root Causes (SPEC Q4) (2026-06-11). Alembic
0019 adds `customer_orders` (26 seeded rows) + `shipments` (14 rows) per ADR
2026-06-11-order-to-ship-and-production-data-domains.md; both in `ALLOWED_READ_TABLES`
(+ legacy map "orders"→customer_orders, regex-safe vs supply_orders). Deterministic seeded
scenarios: CO-0001/2 inventory_shortage (SKU-002/004 in new NO_OPEN_SUPPLY_SKUS), CO-0003/4
upstream_supply_delay (overdue, supply at today+10), CO-0005/6 warehouse delay, CO-0007/8
carrier delay, CO-DS01..08 demand-shift signal for P88 (CUST-009 Kanto growth / CUST-010
Kansai decline; status=shipped, no shipments rows — excluded from delay tools by INNER JOIN).
New tools `list_unshipped_orders` + `analyze_shipment_delay_causes` (precedence: no-snapshot
unknown > stock-present unknown > upstream_supply_delay [open supply arriving late] >
inventory_shortage [no open supply]); `list_today_exceptions` gained fifth screen
unshipped_orders (registry 32→34). Mid-batch fix: original precedence made
upstream_supply_delay unreachable + CO-0003/4 weren't overdue — seed and tool realigned, all
four cause classes live-verified non-zero, P84 risk bands intact (2 critical/2 high/3
medium). Sign-off PASS (proof-of-execution): unit 990 exit 0, canonical integration 16
passed exit 0 (full-DSN run during B-03: 82 passed, 4 skipped, exit 0 — includes the 18 new
P87 integration tests), playwright 33/33 exit 0, build 0, lint 0, typecheck 0.

Previously:

P86 — Today's Exceptions Screening Tool (SPEC Q3) (2026-06-11). New `list_today_exceptions`
tool (read_only, deterministic) aggregates four screens — stockout risk critical/high,
delayed inbound supply, recent demand anomalies (7d), data quality issues (via
`catalog_repo.get_null_profile`, no f-string SQL after batch-check fix) — into one
severity-ranked exception list (cap 50 + `truncated`, mandatory `missing_data`). Wired into
all five `_INTENT_TOOL_SUBSET` intents (registry 31→32) + system prompt rule (call once,
never loop detectors); ToolScenarioModal "Daily Exception Review" scenario added. 23 new
unit tests. Sign-off PASS (proof-of-execution): unit 957 passed exit 0, integration 16
passed exit 0, playwright 33/33 exit 0, build 0, lint 0, typecheck 0.

Previously:

P85 — Agents & Tools Registry: Tool Execution Stats Restoration (2026-06-11). Tools tab on `/agents` was frozen since P20 (commit d0977b8, 2026-06-03) removed the `tool_completed` SSE event: the admin registry query still aggregated the dead event type, AND the replacement tool `graph_node` events were put directly on the raw SSE queue by `AgentRuntime`, bypassing `SessionOrchestrator._push`/`_event_persister` — streamed live, never written to `session_events`. Fixed: new `_emit(event, sse_queue, persister)` helper in `runtime.py` routes tool start/end, `awaiting_approval`, and `session_paused` events to both the queue and the persister (passed via graph `configurable["event_persister"]` at all three config-build sites); `get_registry` tool stats now aggregate `graph_node` kind=tool event=end rows by `payload->>'name'`. D-009 registered+Resolved during sign-off (pre-existing, NOT P85: two ask_user integration tests latent-broken since P78 deterministic routing — stub registries lacked a control-role model; reproduced at baseline d05b122; test-side fix). FP-003 Count → 3 (D-001, D-002, D-009): /harden-system FP-003 required before next phase. Sign-off PASS (proof-of-execution): unit 930 passed exit 0, lint 0, typecheck 0, integration 16 passed exit 0, build 0, playwright 32/32 exit 0. Live verification deferred to user (curl POST denied): run any tool-calling query in the UI, then check /agents Tools tab.

Previously:

P84 — Demo Data Risk Distribution Fix (2026-06-10). `SKU_RISK_BANDS` in `scripts/generate_sample_data.py` assigns deterministic days-of-cover to SKU-001..007 so the demo query "Which products are at stockout risk this week?" returns 2 critical + 2 high + 3 medium SKUs; supply orders for risk SKUs pushed to today+10 so incoming supply cannot rescue the classification. Fix iteration (same day): initial implementation used nominal `base_demand_mean` for on_hand, but `list_stockout_risk` uses the actual 30-day rolling average — seasonal noise pushed SKU-005/006 into "low". Corrected with `compute_recent_avg` helper (mirrors the tool SQL); `generate_demand_history` returns per-SKU recent averages; `generate_inventory` uses `round(actual_avg * DOC)`. Sign-off PASS (proof-of-execution): unit 921 passed exit 0, lint 0, typecheck 0; DB reseeded and live tool verified `count=7` with ratios critical −0.72, high 0.057/0.078, medium 0.287–0.293.

Previously:

P83 — LLM Usage Recording Restoration (2026-06-10). The P54 LangChain migration (commit ccfdb54) orphaned `_real_usage_writer` (`apps/api/state.py`) — no LLM call wrote `llm_usage` since 2026-06-07, leaving `GET /sessions/{id}/usage`, admin `list_llm_usage`, and the web `/llm-calls` and `/usage` pages without new data. Restored via `UsageRecordingCallbackHandler` (LangChain `AsyncCallbackHandler`, new `packages/agent/llm/usage_recording.py`) attached to every ChatModel in `create_model_registry(usage_writer=...)`; captures model, token counts (incl. cache details), prompt/response/tool-calls JSON, latency (logged); call context (session_id / agent_step_id / specialist_role) flows via invoke `config.metadata`; `_real_usage_writer` creates a fallback `agent_steps` row (`make_step(step_type="llm_call")`) when no step id is provided so session totals keep joining; `classify_intent` no longer discards its step id. `UsageWriter` signature unchanged — no ADR. Anthropic cost computation deferred (tokens recorded; cost 0.0). 30 new unit tests. Sign-off PASS (proof-of-execution): unit 921 passed exit 0, lint 0, typecheck 0, build 0, playwright 32/32.

Previously:

P82 — Seed Data Staleness & list_stockout_risk missing_data Fix (2026-06-10). ROOT CAUSE FIX: `START_DATE = date(2025, 1, 1)` in `scripts/generate_sample_data.py` made all demand_history rows fall outside the tools' 30-day rolling window after 2026-01-01 → `avg_daily=0` for all 30 SKUs → `list_stockout_risk` always returned `count=0`. Fixed: `START_DATE` and all supply/inventory/cost fixed dates are now relative to `date.today()`. `list_stockout_risk` now populates `missing_data` per SKU when `avg_daily == 0` (matching `calculate_stockout_risk` convention). 3 new unit tests added: all-zero-demand (count=0 + all SKUs in missing_data), mixed-demand (zero-demand SKUs in missing_data only), and parametrized mixed case.

Previously:

P81 — Tool Scenario Modal Content Refresh (2026-06-10). Fixed 9 broken + 3 partial scenarios in ToolScenarioModal.tsx: inventory→inventory_snapshot table names; DC West→WH-001/WH-002 real seed locations; forecast tool rewritten for sku_id+horizon_days only (no location param); train-model scenario removed (train_forecast not LLM-callable); sc-order-delay rewritten (#ORD-1042 unresolvable); Job Dispatch (HITL) category removed (job_dispatch not LLM-callable per P64 registry); sql scenario retitled "Natural Language Query" (P55 removed sql_query; nl_query is sole Text2SQL); all prompts standardized to English (AGENTS.md §Language Convention). Playwright spec updated (5 categories, English prompt assertions). Sign-off PASS: unit 874 passed exit 0, lint 0, typecheck 0, build 0, playwright 32/32.

Previously:

P80 — Verifier Blocked-Path UX (2026-06-10). D-008 Resolved: truthful `blocked_reason` per blocking site (the "tool-loop guard" default was always misattributed — that path never sets blocked); verifier blocks soft-fail to the fallback text as a completed reply with `verification.blocked_reason` meta (no agent_failed SSE); Rule 1 strips code fences/inline code before the fabrication regex (SQL answers no longer fail the digit lottery). Sign-off PASS: unit 874 passed exit 0, lint 0, typecheck 0, build 0, playwright 32/32. Live verification: the exact 22:47 UTC failing query now returns a real SQL answer; 0 agent_failed in logs; concurrent user session also answered. FP-009 recorded (record-only).

Previously:

P79 — Session Resume & Lifecycle Robustness (2026-06-10). D-006 Resolved: `answer_ask_user`/`resume` guarded by `has_pending_interrupt()` (`graph.aget_state`); missing checkpoint or no pending interrupt → typed `NoPendingInterruptError`, router returns 409 (no graph start from empty state, no LLM burn); `_node_classify_intent` hardened against bare KeyError. D-007 Resolved: session deletion cancels in-flight background runs via `session_tasks` handle registry + tombstone set (`_deleted_session_ids`) stops event persistence; `get_or_recover_session` shared helper gives `update_session_title`/`get_messages`/`set_message_feedback`/`submit_ask_user_answer` the same DB recovery as `post_message`; FK-violation event-persist logs downgraded to debug. Sign-off PASS (proof-of-execution): unit 867 passed exit 0, lint 0, typecheck 0, build 0, playwright 32/32. FP-007/FP-008 recorded (both record-only; no pattern at Count >= 2). Defects originated from live runtime diagnosis of the 2026-06-10 19:01 JST-3 user session error (root cause of THAT error was a uvicorn --reload restart during an in-flight run, triggered by P77 fix edits to bind-mounted apps/api — D-006/D-007 were the latent defects it exposed).

Previously:

P78 — Deterministic Routing Completion (2026-06-10). D-005 Resolved: `select_execution_mode` builds `AgentRoute` deterministically for all intents (no LLM call; `ROUTER_SYSTEM` deleted); one LLM round-trip saved per non-supply_chain request. Sign-off PASS: unit 848 passed exit 0, lint 0, typecheck 0, build 0, playwright 32/32. Live verification: the exact failing query (lookup intent) now completes — steps intent_classification → routing → specialist_execution, assistant reply produced, 0 routing errors. FP-006 recorded (record-only).

Previously:

P77 — Runtime Error Surfacing Fixes (2026-06-10). D-004 Resolved: approvals router responses wrapped in `jsonable_encoder` (4 sites); regression tests added; web `ApiError` class distinguishes HTTP business errors (404 session-not-found message) from network failures. Sign-off PASS: unit 828 passed exit 0, lint 0, typecheck 0, build 0, playwright 32/32 (job_approval deterministic — P76's "flaky" was D-004, not SSE timing). FP-005 recorded (record-only).

Previously:

P76 — Tool Layer Conformance Remediation (2026-06-10). Hybrid tool output contract implemented per ADR 2026-06-10-tool-output-contract-hybrid: `missing_data` on all DB tools; LIMIT+truncated on supply order tools; shared helpers `_shared.py`; evaluator fail-loud; data_catalog_search error key; DOS→DOI merge (registry 32→31, DOI gains stockout_date_estimate); DESIGN.md/AGENT_ARCHITECTURE.md/TOOLS.md amended. Sign-off PASS (proof-of-execution): unit 826 passed exit 0; lint exit 0; typecheck exit 0 (160 files); full-DSN integration 61 passed exit 0; build exit 0; playwright 31 passed + 1 pre-existing flaky exit 0. No defects.

Previously: P75 — Tool Layer Full Audit (2026-06-10): read-only audit of all 35 tool files. Verdicts: 30 keep / 1 merge-candidate (DOS→DOI) / 4 boundary-unclear; no tool deleted. Conformance: Tool Protocol 35/35; Context Pack contract 0/35 (doc-vs-code divergence → ADR in P76/T-477); `nl_query` returns raw rows; `missing_data` never populated. Implementation: SQL parameterization 35/35 clean; `evaluator_tool` silent config fallback (→T-478); unbounded supply-order queries (→T-479); copy-paste helpers (→T-480). Tests: 34/35 dedicated behavioral coverage (`train_forecast` indirect-only →T-482); proof: unit 795 passed exit 0, full-DSN integration 61 passed exit 0. Follow-up registered as P76 (Not Started, awaiting user prioritization). Verdict: 30 keep / 1 merge-candidate (`calculate_days_of_supply` → `calculate_days_of_inventory`; identical formula, DOI is warehouse-aware superset) / 4 boundary-unclear (`calculate_stockout_risk` vs `list_stockout_risk` copy-paste thresholds; `get_open_supply_orders`, `get_delayed_supply_orders`, `compare_demand_periods` thin-wrapper vs nl_query). Copy-paste maintenance risks: `_classify_stockout_risk` duplicated (high), `_db_error_message` duplicated in ~16 files (medium). Unregistered 3 tools all have real consumers — keep.

Previously: P75-B-01 — Static conformance + implementation quality audit (2026-06-10). Key findings: Context Pack contract implemented by 0/35 tools (systemic doc-vs-code gap); `nl_query` returns raw rows; `missing_data` never populated; `evaluator_tool` silent fallback on missing `risk_thresholds.yaml`; open/delayed supply order queries unbounded (no LIMIT); 28 DB tools share a broad-except pattern. SQL parameterization 35/35 clean; no hardcoded schema strings; LLM calls via model layer.

Previously: P74 — Integration Tier Latent Debt (2026-06-10): all 14 latent failures fixed test-side (no production bugs); full-DSN integration 61 passed/0 failed; canonical 16 passed/0 failed; build exit 0.

Previously: P71–P73 — Autonomy Loops programme (2026-06-10). Sign-off PASS: unit 795 passed, canonical integration 16 passed/0 failed (full-DSN 47 passed; 14 latent pre-existing failures tracked as P74/T-470), build exit 0, playwright 32/32. ADR: 2026-06-10-autonomy-loops. D-003 Resolved (FP-004, record-only). Goal loop (set_goal/evaluate_goal + 1 bounded refinement + intent re-route), grounded verification (revision path reconnected), feedback learning (decision_log.outcome → context annotation).

## Blockers

None
