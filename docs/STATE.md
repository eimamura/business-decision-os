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

P89 — Production Plan & Constraint Analysis (SPEC Q7 / Q10). Programme context:
P86–P89 close the SPEC gaps (Q3 → Q4 → Q9 → Q7/Q10), planned 2026-06-11 via intake; ADR
2026-06-11-order-to-ship-and-production-data-domains.md covers P87/P89 schemas.

## Active Lease

P89 B-01 (App Builder) — acquired 2026-06-11

## Last Completed

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
