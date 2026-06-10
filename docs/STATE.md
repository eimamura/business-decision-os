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

P78 — Deterministic Routing Completion

## Active Lease

P78-B-01

## Last Completed

P77 — Runtime Error Surfacing Fixes (2026-06-10). D-004 Resolved: approvals router responses wrapped in `jsonable_encoder` (4 sites); regression tests added; web `ApiError` class distinguishes HTTP business errors (404 session-not-found message) from network failures. Sign-off PASS: unit 828 passed exit 0, lint 0, typecheck 0, build 0, playwright 32/32 (job_approval deterministic — P76's "flaky" was D-004, not SSE timing). FP-005 recorded (record-only).

Previously:

P76 — Tool Layer Conformance Remediation (2026-06-10). Hybrid tool output contract implemented per ADR 2026-06-10-tool-output-contract-hybrid: `missing_data` on all DB tools; LIMIT+truncated on supply order tools; shared helpers `_shared.py`; evaluator fail-loud; data_catalog_search error key; DOS→DOI merge (registry 32→31, DOI gains stockout_date_estimate); DESIGN.md/AGENT_ARCHITECTURE.md/TOOLS.md amended. Sign-off PASS (proof-of-execution): unit 826 passed exit 0; lint exit 0; typecheck exit 0 (160 files); full-DSN integration 61 passed exit 0; build exit 0; playwright 31 passed + 1 pre-existing flaky exit 0. No defects.

Previously: P75 — Tool Layer Full Audit (2026-06-10): read-only audit of all 35 tool files. Verdicts: 30 keep / 1 merge-candidate (DOS→DOI) / 4 boundary-unclear; no tool deleted. Conformance: Tool Protocol 35/35; Context Pack contract 0/35 (doc-vs-code divergence → ADR in P76/T-477); `nl_query` returns raw rows; `missing_data` never populated. Implementation: SQL parameterization 35/35 clean; `evaluator_tool` silent config fallback (→T-478); unbounded supply-order queries (→T-479); copy-paste helpers (→T-480). Tests: 34/35 dedicated behavioral coverage (`train_forecast` indirect-only →T-482); proof: unit 795 passed exit 0, full-DSN integration 61 passed exit 0. Follow-up registered as P76 (Not Started, awaiting user prioritization). Verdict: 30 keep / 1 merge-candidate (`calculate_days_of_supply` → `calculate_days_of_inventory`; identical formula, DOI is warehouse-aware superset) / 4 boundary-unclear (`calculate_stockout_risk` vs `list_stockout_risk` copy-paste thresholds; `get_open_supply_orders`, `get_delayed_supply_orders`, `compare_demand_periods` thin-wrapper vs nl_query). Copy-paste maintenance risks: `_classify_stockout_risk` duplicated (high), `_db_error_message` duplicated in ~16 files (medium). Unregistered 3 tools all have real consumers — keep.

Previously: P75-B-01 — Static conformance + implementation quality audit (2026-06-10). Key findings: Context Pack contract implemented by 0/35 tools (systemic doc-vs-code gap); `nl_query` returns raw rows; `missing_data` never populated; `evaluator_tool` silent fallback on missing `risk_thresholds.yaml`; open/delayed supply order queries unbounded (no LIMIT); 28 DB tools share a broad-except pattern. SQL parameterization 35/35 clean; no hardcoded schema strings; LLM calls via model layer.

Previously: P74 — Integration Tier Latent Debt (2026-06-10): all 14 latent failures fixed test-side (no production bugs); full-DSN integration 61 passed/0 failed; canonical 16 passed/0 failed; build exit 0.

Previously: P71–P73 — Autonomy Loops programme (2026-06-10). Sign-off PASS: unit 795 passed, canonical integration 16 passed/0 failed (full-DSN 47 passed; 14 latent pre-existing failures tracked as P74/T-470), build exit 0, playwright 32/32. ADR: 2026-06-10-autonomy-loops. D-003 Resolved (FP-004, record-only). Goal loop (set_goal/evaluate_goal + 1 bounded refinement + intent re-route), grounded verification (revision path reconnected), feedback learning (decision_log.outcome → context annotation).

## Blockers

None
