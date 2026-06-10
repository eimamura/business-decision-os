# TASKS.md

## Goal

Incrementally build and stabilize the Business Decision OS agent system — eliminating AGENTS.md
violations, closing architectural gaps, and extending capabilities through well-tested phases.

Full task history for P0–P23 is archived at `docs/archive/v3/TASKS.md`.

---

## Completed Phases (Summary)

| Phase | Tasks | Completed |
|---|---|---|
| P0 — Prohibited Violation | T-001 | 2026-06-02 |
| P1–P3 — Domain Integrity, Access Control, Observability | T-002–T-029 | 2026-06-02 |
| P4 — Job Execution & HITL Flow | T-030–T-039 | 2026-06-02 |
| P5 — Test Infrastructure & Cost Reduction | T-040–T-045 | 2026-06-02 |
| P6 — Chat UI Stability | T-046–T-054 | 2026-06-02 |
| P7 — CI Quality & Memory Loop Validation | T-055–T-058 | 2026-06-02 |
| P8 — Mock Mode for Cost-Free UI Testing | T-059–T-062 | 2026-06-02 |
| P9 — LangGraph Migration | T-063–T-075 | 2026-06-02 |
| P10 — Web UI Server State Standardisation | T-076–T-082 | 2026-06-03 |
| P11 — AskUser: Pre-execution Information Gathering | T-083–T-085 | 2026-06-03 |
| P12 — Test Session Pollution Fix | T-086–T-087 | 2026-06-03 |
| P13 — AskUser: interrupt()-based Mid-Execution Gathering | T-088–T-099 | 2026-06-03 |
| P14 — Agent Node Cards | T-100–T-108 | 2026-06-03 |
| P15 — Text Streaming / text_delta SSE | T-109–T-116 | 2026-06-03 |
| P16 — Backward Compat Removal | T-117–T-119 | 2026-06-03 |
| P17 — Orchestrator Cost Reduction | T-120–T-123 | 2026-06-03 |
| P18 — Tool Scenario Coverage | T-124 | 2026-06-03 |
| P19 — SSE Consumer Consolidation | T-125–T-127 | 2026-06-03 |
| P20 — LangGraph-Native SSE Pipeline Rebuild | T-128–T-134 | 2026-06-03 |
| P21 — Chat Bubble Component Refactor | T-135–T-138 | 2026-06-03 |
| P22 — Test Coverage Gaps | T-139–T-140 | 2026-06-03 |
| P23 — Test Suite Rationalization | T-141–T-146 | 2026-06-03 |
| P24 — Ollama Local LLM Provider | T-147–T-152 | 2026-06-04 |
| P25 — Tool Scenario E2E Validation & Session Cleanup | T-153–T-159 | 2026-06-04 |
| P26 — SSE/Broadcaster Bug Fixes | T-160–T-166 | 2026-06-04 |
| P27 — Model Name in Execution Trace Nodes | T-167–T-171 | 2026-06-04 |
| P28 — Real-time Execution Trace & Persistence Recovery | T-172–T-178 | 2026-06-04 |
| P29–P31 — Goal-Based Agent, Forecasting & Demand Analysis | T-179–T-209 | 2026-06-04 |
| P32 — Supply Planning Agent | T-210–T-223 | 2026-06-04 |
| P33 — Finance Impact Agent | T-224–T-234 | 2026-06-04 |
| P34 — Inventory Agent Enhancement | T-235–T-243 | 2026-06-04 |
| P35 — S&OP Agent & Orchestration | T-244–T-251 | 2026-06-04 |
| P36 — Tool Scenario Prompts for S&OP Agents | T-252–T-257 | 2026-06-04 |
| P37 — Playwright E2E: Remove Mocks, Consolidate | T-258–T-265 | 2026-06-05 |
| P38 — Architecture Realignment | T-266–T-271 | 2026-06-06 |
| P44 — Playwright Tests: Revert to Mock SSE | T-311–T-317 | 2026-06-06 |
| P39 — Supply Chain Control Agent (MVP Core) | T-273–T-280 | 2026-06-06 |
| P45 — Control-Agent-Only Routing | T-318–T-324 | 2026-06-06 |
| P40 — Skill Registry | T-281–T-289 | 2026-06-06 |
| P41 — Memory Layer | T-290–T-298 | 2026-06-06 |
| P42 — Context Engineering Integration | T-299–T-304 | 2026-06-06 |
| P43 — MVP Validation (3 Questions) | T-305–T-310 | 2026-06-06 |
| P46 — Skill & Tool Enrichment | T-325–T-330 | 2026-06-06 |
| P47 — Long-Term Memory Physical Implementation | T-331–T-335 | 2026-06-06 |
| P48 — LongTermMemory Integration + Test Accuracy Fix | T-336–T-339 | 2026-06-06 |
| P50 — LLM Response Normalization Layer | T-343–T-347 | 2026-06-07 |
| P51 — Qwen3 Thinking Disable for Structured Output Calls | T-348–T-352 | 2026-06-07 |
| P56 — nl_query クリーンアップ後処理 | T-363–T-369 | 2026-06-07 |
| P57 — nl_query 品質強化 | T-370–T-375 | 2026-06-07 |
| P59 — Control Agent Degenerate Response Guard | T-383–T-387 | 2026-06-07 |
| P60 — Control Agent Tool-Loop Guard | T-388–T-394 | 2026-06-07 |
| P61 — Quality Hardening: Degenerate Guard / Rule-Based Verifier | T-395–T-400 | 2026-06-07 |
| P62 — ControlAgent Groundedness Verifier Rule 1b | T-401–T-406 | 2026-06-07 |
| P63 — ControlAgent Intent-to-Tool Subset Alignment | T-407 (B-01 only) | 2026-06-07 |
| P64 — Agent Architecture Gap Closure (5 Gaps) | T-407–T-420 | 2026-06-10 |

> **Design Realignment Note (2026-06-05):** P29–P36 built Specialist Domain Agents (DemandAgent,
> InventoryAgent, SupplyPlanningAgent, FinanceImpactAgent, SopAgent) as independent runtime units.
> The DESIGN.md refresh (ADR: `docs/adr/2026-06-05-integrated-control-agent-first.md`) specifies
> that in MVP, Specialist Agents exist as **Skill files only (Level 2)** — not runtime units.
> The **domain tools** created in P31–P34 (calculation, analysis, gap tools) remain valid and will
> be accessed by the Supply Chain Control Agent via the Tool Gateway. The agent runtime classes
> will be retired in P38.

---

## P24 — Ollama Local LLM Provider

**Goal:** Add `OllamaClient` behind `LLM_PROVIDER=ollama` so developers can use qwen2.5-coder:7b locally without Anthropic API costs. `LLMClient` protocol signature is unchanged.

### Batch B-01 — OllamaClient + env config (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-147 | ADR docs/adr/2026-06-04-ollama-local-llm-provider.md | Done |
| T-148 | OllamaClient class in packages/agent/llm/__init__.py | Done |
| T-149 | create_llm_client() LLM_PROVIDER=ollama branch | Done |
| T-150 | .env.example: LLM_PROVIDER, OLLAMA_BASE_URL, OLLAMA_MODEL | Done |

Dependencies: none

### Batch B-02 — Tests (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-151 | OllamaClient unit tests (mock httpx) | Done |
| T-152 | Existing unit tests pass | Done |

Dependencies: B-01

---

## P25 — Tool Scenario E2E Validation & Playwright Session Cleanup

**Goal:** Close test session pollution from Playwright tests that never clean up DB rows, and verify that all 20 tool scenario prompts produce a visible, non-empty chat bubble in the UI through mocked-SSE E2E tests and integration tests.

### Batch B-01 — Playwright Session Auto-Cleanup (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-153 | Create `tests/e2e/playwright/fixtures.ts` — `testWithCleanup` fixture that tracks session IDs and calls `DELETE /api/v1/sessions/{id}` in afterEach | Done |
| T-154 | Migrate all session-creating Playwright specs (`chat_flow.spec.ts`, `ask_user_flow.spec.ts`, `job_approval.spec.ts`) to use `testWithCleanup` | Done |

Dependencies: none

### Batch B-02 — Tool Scenario Modal & Chat Bubble Playwright Tests (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-155 | `tool_scenario_modal.spec.ts` — verify modal opens, 5 category tabs visible, clicking a scenario card fills textarea with the prompt and closes modal | Done |
| T-156 | `tool_scenario_bubbles_mock.spec.ts` — mocked SSE (no backend) test verifying each category produces a non-empty assistant bubble (no error bubble, no empty bubble) | Done |
| T-157 | `hitl_scenario_bubbles_mock.spec.ts` — Ask User full cycle (question bubble → answer → result bubble) + Job Dispatch (approval card → approve → status change) using mocked SSE | Done |

Dependencies: B-01

### Batch B-03 — Integration Test Coverage Gaps (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-158 | `tests/integration/test_scenario_coverage.py` — integration tests for catalog / schema / quality / multi-SKU forecast / scenario-comparison intents using mock LLM | Done |
| T-159 | Integration tests for all 6 Ask User HITL modal variants (vague→ask, fully-specified→no ask, warehouse given→ask, SKU-no-period→ask, etc.) | Done |

Dependencies: none (parallel-eligible with B-02)

---

## P26 — SSE/Broadcaster Bug Fixes

**Goal:** 調査で発見した SSE/Broadcaster 周辺の5件の潜在バグ（メモリリーク・エラー時ハング・abort競合・UI更新漏れ）をすべて修正し、ユニットテストで保護する。

### Batch B-01 — Backend quick fixes: memory leak + error-path done + SSE error break (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-160 | `delete_session` / `delete_all_sessions` で `broadcasters` / `broadcaster_ready` をクリーンアップ | Done |
| T-161 | `_run_resume_and_signal` の finally で response が None でも常に `done` を送信 | Done |
| T-162 | SSE `event_generator` の break 条件に `"error"` を追加 | Done |

Dependencies: none

### Batch B-02 — Backend abort race: stale run silently dropped (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-163 | `state.py` に `session_run_ids: dict[str, str]` を追加し、`POST /messages` の `_run_and_signal` 内の各 `queue.put()` 前に run_id チェックを実施。セッション削除時にも run_id をクリーンアップ | Done |

Dependencies: B-01

### Batch B-03 — Frontend: sendAskUserAnswer missing invalidateQueries (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-164 | `sendAskUserAnswer` の `done` ハンドラに `queryClient.invalidateQueries({ queryKey: queryKeys.sessions.all })` を追加 | Done |

Dependencies: none

### Batch B-04 — Tests (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-165 | broadcaster cleanup・run_id stale drop・SSE error break に対するユニットテスト | Done |
| T-166 | 既存ユニットテスト全通過確認（`make test-unit`） | Done |

Dependencies: B-01, B-02, B-03

---

## P27 — Model Name in Execution Trace Nodes

**Goal:** Include `model_name` in `meta` of every orchestrator/agent `graph_node` SSE event, and render a small model badge per node in the ExecutionPanel side panel.

### Batch B-01 — Backend: emit model_name in graph_node meta (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-167 | `session_orchestrator.py`: add `model_name` to `meta` in orchestrator-level graph_node start/end events via `getattr(_llm_client, "_orchestrator_model", None) or getattr(_llm_client, "_model", None)` | Done |
| T-168 | `runtime.py` `_run_agent()`: add `model_name` to `meta` in agent-level graph_node start/end events via `getattr(orchestrator._llm_client, "_model", None)` | Done |

Dependencies: none

### Batch B-02 — Frontend: display model name in ExecutionPanel (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-169 | `ExecutionPanel.tsx`: for orchestrator/agent kind nodes, render `meta.model_name` as a small monospace badge below the node label when present | Done |

Dependencies: B-01

### Batch B-03 — Tests (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-170 | Unit test: `_run_agent` includes `model_name` in agent graph_node meta | Done |
| T-171 | Vitest: `ExecutionPanel` renders model badge when `meta.model_name` is set | Done |

Dependencies: B-01, B-02

---

## P28 — Real-time Execution Trace & Persistence Recovery

**Goal:** Fix a race condition that causes early graph_node SSE events to be silently dropped before the SSE subscriber is registered, resulting in an incomplete execution trace in ExecutionPanel. Also fix missing `response_ready` emission in non-direct-chat execution paths, and verify that execution trace is restored from DB on page refresh or navigation.

### Batch B-01 — Backend: Broadcaster replay buffer + response_ready fix (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-172 | Add `_buffer: list[dict]` to `Broadcaster` in `apps/api/state.py`; on `subscribe()`, replay buffered events into the new subscriber's queue; clear buffer on terminal event (`done`, `error`, `awaiting_input`) delivered via `put()` | Done |
| T-173 | Emit `response_ready` at the end of `_node_run_sequential`, `_node_run_planned`, and `_node_run_dag` in `session_orchestrator.py` — mirrors what `run_direct_chat` already does | Done |

Dependencies: none

### Batch B-02 — Frontend: Restore execution trace on navigation/refresh (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-174 | In `loadMessages()` (`ChatStateContext.tsx`): decouple event hydration from the `isSendingRef.current` guard — call `fetchSessionEvents()` unconditionally (even when `isSending` is true) so that navigating back to an active session restores the partial trace from DB | Done |
| T-175 | In `sendAskUserAnswer()` (`ChatStateContext.tsx`): do NOT clear `graphRun` when resuming from an ask_user interrupt — the existing trace from the first half of execution should remain visible; only clear it when `sendMessage()` starts a fresh conversation turn | Done |

Dependencies: none (parallel-eligible with B-01)

### Batch B-03 — Tests (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-176 | Unit test: `Broadcaster` replay buffer delivers buffered events to a late subscriber; buffer is cleared after terminal event | Done |
| T-177 | Unit test: `_node_run_sequential` emits `response_ready` SSE event via `orchestrator._push` | Done |
| T-178 | Existing unit tests pass (`make test-unit`) | Done |

Dependencies: B-01, B-02

---

## P29 — LLM Call Prompt/Response Persistence

**Goal:** Store prompt messages, response text, and tool calls in `llm_usage` for post-hoc inspection; covers both `ClaudeClient` and `OllamaClient`.

### Batch B-01 — DB migration: add prompt/response columns (Infra) — Done

| Task | Description | Status |
|---|---|---|
| T-179 | Alembic migration `0015_llm_usage_prompt_response.py` — add `prompt_messages_json TEXT`, `response_text TEXT`, `tool_calls_json TEXT` (all nullable) to `llm_usage` | Done |

Dependencies: none

### Batch B-02 — Persistence + LLM clients (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-180 | `LLMUsage` Pydantic model: add optional fields `prompt_messages_json: str \| None = None`, `response_text: str \| None = None`, `tool_calls_json: str \| None = None` | Done |
| T-181 | `LlmUsageRepository.create()` — accept and store the 3 new optional fields in the INSERT | Done |
| T-182 | `ClaudeClient.complete()` — serialize `messages` → `prompt_messages_json`, `response.text` → `response_text`, `response.tool_calls` → `tool_calls_json`; populate `LLMUsage` fields before calling `usage_writer` | Done |
| T-183 | `OllamaClient.complete()` — same as T-182 (ensures Ollama parity) | Done |
| T-184 | `_real_usage_writer` in `apps/api/state.py` — pass `usage.prompt_messages_json`, `usage.response_text`, `usage.tool_calls_json` to `repo.create()` | Done |

Dependencies: B-01

### Batch B-03 — Tests (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-185 | Unit tests: `ClaudeClient.complete()` and `OllamaClient.complete()` populate the 3 new `LLMUsage` fields; `LlmUsageRepository.create()` stores them (mock DB) | Done |
| T-186 | Existing unit tests pass (`make test-unit`) | Done |

Dependencies: B-02

---

## P30 — AgentRuntime execute_tools Unit Tests

**Goal:** `AgentRuntime` の `execute_tools` ノードで LLM が `tool_call` を返した際にツールの `handle()` が実際に呼ばれ、結果が次の LLM 呼び出しにフィードバックされることをユニットテストで保護する。

### Batch B-01 — Tests (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-187 | `tests/unit/helpers.py` に `make_tool_call_response()` ヘルパーを追加 | Done |
| T-188 | execute_tools パス: LLM が tool_call → `handle()` 呼び出し → ツール結果が `tool` role メッセージとして次の LLM 呼び出しに送られる | Done |
| T-189 | ツールが ToolRegistry に見つからない場合はスキップ | Done |
| T-190 | ツール実行が例外を投げた場合は例外が伝播する | Done |
| T-191 | `make test-unit` 全通過確認 | Done |

Dependencies: none

---

## P31 — Demand Agent: Data Analysis Layer

**Goal:** Extend the Demand Agent from a forecast-only agent to a full data-analysis-capable agent by adding 8 new analysis tools (4 must-have, 4 next-tier), wiring them into the registry and allowlist, and updating the system prompt to guide analysis-first behavior.

### Batch B-01 — Must-have analysis tools (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-192 | `DemandProfileTool` — `packages/tools/demand_profile_tool.py`: `profile_demand_data(sku_id?, lookback_days)` → data quality metrics (missing_rate, zero_demand_days, stockout_suspected_days, mean, std, cv, data_quality_score) | Done |
| T-193 | `DemandTrendTool` — `packages/tools/demand_trend_tool.py`: `analyze_demand_trend(sku_id, lookback_days, granularity)` → trend_direction, trend_slope, r_squared, period_over_period_growth, peak/trough_period, periods list | Done |
| T-194 | `ForecastAccuracyTool` — `packages/tools/forecast_accuracy_tool.py`: `evaluate_forecast_accuracy(sku_id, lookback_days)` → mape, wape, bias, coverage, sample_size, worst_period | Done |
| T-195 | `DemandAnomalyTool` — `packages/tools/demand_anomaly_tool.py`: `detect_demand_anomalies(sku_id, lookback_days, z_threshold)` → anomaly_count, anomalies list with date/quantity/z_score/anomaly_type | Done |

Dependencies: none

### Batch B-02 — Next-tier analysis tools (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-196 | `DemandSeasonalityTool` — `packages/tools/demand_seasonality_tool.py`: `analyze_seasonality(sku_id, lookback_days)` → has_weekly_pattern, has_monthly_pattern, peak_periods, trough_periods, seasonality_index | Done |
| T-197 | `DemandDriversTool` — `packages/tools/demand_drivers_tool.py`: `analyze_demand_drivers(sku_id, lookback_days)` → top_customers with demand_share/trend, customer_concentration, sku_risk_level | Done |
| T-198 | `DemandSegmentTool` — `packages/tools/demand_segment_tool.py`: `segment_demand(dimension, lookback_days, top_n)` → segments list with total_qty, demand_share, trend_direction, cv | Done |
| T-199 | `DemandCompareTool` — `packages/tools/demand_compare_tool.py`: `compare_demand_periods(sku_id?, period_a, period_b)` → totals, change_pct, change_units, daily_avg per period | Done |

Dependencies: none (parallel-eligible with B-01)

### Batch B-03 — Registry + allowlist + agent wiring + TOOLS.md (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-200 | Register all 8 new tools in `create_tool_registry()` in `packages/tools/__init__.py` | Done |
| T-201 | Extend `_ROLE_TOOL_ALLOWLIST["demand"]` in `packages/tools/base.py` to include all 8 new tool names | Done |
| T-202 | Rewrite `_SYSTEM_PROMPT` in `packages/agent/domain/demand.py` — 4 sections: Responsibilities, TOOL USE RULES (analysis-first), Available tables, Output format | Done |
| T-203 | Update `docs/TOOLS.md` — add specs for 8 new tools; update demand role allowlist table | Done |

Dependencies: B-01, B-02

### Batch B-04 — Unit tests (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-204 | Unit tests for `DemandProfileTool` — missing_rate calc, cv calc, data_quality_score, sku_id=None path (mock DB) | Done |
| T-205 | Unit tests for `DemandTrendTool` — slope direction, period aggregation, granularity switch (mock DB) | Done |
| T-206 | Unit tests for `ForecastAccuracyTool` — mape=None on zero-demand, wape calc, bias sign, worst_period detection (mock DB) | Done |
| T-207 | Unit tests for `DemandAnomalyTool` — spike/drop/stockout/missing types, z_threshold boundary (mock DB) | Done |
| T-208 | Unit tests for next-tier tools: seasonality index, driver concentration, segment share sum=1, period compare change_pct (mock DB) | Done |
| T-209 | `make test-unit` full pass + `make lint` + `make typecheck` | Done |

Dependencies: B-01, B-02, B-03

---

## P32 — Supply Planning Agent

**Goal:** Add `SupplyPlanningAgent` domain agent with 5 supply analysis tools that assess supply feasibility against demand forecasts using existing `supply_orders`, `inventory_snapshot`, and `demand_history` tables.

### Batch B-01 — SupplyPlanningAgent class + supply analysis tools (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-210 | `SupplyPlanningAgent` — `packages/agent/domain/supply_planning.py`: role="supply_planning", system prompt covering supply gap analysis, lead time, supplier risk; analysis-first like DemandAgent | Done |
| T-211 | `GetOpenSupplyOrdersTool` — `packages/tools/supply_open_orders_tool.py`: `get_open_supply_orders(sku_id?, status_filter)` → orders list with sku_id, supplier_id, quantity, expected_arrival, days_until_arrival | Done |
| T-212 | `CalculateSupplyGapTool` — `packages/tools/supply_gap_tool.py`: `calculate_supply_gap(sku_id, horizon_days)` → on_hand, incoming_qty, forecast_demand, gap_units, gap_pct, risk_level (low/medium/high) | Done |
| T-213 | `AnalyzeSupplyLeadTimeTool` — `packages/tools/supply_lead_time_tool.py`: `analyze_supply_lead_time(sku_id?, lookback_days)` → avg_lead_time_days, min_lead_time_days, max_lead_time_days, lead_time_std, supplier_count | Done |
| T-214 | `CalculateDaysOfSupplyTool` — `packages/tools/supply_days_tool.py`: `calculate_days_of_supply(sku_id)` → on_hand_qty, avg_daily_demand, days_of_supply, stockout_date_estimate | Done |
| T-215 | `AnalyzeSupplyRiskTool` — `packages/tools/supply_risk_tool.py`: `analyze_supply_risk(sku_id, horizon_days)` → risk_score (0–1), risk_level, gap_risk, lead_time_risk, concentration_risk (supplier HHI), top_risk_factors list | Done |

Dependencies: none

### Batch B-02 — Wiring + ADR (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-216 | ADR `docs/adr/2026-06-04-sop-specialist-roles.md` — document addition of supply_planning, finance_impact, sop to SpecialistRole Literal and DOMAIN_AGENT_ROLES | Done |
| T-217 | Add `"supply_planning"` to `SpecialistRole` Literal in `packages/agent/base.py`; add to `DOMAIN_AGENT_ROLES` set and `VALID_AGENT_ROLES` in `packages/agent/orchestrator/roles.py`; add `SupplyPlanningAgent` to `packages/agent/domain/__init__.py` `create_domain_agents()` | Done |
| T-218 | Add `"supply_planning"` allowlist in `packages/tools/base.py`: `["sql_query", "nl_query", "get_open_supply_orders", "calculate_supply_gap", "analyze_supply_lead_time", "calculate_days_of_supply", "analyze_supply_risk"]`; register 5 new tools in `packages/tools/__init__.py` `create_tool_registry()` | Done |
| T-219 | Add supply_planning to `"lookup"`, `"domain_analysis"`, `"cross_domain_analysis"` allowed_agent_roles in `packages/agent/orchestrator/intent_registry.py` | Done |

Dependencies: B-01

### Batch B-03 — Unit tests (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-220 | Unit tests for `GetOpenSupplyOrdersTool` — pending orders, empty result, DB error (mock DB) | Done |
| T-221 | Unit tests for `CalculateSupplyGapTool` — shortage detected, surplus detected, zero forecast (mock DB) | Done |
| T-222 | Unit tests for `AnalyzeSupplyLeadTimeTool`, `CalculateDaysOfSupplyTool`, `AnalyzeSupplyRiskTool` (mock DB) | Done |
| T-223 | `make test-unit` + `make lint` + `make typecheck` | Done |

Dependencies: B-01, B-02

---

## P33 — Finance Impact Agent

**Goal:** Add `FinanceImpactAgent` domain agent with 4 cost-impact tools using existing `cost_master` and `inventory_snapshot` tables. Revenue analysis (requiring a price table) is deferred to a future phase.

### Batch B-01 — FinanceImpactAgent class + finance tools (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-224 | `FinanceImpactAgent` — `packages/agent/domain/finance_impact.py`: role="finance_impact", system prompt covering cost impact analysis, holding/stockout/ordering costs, scenario comparison; note revenue analysis requires price data not yet in schema | Done |
| T-225 | `CalculateHoldingCostImpactTool` — `packages/tools/finance_holding_cost_tool.py`: `calculate_holding_cost_impact(sku_id, excess_units)` → unit_holding_cost, total_holding_cost, annualized_holding_cost, holding_cost_pct_of_value | Done |
| T-226 | `CalculateStockoutCostImpactTool` — `packages/tools/finance_stockout_cost_tool.py`: `calculate_stockout_cost_impact(sku_id, shortage_units)` → unit_stockout_cost, total_stockout_cost, opportunity_cost_estimate | Done |
| T-227 | `CalculateExpediteCostTool` — `packages/tools/finance_expedite_cost_tool.py`: `calculate_expedite_cost(sku_id, expedite_units, expedite_multiplier?)` → base_ordering_cost, expedite_premium, total_expedite_cost, cost_vs_stockout_comparison | Done |
| T-228 | `CompareCostScenariosTool` — `packages/tools/finance_scenario_tool.py`: `compare_cost_scenarios(sku_id, shortage_units, horizon_days)` → scenarios list [{name, total_cost, cost_components}] covering: do_nothing, full_expedite, partial_fulfill; recommended_scenario | Done |

Dependencies: none (parallel-eligible with P32 B-01)

### Batch B-02 — Wiring (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-229 | Add `"finance_impact"` to `SpecialistRole` Literal in `packages/agent/base.py`; add to `DOMAIN_AGENT_ROLES`; add `FinanceImpactAgent` to `packages/agent/domain/__init__.py` `create_domain_agents()` | Done |
| T-230 | Add `"finance_impact"` allowlist in `packages/tools/base.py`: `["sql_query", "nl_query", "calculate_holding_cost_impact", "calculate_stockout_cost_impact", "calculate_expedite_cost", "compare_cost_scenarios"]`; register 4 tools in `packages/tools/__init__.py` | Done |
| T-231 | Add finance_impact to `"lookup"`, `"domain_analysis"`, `"cross_domain_analysis"`, `"decision_support"` allowed_agent_roles in `intent_registry.py` | Done |

Dependencies: B-01

### Batch B-03 — Unit tests (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-232 | Unit tests for `CalculateHoldingCostImpactTool` and `CalculateStockoutCostImpactTool` — positive costs, zero excess/shortage, missing cost_master row (mock DB) | Done |
| T-233 | Unit tests for `CalculateExpediteCostTool` and `CompareCostScenariosTool` — expedite premium calc, scenario ordering, recommended_scenario field (mock DB) | Done |
| T-234 | `make test-unit` + `make lint` + `make typecheck` | Done |

Dependencies: B-01, B-02

---

## P34 — Inventory Agent Enhancement

**Goal:** Add 4 inventory calculation tools to InventoryAgent so it can quantify stockout risk, excess inventory, days-of-inventory, and available-to-promise — going beyond raw SQL queries.

### Batch B-01 — Inventory calculation tools (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-235 | `CalculateDaysOfInventoryTool` — `packages/tools/inventory_doi_tool.py`: `calculate_days_of_inventory(sku_id, warehouse_id?)` → on_hand_qty, avg_daily_demand, days_of_inventory, reorder_signal (bool) | Done |
| T-236 | `CalculateStockoutRiskTool` — `packages/tools/inventory_stockout_risk_tool.py`: `calculate_stockout_risk(sku_id, horizon_days)` → on_hand, demand_forecast, incoming_supply, projected_ending_stock, stockout_date_estimate, risk_level | Done |
| T-237 | `CalculateExcessInventoryRiskTool` — `packages/tools/inventory_excess_tool.py`: `calculate_excess_inventory_risk(sku_id, lookback_days?)` → on_hand, avg_daily_demand, excess_units, excess_days, excess_risk_level | Done |
| T-238 | `GetAvailableToPromiseTool` — `packages/tools/inventory_atp_tool.py`: `get_available_to_promise(sku_id, warehouse_id?)` → on_hand, on_order_incoming, atp_units, atp_date_horizon | Done |

Dependencies: none

### Batch B-02 — Wiring + system prompt update (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-239 | Add 4 new tool names to `"inventory"` allowlist in `packages/tools/base.py`; register in `create_tool_registry()` in `packages/tools/__init__.py` | Done |
| T-240 | Update `_SYSTEM_PROMPT` in `packages/agent/domain/inventory.py` — add TOOL USE RULES section naming the 4 new tools; add "call calculate_stockout_risk first for any shortage analysis" instruction | Done |

Dependencies: B-01

### Batch B-03 — Unit tests (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-241 | Unit tests for `CalculateDaysOfInventoryTool` and `GetAvailableToPromiseTool` (mock DB) | Done |
| T-242 | Unit tests for `CalculateStockoutRiskTool` and `CalculateExcessInventoryRiskTool` (mock DB) | Done |
| T-243 | `make test-unit` + `make lint` + `make typecheck` | Done |

Dependencies: B-01, B-02

---

## P35 — S&OP Agent & Orchestration

**Goal:** Add `SopAgent` as the S&OP synthesis agent and a new "sop" intent that routes the SessionOrchestrator through a sequential demand→inventory→supply_planning→finance_impact→sop plan, enabling full S&OP cycle in one session.

### Batch B-01 — SopAgent class + "sop" intent (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-244 | `SopAgent` — `packages/agent/domain/sop.py`: role="sop", system prompt that synthesizes multi-agent outputs into a final S&OP recommendation covering demand/inventory/supply/finance dimensions; outputs structured decision with reason + next_actions | Done |
| T-245 | Add `"sop"` to `SpecialistRole` Literal in `packages/agent/base.py`; add to `DOMAIN_AGENT_ROLES`; add `SopAgent` to `packages/agent/domain/__init__.py` `create_domain_agents()` | Done |
| T-246 | Add `"sop"` allowlist in `packages/tools/base.py`: `["sql_query", "nl_query"]`; update `packages/agent/orchestrator/roles.py` `DOMAIN_AGENT_ROLES` | Done |
| T-247 | Add `"sop"` intent to `INTENT_REGISTRY` in `packages/agent/orchestrator/intent_registry.py` — plan_prompt instructs sequential demand→inventory→supply_planning→finance_impact→sop flow; allowed_agent_roles includes all 5 | Done |

Dependencies: P32 Done, P33 Done, P34 Done

### Batch B-02 — Tests (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-248 | Unit test: `SopAgent` instantiates with role="sop"; `_SYSTEM_PROMPT` references structured recommendation output | Done |
| T-249 | Unit test: `INTENT_REGISTRY["sop"]` exists; `allowed_agent_roles` contains all 5 S&OP agents; `max_tool_calls` ≥ 25 | Done |
| T-250 | Unit test: `SpecialistRole` Literal includes "supply_planning", "finance_impact", "sop"; `DOMAIN_AGENT_ROLES` contains all three | Done |
| T-251 | `make test-unit` + `make lint` + `make typecheck` | Done |

Dependencies: B-01

---

## P36 — Tool Scenario Prompts for S&OP Agents

**Goal:** Add Supply Planning, Finance & Cost, and S&OP scenario categories to the Tool Scenarios modal and 3 quick chips to ToolScenarioBar, exposing the new P32–P35 agents to the demo UI.

### Batch B-01 — ToolScenarioModal + ToolScenarioBar (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-252 | Add `"supply"` category (4 scenarios) to `CATEGORIES` in `apps/web/components/ToolScenarioModal.tsx`: supply gap analysis, lead time review, open orders check, supply risk assessment | Done |
| T-253 | Add `"finance"` category (4 scenarios) to `ToolScenarioModal.tsx`: holding cost analysis, stockout cost impact, expedite cost comparison, cost scenario comparison | Done |
| T-254 | Add `"sop"` category (3 scenarios) to `ToolScenarioModal.tsx`: full S&OP cycle, shortage decision, inventory health check | Done |
| T-255 | Add 3 quick chips (Supply Gap, Cost Scenarios, S&OP) to `apps/web/components/ToolScenarioBar.tsx` | Done |

Dependencies: none

### Batch B-02 — Playwright test update (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-256 | Update `tests/e2e/playwright/tool_scenario_modal.spec.ts` — rename "all 5 category tabs" test, add assertions for Supply Planning, Finance & Cost, S&OP tabs | Done |
| T-257 | `make build` + `npx vitest run` (all checks pass) | Done |

Dependencies: B-01

---

## P37 — Playwright E2E: Remove Mocks, Consolidate

**Goal:** Replace all `page.route()` mock interceptors in Playwright tests with real API + real Ollama backend calls. Delete duplicate mock-only spec files; consolidate their coverage into the surviving real-backend specs.

### Batch B-01 — Delete duplicate mock-only specs (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-258 | Delete `tests/e2e/playwright/ask_user_bubble_mock.spec.ts` — coverage fully subsumed by ask_user_flow.spec.ts after B-02 | Done |
| T-259 | Delete `tests/e2e/playwright/hitl_scenario_bubbles_mock.spec.ts` — ask-user coverage → ask_user_flow.spec.ts; job approval coverage → job_approval.spec.ts | Done |

Dependencies: none

### Batch B-02 — Rewrite HITL tests with real Ollama (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-260 | Rewrite `ask_user_flow.spec.ts` — remove MOCK_LLM/MOCK_ASK_USER requirement; use real Ollama; cover: question bubble appears, chip pre-populates input, submit disabled before selection, answer submission → answered state + assistant reply, fully-specified prompt skips AskUser | Done |
| T-261 | Rewrite `job_approval.spec.ts` — remove RUN_E2E guard (always run); add "awaiting_approval event shows card with action buttons" test (merged from deleted hitl spec); approve + reject flows via real backend | Done |

Dependencies: B-01

### Batch B-03 — Rewrite trace persistence tests with real Ollama (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-262 | Rewrite `realtime_trace_persistence.spec.ts` — remove all `page.route()` mocks; run real Ollama agent; verify: spinner CSS on running nodes, trace nodes appear on completion, execution trace persists after page reload; consolidate with `live_trace_verify.spec.ts` if coverage overlaps | Done |

Dependencies: B-01

### Batch B-04 — Rewrite tool scenario tests with real Ollama (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-263 | Rename + rewrite `tool_scenario_bubbles_mock.spec.ts` → `tool_scenario_bubbles.spec.ts` — no `page.route()`; for each scenario prompt (Data Query, Forecasting, Simulation, Optimization, Data Catalog): create real session, send prompt, verify assistant bubble appears ≤60s | Done |
| T-264 | Rewrite `tool_scenario_modal.spec.ts` — remove all `page.route()` mocks; use real session creation; verify modal open/tab-switch/chip UI; verify scenario card click sends real POST /messages and assistant bubble appears | Done |

Dependencies: B-01

### Batch B-05 — Quality gate (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-265 | `make test-playwright` full pass — all surviving spec files (7 files after 2 deleted), no tests skipped via RUN_E2E guard or env-var conditions | Done |

Dependencies: B-02, B-03, B-04

---

## P38 — Architecture Realignment: Deactivate Specialist Agent Routing

**Goal:** Stop routing new supply chain intents through the specialist runtime agents (DemandAgent,
InventoryAgent, SupplyPlanningAgent, FinanceImpactAgent, SopAgent). The agent class files and their
domain tools are **left in place** — they are not deleted or moved. Removal happens only if they
create concrete problems (test failures, import conflicts, confusion during P39+ work). The domain
tools from P31–P34 remain registered and will be reused by the Control Agent.

Dependencies: P37-B-05 (quality gate must pass before P38 starts)

### Batch B-01 — Move specialist agent classes to deprecated/ + deactivate routing (App Builder) — Done

Agent class files are moved to `packages/agent/deprecated/` — kept intact for reference and potential
Skill file conversion, but no longer imported or registered anywhere.

| Task | Description | Status |
|---|---|---|
| T-266 | Create `packages/agent/deprecated/` and move `packages/agent/domain/demand.py`, `inventory.py`, `supply_planning.py`, `finance_impact.py`, `sop.py` into it; add `packages/agent/deprecated/__init__.py` (empty — do not re-export) | Done |
| T-267 | Remove `"sop"` intent and S&OP-specific multi-agent plan routes from `packages/agent/orchestrator/intent_registry.py`; remove `"demand"`, `"inventory"`, `"supply_planning"`, `"finance_impact"`, `"sop"` from `DOMAIN_AGENT_ROLES` / `VALID_AGENT_ROLES` in `roles.py` and `SpecialistRole` Literal in `packages/agent/base.py`; remove all five from `create_domain_agents()` in `packages/agent/domain/__init__.py` | Done |

Dependencies: none

### Batch B-02 — Update Tool Scenario UI (App Builder) — Done

The Supply, Finance, and S&OP categories in the Tool Scenario Modal (added in P36) sent prompts that
assumed specialist routing. With those routes deactivated, these prompts will fall through to the
Control Agent in P39. For now, remove them from the UI to avoid confusing demo paths that no longer
have a valid route.

| Task | Description | Status |
|---|---|---|
| T-268 | Remove "supply", "finance", "sop" categories from `ToolScenarioModal.tsx` CATEGORIES; retain "query", "forecast", "simulation", "optimization", "catalog" | Done |
| T-269 | Remove the 3 quick chips (Supply Gap, Cost Scenarios, S&OP) from `ToolScenarioBar.tsx`; update `tool_scenario_modal.spec.ts` to assert 5-category structure | Done |

Dependencies: B-01

### Batch B-03 — Quality gate (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-270 | `make test-unit` + `make lint` + `make typecheck` — all pass | Done |
| T-271 | `make test-playwright` — all surviving Playwright specs pass with 5-category tool scenario modal | Done |

Dependencies: B-01, B-02

---

## P44 — Playwright Tests: Revert to Mock SSE

**Goal:** Replace real Ollama calls in Playwright specs with `page.route()` mock SSE interceptors to make `make test-playwright` complete in under 2 minutes (down from 40+ minutes).

Dependencies: P38-B-02 Done (P38-B-03 blocked on this phase completing first)

### Batch B-01 — Shared mock SSE helper (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-311 | Create `tests/e2e/playwright/sse-mock.ts` — `mockCompletedStream(page, sessionId, text)` (routes SSE stream: graph_node start/end + text_delta + response_ready + done; routes GET messages: returns [user, assistant] pair) and `mockAskUserStream(page, sessionId, opts)` (routes SSE: graph_node + ask_user_required + awaiting_input) | Done |

Dependencies: none

### Batch B-02 — Rewrite tool_scenario_bubbles.spec.ts (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-312 | Rewrite all 5 tests using `mockCompletedStream()`; remove `OLLAMA_TIMEOUT`; reduce per-test timeout to 30s; keep all assertions (bubble visible, not empty, no text-red-400) | Done |

Dependencies: B-01

### Batch B-03 — Rewrite ask_user_flow.spec.ts (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-313 | Rewrite 5 tests: tests 1–4 use `mockAskUserStream()` (inject ask_user_required event); test 5 (fully-specified, no ask) uses `mockCompletedStream()`; reduce ASK_USER_TIMEOUT and REPLY_TIMEOUT to 10s; keep all UI assertions | Done |

Dependencies: B-01

### Batch B-04 — Rewrite live_trace_verify.spec.ts (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-314 | Rewrite tests 1–3 using mocked graph_node events; reduce timeout to 15s; test 4 (persistence) kept as real Ollama with 90s timeout — requires real DB events for reload verification | Done |

Dependencies: B-01

### Batch B-05 — Mock slow test in tool_scenario_modal.spec.ts (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-315 | Replace the 1 real-Ollama test ("clicking a scenario card closes the modal and sends the prompt as a message") with `mockCompletedStream()` approach; keep the 4 fast UI-only tests unchanged | Done |

Dependencies: B-01

### Batch B-06 — Quality gate (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-316 | `make test-playwright` — all 7 spec files pass in under 2 minutes total | Done |
| T-317 | `make test-unit` + `make lint` + `make typecheck` — all pass | Done |

Dependencies: B-02, B-03, B-04, B-05

---

## P39 — Supply Chain Control Agent (MVP Core)

**Goal:** Build the Supply Chain Control Agent in `packages/agent/control/`. This is the cross-domain
judgment center and sole user-facing responder for supply chain queries (DESIGN.md §Agent Classification).
The Control Agent receives cross-domain context from SessionOrchestrator, calls domain tools via the Tool
Gateway, and produces decision-ready answers covering all domains (demand, inventory, supply, logistics,
finance).

Dependencies: P38 Done

### Batch B-01 — ControlAgent class (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-273 | Create `packages/agent/control/__init__.py` and `packages/agent/control/control_agent.py` — `ControlAgent` class implementing the `Specialist` protocol; role="control"; system prompt covering cross-domain operational judgment (stockout risk, exceptions, shipment delays, supply gaps, root cause candidates, action priorities) | Done |
| T-274 | Tool allowlist for ControlAgent in `packages/tools/base.py`: `["sql_query", "nl_query"]` + all calculation/analysis tools from P31–P34 (`profile_demand_data`, `analyze_demand_trend`, `evaluate_forecast_accuracy`, `detect_demand_anomalies`, `analyze_seasonality`, `analyze_demand_drivers`, `segment_demand`, `compare_demand_periods`, `calculate_supply_gap`, `get_open_supply_orders`, `analyze_supply_lead_time`, `calculate_days_of_supply`, `analyze_supply_risk`, `calculate_holding_cost_impact`, `calculate_stockout_cost_impact`, `calculate_expedite_cost`, `compare_cost_scenarios`, `calculate_days_of_inventory`, `calculate_stockout_risk`, `calculate_excess_inventory_risk`, `get_available_to_promise`) | Done |
| T-275 | Register ControlAgent in `packages/agent/orchestrator/roles.py` — add `"control"` to agent role definitions; add `ControlAgent` to `create_domain_agents()` | Done |

Dependencies: P38 Done

### Batch B-02 — SessionOrchestrator thin routing (App Builder) — Done

Simplify SessionOrchestrator to classify intent → route supply chain intents to ControlAgent.
Remove multi-agent sequential planning logic introduced for the S&OP pipeline.

| Task | Description | Status |
|---|---|---|
| T-276 | Add `"supply_chain"` intent to `INTENT_REGISTRY` in `packages/agent/orchestrator/intent_registry.py` — `allowed_agent_roles: ["control"]`; plan_prompt directs single ControlAgent call with full cross-domain tool access | Done |
| T-277 | Remove or stub out multi-agent plan-building nodes in `packages/agent/session_orchestrator.py` that previously coordinated sequential specialist runs; replace with single-agent delegation to ControlAgent for supply_chain intent | Done |

Dependencies: B-01

### Batch B-03 — Tests (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-278 | Unit test: `ControlAgent` instantiates with role="control"; `_SYSTEM_PROMPT` references all supply chain domains (demand, inventory, supply, logistics, finance) | Done |
| T-279 | Unit test: `INTENT_REGISTRY["supply_chain"]` routes to `allowed_agent_roles=["control"]`; ControlAgent tool allowlist contains sql_query + all domain calculation tools | Done |
| T-280 | `make test-unit` + `make lint` + `make typecheck` | Done |

Dependencies: B-01, B-02

---

## P40 — Skill Registry (packages/knowledge/skills/)

**Goal:** Build the Skill Registry as the authoritative source for standard analysis procedures
(DESIGN.md §Context Engineering Layer §Skill Loader). Skills define *what to do*, not LLM reasoning —
making analysis reproducible and auditable. Implement `SkillLoader` that matches intent → Skill files
and injects relevant procedures into the ControlAgent context on demand.

Dependencies: P39 Done

### Batch B-01 — Skill file format + SkillLoader (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-281 | Define Skill file format in `packages/knowledge/skills/` — each file is markdown with frontmatter: `skill_name`, `description`, `required_tables`, `required_kpis`, `procedure` (numbered steps), `output_schema` | Done |
| T-282 | `packages/knowledge/__init__.py` and `packages/knowledge/skill_loader.py` — `SkillLoader` class: `load(intent: str) -> list[str]` returns Skill file content for the given intent; MVP mapping is declared in code (keyword/intent-to-filename dict), not inferred dynamically | Done |

Dependencies: none

### Batch B-02 — MVP Skill files (App Builder) — Done

Three Skill files covering the MVP validation questions (DESIGN.md §Agent Design §MVP Validation Questions):

| Task | Description | Status |
|---|---|---|
| T-283 | `packages/knowledge/skills/stockout_risk_analysis.md` — procedure: check on_hand vs. demand forecast vs. incoming supply; compute days-of-supply; identify SKUs with days_of_supply < reorder threshold; surface root cause (low stock vs. inbound delay vs. demand surge) | Done |
| T-284 | `packages/knowledge/skills/exception_detection.md` — procedure: scan inventory, orders, shipments, and production for anomalies exceeding thresholds; rank by business impact; return prioritized exception list with root cause candidates | Done |
| T-285 | `packages/knowledge/skills/shipment_delay_root_cause.md` — procedure: cross-reference open orders vs. inventory availability vs. shipping status vs. inbound schedule; distinguish: inventory-blocked vs. carrier-delayed vs. slot-constrained vs. inbound-delayed; return root cause candidates with evidence | Done |

Dependencies: B-01

### Batch B-03 — SkillLoader integration into ControlAgent (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-286 | In `packages/agent/control/control_agent.py` (or its context builder): before each LLM call, invoke `SkillLoader.load(intent)` and prepend the returned Skill procedure(s) as a structured context block in the user message | Done |

Dependencies: B-01, B-02, P39 Done

### Batch B-04 — Tests (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-287 | Unit test: `SkillLoader.load("supply_chain")` returns content from at least one Skill file; `SkillLoader.load("unknown_intent")` returns empty list without error | Done |
| T-288 | Unit test: ControlAgent context builder includes Skill procedure text in the user message when SkillLoader returns content | Done |
| T-289 | `make test-unit` + `make lint` + `make typecheck` | Done |

Dependencies: B-01, B-02, B-03

---

## P41 — Memory Layer (packages/memory/)

**Goal:** Implement the six typed Memory store base classes as the Memory Layer public API
(DESIGN.md §Memory Design). Physical implementations are minimal in MVP. The typed API is locked;
physical grouping can evolve independently.

Dependencies: P39 Done

### Batch B-01 — Typed store base classes (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-290 | `packages/memory/__init__.py` — define abstract base classes for all six typed stores: `ShortTermMemory`, `WorkingMemory`, `LongTermMemory`, `DecisionMemory`, `UserMemory`, `DomainMemory`; each exposes `write(record)` and `search(query, k) -> list` | Done |
| T-291 | `packages/memory/stub.py` — `StubMemoryStore` in-memory implementations of all six typed stores; used in unit tests to replace real DB | Done |

Dependencies: none

### Batch B-02 — WorkingMemory physical implementation (App Builder) — Done

WorkingMemory maps to existing DB tables: `agent_session`, `task_run`, `tool_result`, `intermediate_artifact`, `approval_state` (DESIGN.md §Context Engineering Layer §Working Context Store).

| Task | Description | Status |
|---|---|---|
| T-292 | `packages/memory/working.py` — `WorkingMemoryStore(WorkingMemory)` backed by existing repository classes in `packages/persistence/`; `write()` creates `task_run` + `tool_result` rows; `search()` returns recent task_run records for the session | Done |
| T-293 | Alembic migration if any schema changes needed to support `intermediate_artifact` table (check whether it already exists; create only if absent) | Done |

Dependencies: B-01

### Batch B-03 — DecisionMemory physical implementation (App Builder) — Done

DecisionMemory maps to `decision_log` (with `record_type` column distinguishing decisions from failures) and pgvector embeddings for past-case similarity search (stub in MVP; real pgvector in Post-MVP).

| Task | Description | Status |
|---|---|---|
| T-294 | Alembic migration: `decision_log` table — `id`, `session_id`, `record_type` (decision / failure), `content_json TEXT`, `agent_role`, `created_at`; add index on `(session_id, record_type)` | Done |
| T-295 | `packages/memory/decision.py` — `DecisionMemoryStore(DecisionMemory)` backed by `decision_log` repository; `write()` inserts record; `search()` returns recent records filtered by session_id + record_type (pgvector stub: full-table recency-ordered fallback in MVP) | Done |

Dependencies: B-01

### Batch B-04 — Tests (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-296 | Unit tests: `StubMemoryStore` write + search round-trip for all six typed stores | Done |
| T-297 | Integration tests: `WorkingMemoryStore` and `DecisionMemoryStore` write + search against real DB | Done |
| T-298 | `make test-unit` + `make test-integration` + `make lint` + `make typecheck` | Done |

Dependencies: B-01, B-02, B-03

---

## P42 — Context Engineering Integration

**Goal:** Wire Memory Retriever and Skill Loader into the ControlAgent context-building step so that on
every LLM call the agent receives: (1) relevant past decisions from DecisionMemory, (2) the matching
Skill procedure(s) from the Skill Registry. Neither is pre-loaded — both are retrieved on demand
(DESIGN.md §Context Engineering Layer §Constraints).

Dependencies: P40 Done, P41 Done

### Batch B-01 — Memory Retriever integration (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-299 | In the ControlAgent context builder: before the LLM call, query `DecisionMemoryStore.search(query_text=user_query, k=3)` and `DomainMemoryStore.search(query_text=user_query, k=2)` (stub in MVP); append retrieved records as a structured "Past Decisions / Business Rules" context block | Done |
| T-300 | After each ControlAgent response: write the session decision record to `DecisionMemoryStore` — includes: session_id, intent, agent_role="control", tool_calls_made, response summary, record_type="decision" | Done |
| T-301 | On ControlAgent failure (exception propagated to orchestrator): write failure record to `DecisionMemoryStore` — record_type="failure", includes: session_id, intent, error message, tool_calls_made | Done |

Dependencies: P40 Done, P41 Done

### Batch B-02 — Tests (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-302 | Unit test: ControlAgent context builder calls `DecisionMemoryStore.search()` before LLM call; retrieved records appear in context block | Done |
| T-303 | Unit test: successful response writes `record_type="decision"` to `DecisionMemoryStore`; failure writes `record_type="failure"` | Done |
| T-304 | `make test-unit` + `make lint` + `make typecheck` | Done |

Dependencies: B-01

---

## P43 — MVP Validation (3 Questions)

**Goal:** Validate that the integrated Supply Chain Control Agent can answer the three MVP validation
questions defined in DESIGN.md §Agent Design §MVP Validation Questions:
(1) What exceptions does the human need to see today?
(2) Which products have high stockout risk?
(3) What are the root cause candidates for shipment delays and unfulfilled orders?

Dependencies: P42 Done

### Batch B-01 — Integration tests (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-305 | Integration test: "What are today's exceptions?" → ControlAgent calls exception_detection Skill + relevant tools; response includes prioritized exception list with at least one root cause candidate; `record_type="decision"` written to DecisionMemory | Done |
| T-306 | Integration test: "Which products are at stockout risk this week?" → ControlAgent calls stockout_risk_analysis Skill + stockout_risk tools; response includes at-risk SKU list with days-of-supply and risk classification | Done |
| T-307 | Integration test: "Why is order #X delayed?" → ControlAgent calls shipment_delay_root_cause Skill + SQL tools; response identifies root cause category (inventory-blocked / carrier-delayed / inbound-delayed) with evidence | Done |

Dependencies: none

### Batch B-02 — Playwright E2E (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-308 | Add 3 "MVP Demo" scenario prompts to `ToolScenarioModal.tsx` — one for each MVP validation question; add to a new "Supply Chain" category | Done |
| T-309 | Playwright spec: each MVP scenario prompt triggers a ControlAgent response bubble within 90s; execution trace shows ControlAgent node + tool call nodes | Done |

Dependencies: P42 Done, B-01

### Batch B-03 — Quality gate (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-310 | `make test-unit` + `make test-integration` + `make test-playwright` — all pass; ControlAgent answers all 3 MVP questions end-to-end | Done |

Dependencies: B-01, B-02

---

## P45 — Control-Agent-Only Routing

**Goal:** Remove all agent roles from `VALID_AGENT_ROLES` except `"control"`, route all non-chat
INTENT_REGISTRY entries to ControlAgent, and simplify prompts — aligning the MVP implementation
with DESIGN.md's "SessionOrchestrator → ControlAgent only" rule.

Dependencies: P39 Done

### Batch B-01 — Remove legacy agent roles (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-318 | `packages/agent/orchestrator/roles.py` — set `DOMAIN_AGENT_ROLES = {"control"}` only; set `CROSS_DOMAIN_AGENT_CLASSES = {}` (empty); `VALID_AGENT_ROLES` becomes `{"control"}` | Done |
| T-319 | `packages/agent/domain/__init__.py` — `create_domain_agents()` returns only `[ControlAgent(llm_client, tool_registry, sse_queue)]`; remove imports of all legacy domain agents | Done |
| T-320 | `packages/agent/base.py` — remove all values from `SpecialistRole` Literal except `"orchestrator"` and `"control"` | Done |

Dependencies: none

### Batch B-02 — Simplify INTENT_REGISTRY + prompts (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-321 | `packages/agent/orchestrator/intent_registry.py` — set `allowed_agent_roles=["control"]` for all non-chat intents (lookup, domain_analysis, cross_domain_analysis, decision_support, supply_chain); chat stays `[]` | Done |
| T-322 | `packages/agent/orchestrator/prompts.py` — simplify `ROUTER_SYSTEM`, `PLAN_SYSTEM`, `DAG_SYSTEM` allowed agents to `"control"` only | Done |

Dependencies: B-01

### Batch B-03 — Tests + quality gate (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-323 | Update unit tests that reference removed roles (test_intent_registry.py, test_control_agent.py, etc.) | Done |
| T-324 | `make test-unit` + `make lint` + `make typecheck` | Done |

Dependencies: B-01, B-02

---

## P46 — Skill & Tool Enrichment

**Goal:** Fix Q3 (shipment delay) by adding a `GetDelayedSupplyOrdersTool` that queries
actual delayed orders without requiring a specific order ID, and revise the `shipment_delay_root_cause`
and `exception_detection` Skill files to align with the real DB schema
(`supply_orders`, `inventory_snapshot`, `demand_history`).

Dependencies: P43 Done

### Batch B-01 — Delayed orders tool + Skill revisions (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-325 | `packages/tools/supply_delayed_orders_tool.py` — `GetDelayedSupplyOrdersTool`; queries `supply_orders WHERE expected_arrival < TODAY AND status != 'delivered'`; optional `sku_id` filter; returns list of `{sku_id, supplier_id, expected_arrival, days_overdue, quantity, status}` per row; `days_overdue = (today - expected_arrival).days` | Done |
| T-326 | Register `GetDelayedSupplyOrdersTool` in `packages/tools/__init__.py` `create_tool_registry()` | Done |
| T-327 | Revise `packages/knowledge/skills/shipment_delay_root_cause.md` — step 1 changes from "retrieve by provided identifier" to "call `get_delayed_supply_orders` to find all orders where expected_arrival < today and status != delivered"; remove assumption about `order_id` parameter; preserve the 8-step diagnosis structure | Done |
| T-328 | Revise `packages/knowledge/skills/exception_detection.md` — replace `inventory` table references with `inventory_snapshot`, replace `supply` table references with `supply_orders`; align step 2/3 with actual `supply_orders` columns (`expected_arrival`, `status`); preserve the 8-step structure | Done |

Dependencies: none

### Batch B-02 — Tests (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-329 | Unit test `tests/unit/test_supply_delayed_orders_tool.py` — AsyncMock pool; tests: (a) returns orders with `days_overdue` computed correctly, (b) returns empty list when no overdue orders, (c) DB error returns `{"error": ...}` dict | Done |
| T-330 | `make test-unit && make lint && make typecheck` — all pass | Done |

Dependencies: B-01

---

## P47 — Long-Term Memory Physical Implementation

**Goal:** Add `LongTermMemoryStore` backed by a new `long_term_memory` table so that the
ControlAgent can persist and retrieve long-horizon patterns, user preferences, and domain
knowledge across sessions — completing the memory layer defined in DESIGN.md §Memory Design.

Dependencies: P41 Done (Memory Layer base classes)

### Batch B-01 — DB migration (Infra) — Done

| Task | Description | Status |
|---|---|---|
| T-331 | `apps/api/alembic/versions/0017_long_term_memory.py` — create table `long_term_memory(id UUID PK DEFAULT gen_random_uuid(), memory_type VARCHAR(32) NOT NULL, scope VARCHAR(128) NOT NULL DEFAULT '', content TEXT NOT NULL, metadata_json TEXT NOT NULL DEFAULT '{}', created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())`; index `ix_long_term_memory_type_scope` on `(memory_type, scope)`; `down_revision='0016'` | Done |

Dependencies: none

### Batch B-02 — LongTermMemoryStore implementation (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-332 | `packages/memory/long_term.py` — `LongTermMemoryStore` standalone async class (same pattern as `DecisionMemoryStore`); `write(record)` requires keys `memory_type`, `content`; optional `scope` (default `''`), `metadata` (default `{}`); parameterized INSERT; `search(query, k=5)` — parses `"type:<type>"` or `"scope:<scope>"` prefix to add WHERE filter; returns `list[dict]` with keys `id, memory_type, scope, content, metadata_json, created_at`; ORDER BY `created_at DESC LIMIT k` | Done |
| T-333 | `packages/memory/__init__.py` — add `from packages.memory.long_term import LongTermMemoryStore` at top-level imports; add `"LongTermMemoryStore"` to `__all__` | Done |

Dependencies: B-01

### Batch B-03 — Tests (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-334 | Unit tests `tests/unit/test_long_term_memory_store.py` — AsyncMock asyncpg pool (same pattern as `test_decision_memory_store`); tests: write inserts correct fields, search with `type:` prefix adds WHERE filter, search with `scope:` prefix adds WHERE filter, search with bare query returns k records without filter, invalid/empty query returns records without filter, DB error in write propagates | Done |
| T-335 | `make test-unit && make lint && make typecheck` — all pass | Done |

Dependencies: B-01, B-02

---

## P48 — LongTermMemory Integration + Test Accuracy Fix

**Goal:** Wire `LongTermMemoryStore` into `ControlAgent.run()` for pre-call domain knowledge
retrieval (replacing the MVP stub comment), and fix `tool_scenario_modal.spec.ts` to reflect
the 6 categories now present in the modal (including the Supply Chain category added in P43).

Dependencies: P47 Done

### Batch B-01 — ControlAgent integration + Playwright fix (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-336 | `packages/agent/control/control_agent.py` — replace the `# NOTE: DomainMemoryStore retrieval is skipped` comment (line 111) with an actual `LongTermMemoryStore().search(f"scope:{intent_category}", k=3)` call; if records returned inject as `## Domain Knowledge\n\n<records>` block appended to instruction after Skills; non-fatal (catch all exceptions, log, continue) | Done |
| T-337 | `tests/e2e/playwright/tool_scenario_modal.spec.ts` — rename test from "all 5 category tabs are visible" to "all 6 category tabs are visible"; add `await expect(dialog.getByText("Supply Chain")).toBeVisible()` assertion alongside existing 5 checks | Done |

Dependencies: none

### Batch B-02 — Tests + quality gate (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-338 | Unit tests for LongTermMemory integration in ControlAgent — add 2 tests to a new file `tests/unit/agent/test_control_agent_long_term.py`: (a) when `LongTermMemoryStore.search` returns records, `## Domain Knowledge` block appears in task.instruction passed to `super().run`; (b) when `LongTermMemoryStore.search` raises, ControlAgent does not raise and continues normally | Done |
| T-339 | `make test-unit && make lint && make typecheck` — all pass | Done |

Dependencies: B-01

---

## P52 — LangChain ChatModel 移行 Phase 1: ModelRegistry + Structured Output

**Goal:** LangChain `BaseChatModel` を導入し、`ModelRegistry` でロール別モデル選択を実現。orchestrator ロールの 3 LLM 呼び出し（intent 分類、ルーティング、ask_user 判定）を `with_structured_output()` に移行して手動 JSON パースを排除する。

Dependencies: P51 Done

### Batch B-01 — ADR + 依存パッケージ追加 (Infra) — Done

| Task | Description | Status |
|---|---|---|
| T-353 | ADR `docs/adr/2026-06-07-langchain-chatmodel-migration.md` — 作成済み | Done |
| T-354 | `pyproject.toml` に `langchain-core>=0.3`, `langchain-anthropic>=0.3`, `langchain-ollama>=0.3` を追加。`uv add langchain-core langchain-anthropic langchain-ollama` で実行し `uv.lock` を更新する | Done |

Dependencies: none

### Batch B-02 — ModelRegistry 実装 (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-355 | `packages/agent/model_registry.py` に `ModelRegistry` クラスを実装。`get(role: str) -> BaseChatModel` メソッド: role は `"orchestrator"` / `"planner"` / `"control"` を受け付け、unknown role は `ValueError` を raise。`LLM_PROVIDER=anthropic` の場合 `ChatAnthropic(model=..., temperature=0.0)`、`LLM_PROVIDER=ollama` の場合 `ChatOllama(model=..., base_url=..., temperature=0.0)` を返す。orchestrator/planner ロールの Ollama モデルには `num_predict=512, think=False` を追加。`create_model_registry() -> ModelRegistry` factory 関数を公開し環境変数 (`LLM_PROVIDER`, `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`, `OLLAMA_BASE_URL`, `OLLAMA_MODEL`) から構築する。`ANTHROPIC_MODEL` が未設定なら `"claude-sonnet-4-6"` をデフォルトとする。 | Done |
| T-356 | `packages/agent/__init__.py` に `from packages.agent.model_registry import ModelRegistry, create_model_registry` を追加し `__all__` に含める | Done |

Dependencies: B-01

### Batch B-03 — Structured Output 移行 (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-357 | `packages/agent/orchestrator/models.py` に `AskUserDecision(BaseModel)` を追加: `needs_input: bool`, `question: str \| None = None`, `suggestions: list[str] \| None = None` | Done |
| T-358 | `SessionOrchestrator.__init__` に `model_registry: ModelRegistry \| None = None` パラメータを追加（デフォルト `None`）。`self._orchestrator_model: BaseChatModel \| None = model_registry.get("orchestrator") if model_registry else None` を設定する | Done |
| T-359 | `classify_intent()` を書き換え: `model_registry` が提供されていれば `self._orchestrator_model.with_structured_output(SessionIntent).ainvoke([SystemMessage(INTENT_SYSTEM), HumanMessage(query_text)])` を使用、未提供なら既存の `_llm_client.complete()` パスへフォールバック。`make_step` ステップ記録は両パスで維持する | Done |
| T-360 | `select_execution_mode()` を同パターンで書き換え: `self._orchestrator_model.with_structured_output(AgentRoute).ainvoke(...)` または既存フォールバック | Done |
| T-361 | `_node_prepare_ask_user()` の ask_user 判定部分を書き換え: `self._orchestrator_model.with_structured_output(AskUserDecision).ainvoke(...)` または既存フォールバック。`ASK_USER_SYSTEM` プロンプトはそのまま使用 | Done |

Dependencies: B-02

### Batch B-04 — Tests (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-362 | `tests/unit/test_model_registry.py` — 4 ケース: (a) `LLM_PROVIDER=anthropic` → `ChatAnthropic` インスタンス、(b) `LLM_PROVIDER=ollama` → `ChatOllama` インスタンス、(c) orchestrator ロールの Ollama モデルに `num_predict=512`、(d) unknown role → `ValueError` | Done |
| T-363 | `tests/unit/test_session_orchestrator_structured.py` — `with_structured_output` パスの 3 ケース: (a) `classify_intent` が `SessionIntent` を返す（`MagicMock` で `with_structured_output().ainvoke()` をスタブ）、(b) `select_execution_mode` が `AgentRoute` を返す、(c) `model_registry=None` のとき既存フォールバックパスが使われる | Done |
| T-364 | `make test-unit && make lint && make typecheck` — 全通過: 798 passed, lint clean, typecheck clean (2026-06-07) | Done |

Dependencies: B-03

---

## P53 — LangChain ChatModel Migration Phase 2: Planner + ControlAgent

**Goal:** Migrate `planning.py` (Planner) and `runtime.py` (ControlAgent) LLM calls to LangChain `with_structured_output()` / `bind_tools()`, eliminating remaining `_llm_client.complete()` calls from the orchestration core.

Dependencies: P52 Done

### Batch B-01 — Planner migration (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-365 | `create_execution_plan()` in `planning.py` — when `orchestrator._model_registry is not None`, use `model.with_structured_output(ExecutionPlan).ainvoke([SystemMessage(PLAN_SYSTEM), HumanMessage(user_content)])` instead of `_llm_client.complete()`; keep legacy fallback path when registry is None | Done |
| T-366 | `create_task_nodes()` in `planning.py` — add `DagPlan(BaseModel)` wrapper with `nodes: list[TaskNode]` to `orchestrator/models.py`; use `model.with_structured_output(DagPlan).ainvoke(...)` when registry present; extract `plan.nodes`; keep legacy fallback | Done |
| T-367 | `_summarize_messages()` in `runtime.py` — add `lc_model: BaseChatModel | None = None` parameter; when provided use `lc_model.ainvoke([SystemMessage(...), HumanMessage(text_content)])` and return `response.content`; fallback to existing `llm_client.complete()` path | Done |

Dependencies: none

### Batch B-02 — ControlAgent bind_tools migration (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-368 | `AgentRuntime.__init__` — add `model_registry: ModelRegistry \| None = None` parameter; store `self._lc_model: BaseChatModel \| None = model_registry.get("control") if model_registry else None` | Done |
| T-369 | `_call_model_node()` — when `self._lc_model is not None`, build LangChain message list from `effective_messages`; call `self._lc_model.bind_tools(tool_dicts).ainvoke(lc_messages)`; map `AIMessage.tool_calls` `[{"name", "args", "id"}]` to existing `response.tool_calls` shape `[{"name", "input", "id"}]`; continue loop while `ai_msg.tool_calls` is non-empty; break when empty (analogous to `finish_reason == "stop"`); keep full legacy path when `_lc_model is None` | Done |
| T-370 | `_verify_findings_node()` — when `self._lc_model is not None`, call `self._lc_model.ainvoke([HumanMessage(verifier_content)])` and extract `.content` for `_parse_verifier_status()`; keep legacy fallback | Done |

Dependencies: B-01

### Batch B-03 — Tests (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-371 | `tests/unit/test_planner_structured.py` — mock `orchestrator._model_registry`; verify `create_execution_plan` returns `ExecutionPlan` via `with_structured_output`; verify `create_task_nodes` returns `list[TaskNode]` via `DagPlan`; verify fallback path for both | Done |
| T-372 | `tests/unit/test_agent_runtime_bind_tools.py` — mock `_lc_model`; verify `bind_tools` is called with tool dicts; verify `tool_calls` mapping from `args` to `input`; verify `_verify_findings_node` uses `_lc_model.ainvoke` when set; verify legacy fallback | Done |
| T-373 | `make test-unit && make lint && make typecheck` — all pass | Done |

Dependencies: B-02

---

## P54 — LangChain ChatModel Migration Phase 3: NlQueryTool + LLMClient Deletion — Done

**Goal:** Complete LangChain migration — update `NlQueryTool` and `history.py`, remove all legacy `LLMClient` fallback paths, and delete `LLMClient` Protocol, `ClaudeClient`, `OllamaClient`, and `create_llm_client()`.

Dependencies: P53 Done

### Batch B-01 — NlQueryTool + history.py + app wiring (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-374 | `nl_query_tool.py` — `_generate_sql(model: BaseChatModel, ...)` uses `model.ainvoke([SystemMessage, HumanMessage])` and extracts `.content`; `generate_and_run(model: BaseChatModel)`; `NlQueryTool.__init__(model: BaseChatModel \| None)` replacing `llm_client`; update guard error message | Done |
| T-375 | `packages/tools/__init__.py` — `create_tool_registry(model: BaseChatModel \| None = None)` replacing `llm_client: LLMClient \| None`; remove `LLMClient` import; update `NlQueryTool(model=model)` call | Done |
| T-376 | `packages/agent/history.py` — replace `create_llm_client()` with `create_model_registry().get("control").ainvoke([SystemMessage, HumanMessage])` in `_summarize()`; remove `create_llm_client` import; add `langchain_core.messages` imports | Done |
| T-377 | `apps/api/state.py` — replace `create_llm_client()` with `create_model_registry()`; pass `model=registry.get("control")` to `create_tool_registry()`; pass `model_registry=registry` to `SessionOrchestrator`; remove `create_llm_client` import | Done |

Dependencies: none

### Batch B-02 — Remove legacy fallback paths (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-378 | `session_orchestrator.py` — remove `if self._model_registry is not None:` guards from `classify_intent()`, `select_execution_mode()`, `_node_prepare_ask_user()`; make LangChain path unconditional; keep `llm_client` param but remove its usage in these 3 methods | Done |
| T-379 | `planning.py` — remove legacy `_llm_client.complete()` fallback from `create_execution_plan()` and `create_task_nodes()`; remove `from packages.agent.llm import LLMMessage` lazy imports in those functions | Done |
| T-380 | `runtime.py` — remove legacy `_llm_client.complete()` fallback from `_call_model_node()`, `_verify_findings_node()`, and `_summarize_messages()`; make `lc_model` required (raise `RuntimeError` if `self._lc_model is None` at call time) | Done |

Dependencies: B-01

### Batch B-03 — Delete LLMClient, ClaudeClient, OllamaClient (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-381 | `packages/agent/llm/__init__.py` — delete `ClaudeClient` class (~lines 351–634); remove from `__all__` if present | Done |
| T-382 | `packages/agent/llm/__init__.py` — delete `OllamaClient` class and `_normalize_llm_text` module-level helper (~lines 635–913); remove from `__all__` if present | Done |
| T-383 | `packages/agent/llm/__init__.py` — delete `LLMClient(Protocol)` class (~lines 131–172) and `create_llm_client()` factory (~lines 914+); remove from `__all__`; keep `LLMMessage`, `LLMToolSpec`, `LLMResponse`, `LLMUsage`, `LLMStreamEvent`, `StubClaudeClient`, `ScenarioStubClaudeClient` | Done |

Dependencies: B-02

### Batch B-04 — Tests (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-384 | Update `tests/unit/test_tool_isolation.py` line ~366: replace `NlQueryTool(llm_client=SQLStubClaudeClient(...))` with `NlQueryTool(model=mock_model)` where `mock_model` is a `MagicMock(spec=BaseChatModel)` with `ainvoke = AsyncMock(return_value=AIMessage(content="SELECT pg_sleep(10)"))` | Done |
| T-385 | `make test-unit && make lint && make typecheck` — all pass | Done |

Dependencies: B-03

---

## P51 — Qwen3 Thinking Disable for Structured Output Calls

**Goal:** `OllamaClient.complete()` の orchestrator ロール呼び出しおよびツール呼び出しに `"think": False` を追加し、Qwen3 thinking モデルが thinking フェーズで max_tokens を消費して `content=""` になる問題を解消する。

Dependencies: P50 Done

### Batch B-01 — OllamaClient `think=False` 追加 (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-348 | `packages/agent/llm/__init__.py` — `OllamaClient.complete()` の `if tools:` ブロック内に `payload["think"] = False` を追加（`tool_choice` 設定の直後）。thinking と function calling は相性が悪く、tool 呼び出し精度を下げるため | Done |
| T-349 | `packages/agent/llm/__init__.py` — `elif specialist_role == "orchestrator":` ブロック内に `payload["think"] = False` を追加（`response_format` 設定の直後）。分類・ルーティング呼び出しでは thinking 不要、かつ thinking フェーズが max_tokens を消費して `content=""` になる問題の根本対処 | Done |
| T-350 | `packages/agent/llm/__init__.py` — `_normalize_llm_text` の warning メッセージ末尾に `"Set think=False in the request payload to prevent this."` を追加 | Done |

Dependencies: none

### Batch B-02 — Tests (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-351 | `tests/unit/` 内の OllamaClient 既存ユニットテスト（`test_ollama_client.py` または相当ファイル）に 2 ケース追加: (a) `specialist_role="orchestrator"` で `complete()` 呼び出し → payload に `"think": False` が含まれる、(b) `tools=[...]` 指定で `complete()` 呼び出し → payload に `"think": False` が含まれる | Done |
| T-352 | `make test-unit && make lint && make typecheck` — 全通過 | Done |

Dependencies: B-01

---

## P50 — LLM Response Normalization Layer

**Goal:** `_normalize_llm_text()` を `llm/__init__.py` 内に導入し、thinking タグ・side-channel reasoning フィールド・空コンテンツをLLM層で吸収。`LLMResponse.text` が常にクリーンな状態で返るようにし、`parsing.py` からモデル固有知識を排除する。

Dependencies: P49 Done

### Batch B-01 — ResponseNormalizer 実装 (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-343 | `packages/agent/llm/__init__.py` — `_normalize_llm_text(message: dict[str, Any], model_name: str) -> str` を追加。①`content = message.get("content") or ""`、②`re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()` で thinking タグ除去、③除去後も空なら `message.get("reasoning") or message.get("thinking")` を fallback テキストとして使用しWarningログ出力、④正規化テキストを返す | Done |
| T-344 | `OllamaClient.complete()` の thinking 警告ブロック + `text: str = content` を `text = _normalize_llm_text(message, self._model)` 1行に置換 | Done |
| T-345 | `packages/agent/orchestrator/parsing.py` — `_json_obj` / `_json_array` 内の `_strip_thinking()` 呼び出しを削除（LLM 層で既に除去済み）; `_strip_thinking` 関数自体も削除 | Done |

Dependencies: none

### Batch B-02 — Tests (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-346 | `tests/unit/test_normalize_llm_text.py` — `_normalize_llm_text` を直接インポートして 6 ケース: (a) 通常 content → そのまま返る、(b) `<think>…</think>` あり → 除去後テキスト返る、(c) 複数 `<think>` ブロック → 全除去、(d) content 空 + reasoning フィールド → reasoning を返し `logger.warning` 発火、(e) content 空 + thinking フィールド → thinking を返し `logger.warning` 発火、(f) content 空 + side-channel なし → `""` を返す | Done |
| T-347 | `make test-unit && make lint && make typecheck` — 全通過 | Done |

Dependencies: B-01

---

## P49 — AI Response Copy Button

**Goal:** `AssistantBubble` にコピーボタンを追加し、AI 回答のテキストをワンクリックでクリップボードにコピーできるようにする。

Dependencies: P48 Done

### Batch B-01 — AssistantBubble コピーボタン実装 (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-340 | `apps/web/components/chat/bubbles/AssistantBubble.tsx` — `useState` + clipboard ハンドラを追加し、コンテンツがあり streaming 中でない場合に "Copy / Copied!" ボタンを BubbleShell 下に描画する（`ml-10` でアバター分インデント、`aria-label="copy response"` / `aria-label="copied"`） | Done |

Dependencies: none

### Batch B-02 — テスト + 品質ゲート (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-341 | `apps/web/components/__tests__/AssistantCopyButton.test.tsx` — SqlCopyButton テストと同パターンで 4 ケース: (a) コンテンツあり → ボタン描画、(b) コンテンツなし → ボタン非表示、(c) クリック → clipboard.writeText 呼び出し、(d) クリック後 "Copied!" → 2000ms 後に "Copy" に戻る | Done |
| T-342 | `make lint && make typecheck && make test-unit` — 全通過 | Done |

Dependencies: B-01

Dependencies: B-01

---

## P55 — nl_query 単一 Text2SQL ツール化 + sql_query 削除

**Goal:** `sql_query` を削除し `nl_query` を全ロールで唯一の Text2SQL ツールとする。小規模ローカルモデルがスキーマ外カラム名を幻覚する問題を構造的に排除する。

Dependencies: P54 Done

### Batch B-01 — 幻覚防止バグ修正 (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-348 | `packages/tools/sql_allowlist.py` — `canonicalize_table_names()` 追加: `inventory`→`inventory_snapshot` 等のレガシーテーブル名をガードレール検証前に正規化する `_LEGACY_TABLE_MAP` + `_LEGACY_PATTERN` + 変換関数 | Done |
| T-349 | `packages/tools/nl_query_tool.py` — 静的 `FEW_SHOT_EXAMPLES` 定数を削除し、`_parse_schema_cols()` + `_build_few_shot_examples()` で `get_schema_context()` から動的生成に置換（AGENTS.md §73-74 準拠） | Done |
| T-350 | `packages/tools/schema_context.py` — スキーマコンテキスト文字列末尾に IMPORTANT ノート追記（正確なテーブル名使用を促す） | Done |
| T-351 | `packages/simulation/inventory.py` — `FROM inventory` → `FROM inventory_snapshot` に修正 | Done |

Dependencies: none

### Batch B-02 — sql_query 削除 + nl_query 昇格 (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-352 | `packages/tools/sql_tool.py` — `SqlQueryTool` ファイルを削除 | Done |
| T-353 | `packages/tools/__init__.py` — `SqlQueryTool` のインポート・エクスポート・レジストリ登録を削除 | Done |
| T-354 | `packages/tools/base.py` — `_ROLE_TOOL_ALLOWLIST` の全ロール（control, data_engineer, demand, inventory, supply_planning, finance_impact, replenishment, procurement, supplier, production, logistics, sop, anomaly_detector）から `sql_query` を削除し `nl_query` のみ残す | Done |
| T-355 | `packages/agent/control/control_agent.py` — `_INTENT_TOOL_SUBSET` の全インテント（supply_chain / demand / inventory / finance）で `sql_query` → `nl_query` に置換; `_SYSTEM_PROMPT` にツール優先順位（専門ツール→nl_query→カラム名幻覚禁止）を追記 | Done |
| T-356 | `packages/agent/cross_domain/data_engineer.py` — output_builder の `"sql_query"` キー参照を `"nl_query"` に更新 | Done |
| T-357 | `packages/agent/orchestrator/prompts.py` — PLAN_SYSTEM / DAG_SYSTEM のサンプル JSON を `nl_query` に更新 | Done |
| T-358 | `docs/TOOLS.md`, `docs/DESIGN.md` — `sql_query` / `SqlQueryTool` 参照を `nl_query` に更新 | Done |
| T-359 | `docs/adr/2026-06-07-nl-query-sole-text2sql.md` — ADR 作成 | Done |

Dependencies: B-01

### Batch B-03 — テスト + 品質ゲート (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-360 | `tests/unit/` および `tests/integration/` — `SqlQueryTool` テストを削除、全 `sql_query` stub 名を `nl_query` に更新（test_tool_isolation.py, test_output_builders.py, test_sse_queue_injection.py, test_agent_runtime.py, test_hitl_flow.py, test_tool_safety_level.py, test_structlog.py, test_tool_allowlists.py, test_control_agent.py, test_prompts_mock_llm.py, test_tools_real_db.py） | Done |
| T-361 | `packages/agent/llm/__init__.py` — `astream()` の不要な `# type: ignore[override]` を削除 | Done |
| T-362 | `make test-unit && make lint && make typecheck` — 749 passed, all checks passed, no issues | Done |

Dependencies: B-01, B-02

---

## P56 — nl_query クリーンアップ後処理

**Goal:** P55検証で発見された残存`sql_query`参照・デッドコード・スタブを全て除去し、コードベースを一貫させる。

Dependencies: P55 Done

### Batch B-01 — パッケージコードのデッドコード削除 (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-363 | `packages/tools/sql_allowlist.py` — `validate_query()` 関数を削除（どこからもインポートされていないデッドコード） | Done |
| T-364 | `packages/tools/nl_query_tool.py` — `_load_positive_examples()` スタブを削除し、`generate_and_run` 内の呼び出し (`dynamic_examples = await _load_positive_examples()`) と `_generate_sql` の `dynamic_examples` パラメータを削除 | Done |
| T-365 | `packages/knowledge/skills/_FORMAT.md:52` — 例の中の `sql_query` を `nl_query` に更新 | Done |
| T-366 | `apps/web/hooks/__tests__/useAgentProgress.test.ts:146` — `toolName: "sql_query"` → `toolName: "nl_query"` に更新 | Done |

Dependencies: none

### Batch B-02 — Python テストスタブ修正 + 品質ゲート (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-367 | `tests/unit/test_tool_isolation.py:96` — LLMスタブレスポンスの `"tools":["sql_query"]` → `"tools":["nl_query"]` に更新 | Done |
| T-368 | `tests/unit/test_tool_layer_integration.py:152,158,215,220` — スタブの `tools=["sql_query"]` → `tools=["nl_query"]` に更新 | Done |
| T-369 | `make test-unit && make lint && make typecheck` — 品質ゲート全通過確認 | Done |

Dependencies: B-01

---

## P57 — nl_query 品質強化

**Goal:** 評価で発見した問題（エラーキー不整合・空スキーマのフェイルサイレント・キャッシュ上限なし・クエリタイムアウト不在）を修正し、テストカバレッジを補完する。

Dependencies: P56 Done

### Batch B-01 — 実装修正 (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-370 | `packages/tools/nl_query_tool.py` — `handle()` 冒頭で `get_schema_context()` が空文字のとき `RuntimeError("Schema context not loaded — call load_schema_context() at startup")` を raise | Done |
| T-371 | `packages/tools/nl_query_tool.py` — エラーパス3箇所（SQLGuardrailError, RuntimeError, Exception）のキーを `results`→`rows`, `count`→`row_count` に統一; `output_schema.properties` に `error` と `note` を追加 | Done |
| T-372 | `packages/persistence/query_repo.py` — `conn.fetch(_inject_limit(query, MAX_ROWS))` に `timeout=30.0` 引数を追加（asyncpg statement timeout 30秒） | Done |
| T-373 | `packages/tools/nl_query_tool.py` — `_result_cache` に最大512エントリ制限を追加: キャッシュ書き込み前に `len(_result_cache) > 512` なら最古エントリ（`min(..., key=lambda k: _result_cache[k][2])`）を削除 | Done |

Dependencies: none

### Batch B-02 — テスト補完 + 品質ゲート (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-374 | `tests/unit/test_tool_isolation.py` — NlQueryTool の追加テスト3件: (1) `get_schema_context()` が空のとき `RuntimeError` が発生する, (2) SQLGuardrailError発生時レスポンスに `rows`/`row_count` キーが存在する, (3) キャッシュヒット時に DB クエリが呼ばれないことを確認 | Done |
| T-375 | `make test-unit && make lint && make typecheck` — 品質ゲート全通過確認 | Done |

Dependencies: B-01

---

## P58 — list_stockout_risk Bulk Tool

**Goal:** Add `list_stockout_risk` tool that retrieves stockout risk for all SKUs in a single SQL query, eliminating the N-round-trip loop pattern on `calculate_stockout_risk`.

Root cause class: `missing_tool` — identified via LLM-as-a-Judge session.

### Batch B-01 — Tool implementation (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-376 | Create `packages/tools/list_stockout_risk_tool.py` — `ListStockoutRiskTool`; name=`list_stockout_risk`; inputs `horizon_days` (int, default 7) and `min_risk_level` (string enum `["low","medium","high","critical"]`, default `"medium"`); single JOIN query across `inventory_snapshot + supply_orders + demand_history`; reuses `_classify_stockout_risk` thresholds; output `{ items: [...], count: int }`; `safety_level = "read_only"` | Done |

Dependencies: none

### Batch B-02 — Wiring (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-377 | `packages/tools/base.py` — add `"list_stockout_risk"` to `_ROLE_TOOL_ALLOWLIST["inventory"]` and `_ROLE_TOOL_ALLOWLIST["control"]` | Done |
| T-378 | `packages/tools/__init__.py` — import `ListStockoutRiskTool`, add to `__all__`, register in `create_tool_registry()` | Done |
| T-379 | `packages/agent/control/control_agent.py` — add `"list_stockout_risk"` to `_INTENT_TOOL_SUBSET["supply_chain"]` and `_INTENT_TOOL_SUBSET["inventory"]`; update `_SYSTEM_PROMPT` to include: "For enumeration of stockout risk across all SKUs, call `list_stockout_risk(horizon_days=7)` once instead of looping `calculate_stockout_risk` per SKU" | Done |

Dependencies: B-01

### Batch B-03 — Tests (Test/Review) — Not Started

| Task | Description | Status |
|---|---|---|
| T-380 | `tests/unit/tools/test_list_stockout_risk_tool.py` — unit tests with AsyncMock pool: (a) returns all SKUs filtered by `min_risk_level`; (b) `count` matches `len(items)`; (c) stockout_date_estimate computed correctly for critical SKU; (d) empty result when no SKUs meet threshold; (e) DB error returns `{"error": ...}` dict; (f) `min_risk_level="low"` returns all non-none risk items | Done |
| T-381 | `tests/integration/test_list_stockout_risk_tool_integration.py` — integration test against real DB: tool returns list, each item has required keys, count matches | Done |
| T-382 | `make test-unit && make lint && make typecheck` — all pass | Not Started |

Dependencies: B-01, B-02

---

## P60 — Control Agent Tool-Loop Guard

**Goal:** Prevent gemma4:12b (and other local models) from calling the same tool repeatedly in a
single session instead of synthesising results. Fix has three layers: a prompt guard in
`control_agent.py`, a runtime duplicate-tool detector in `runtime.py`, and a secondary prompt
addition that ensures `get_delayed_supply_orders` is called for "exceptions" questions alongside
`list_stockout_risk`.

Root cause class: `model_limitation` — verified via container logs: `finish_reason: "tool_use"`,
`tool_call_count: 1` repeated 10× before `verify_status: "blocked"`.

Dependencies: P59 Done

### Batch B-01 — Prompt guard in control_agent.py (App Builder) — Done

Add a hard stop instruction to `_SYSTEM_PROMPT` in `packages/agent/control/control_agent.py`.
The instruction must appear immediately after the existing tool usage priority block (after the
"Always ground recommendations…" line) so that the model reads it before generating any tool call.

| Task | Description | Status |
|---|---|---|
| T-388 | `packages/agent/control/control_agent.py` — append two sentences to `_SYSTEM_PROMPT`, after the "Always ground recommendations in tool results…" paragraph: `"Never call the same tool twice in one session. After receiving results from list_stockout_risk, synthesise them immediately into a final answer — do NOT call any tool again."` | Done |
| T-389 | `packages/agent/control/control_agent.py` — append a third instruction to the same block for the exception/delay use-case: `"For exception/delay questions, call get_delayed_supply_orders() to surface supply chain delays alongside list_stockout_risk for stockout enumeration."` | Done |

Dependencies: none

### Batch B-02 — Runtime duplicate-tool detection in runtime.py (App Builder) — Done

Add logic to `_should_continue()` in `packages/agent/runtime.py` that inspects the accumulated
`state["tool_results"]` list for repeated tool names and forces an early transition to
`verify_findings` before `_MAX_ITERATIONS` is reached.

`state["tool_results"]` is `list[dict[str, Any]]` where each dict has a single key equal to the
tool name. The duplicate check: collect all tool names from this list; if any name appears ≥ 2
times, return `"verify_findings"` immediately and emit a WARNING log.

| Task | Description | Status |
|---|---|---|
| T-390 | `packages/agent/runtime.py` — in `_should_continue()`, after the `_MAX_ITERATIONS` guard and before the `response.tool_calls` / `finish_reason` check, add: collect `seen_tool_names` by iterating `state.get("tool_results") or []` and extracting `list(d.keys())[0]` for each dict; if any name has count ≥ 2 in `seen_tool_names`, emit `_log.warning("duplicate tool call detected — forcing verify_findings", ...)` and return `"verify_findings"` | Done |

Dependencies: none

### Batch B-03 — Tests (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-391 | `tests/unit/test_agent_runtime_tool_loop_guard.py` — 2 unit tests: (a) when `state["tool_results"]` contains `[{"list_stockout_risk": {...}}, {"list_stockout_risk": {...}}]`, `_should_continue()` returns `"verify_findings"` without reaching the `execute_tools` branch; (b) when the same tool appears only once, `_should_continue()` returns `"execute_tools"` normally | Done |
| T-392 | `tests/unit/agent/test_control_agent_prompt.py` (or extend existing `test_control_agent.py`) — assert that `_SYSTEM_PROMPT` contains the substring `"Never call the same tool twice"` and the substring `"get_delayed_supply_orders"` | Done |
| T-393 | `make test-unit && make lint && make typecheck` — all pass | Done |

Dependencies: B-01, B-02

### Batch B-04 — blocked-status fabrication fix (App Builder) — Done

Fix `run()` in `packages/agent/runtime.py` so that when `run_status == "blocked"`, the upstream
orchestrator receives `status="failed"` and a safe fallback message instead of the agent's
fabricated conclusion text.

**Problem:** Lines ~964–966 map `"blocked"` to `specialist_status = "completed"` and pass
`last_response.text` unchanged into `SpecialistResult.output["text"]`. Because `verify_findings`
is the final node when the tool-loop guard fires, the LLM may have emitted a fabricated summary
before the block was detected. That text surfaces to users as a real answer.

**Fix (in `run()`, final assembly block):**
- When `run_status == "blocked"`: set `specialist_status = "failed"` and override the output text
  with the safe fallback `"Could not verify findings. Please rephrase your question or try again."`.
- Populate `SpecialistResult.error` with `"run blocked by tool-loop guard"` when the existing
  `final_state.get("error")` is `None`, so the orchestrator has a machine-readable reason.
- The `SpecialistResult.output` dict must still contain the `"text"` key (set to the fallback),
  `"tool_results"` (unchanged), and all other keys already produced by `_output_builder`.

| Task | Description | Status |
|---|---|---|
| T-394 | `packages/agent/runtime.py` — in the final assembly block of `run()` (~lines 963–970): replace the `if run_status in ("completed", "blocked"):` branch with separate handling: `"completed"` → `specialist_status = "completed"` (unchanged); `"blocked"` → `specialist_status = "failed"`, replace output text with `"Could not verify findings. Please rephrase your question or try again."`, set `error = final_state.get("error") or "run blocked by tool-loop guard"`. Also add a unit test `tests/unit/test_agent_runtime_blocked_status.py` asserting: (a) a run that returns `status="blocked"` produces `SpecialistResult.status == "failed"` and `SpecialistResult.output["text"]` equals the safe fallback string (not the LLM fabricated text); (b) `SpecialistResult.error` is non-empty. | Done |

Dependencies: B-02

---

## P59 — Control Agent Degenerate Response Guard

**Goal:** Prevent the Control Agent from delivering truncated one-word answers (e.g., "Based") to the
UI by adding a minimum-length guard in `runtime.py`, raising `max_tokens` defaults in stub LLM
classes, and emitting a WARNING log when `output_tokens` approaches `max_tokens`.

Root cause class: `model_limitation` — identified via LLM-as-a-Judge session: two consecutive
truncated responses ("…However," and "Based") traced to Ollama local model output-token exhaustion
and quantized-model quality degradation.

Dependencies: P58 Done

### Batch B-01 — Degenerate response guard + max_tokens raise + token saturation log (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-383 | `packages/agent/runtime.py` — before calling `self._output_builder(merged_tool_results, last_response)` (line ~961), extract `final_text = last_response.text if last_response else ""`; if `final_text` is not empty and `len(final_text) < 80`, raise `RuntimeError(f"Degenerate LLM response (len={len(final_text)}): {final_text!r}")` | Done |
| T-384 | `packages/agent/llm/__init__.py` — raise the `max_tokens: int = 4096` default to `8192` on all four `complete()` / `stream()` signatures inside `StubClaudeClient` and `ScenarioStubClaudeClient` (lines ~90, ~120, ~183, ~251) | Done |
| T-385 | `packages/agent/runtime.py` — add module-level constant `_MAX_TOKENS_WARN_THRESHOLD = 4000`; in `_call_model_node()` after the existing `"specialist LLM response received"` log block: if `response.output_tokens >= _MAX_TOKENS_WARN_THRESHOLD`, emit `_log.warning("output_tokens near max_tokens limit — response may be truncated", output_tokens=response.output_tokens, threshold=_MAX_TOKENS_WARN_THRESHOLD, agent_role=self.role)` | Done |

Dependencies: none

### Batch B-02 — Tests (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-386 | `tests/unit/test_agent_runtime_degenerate_guard.py` — 2 unit tests: (a) when `last_response.text` is a string of fewer than 80 characters (e.g. `"Based"`), `AgentRuntime.run()` raises `RuntimeError` containing `"Degenerate LLM response"`; (b) when `last_response.text` is 80+ characters, no error is raised and `SpecialistResult.output["text"]` equals the response text | Done |
| T-387 | `make test-unit && make lint && make typecheck` — all pass | Done |

Dependencies: B-01

---

## P61 — Quality Hardening: Degenerate Guard / Rule-Based Verifier

**Goal:** Fix three residual quality problems in `packages/agent/runtime.py`: (1) degenerate guard
overrides output text and sets `specialist_status = "failed"` instead of warn-only; (2) `call_model_final`
applies the same lightweight degenerate check before returning; (3) `verify_findings` converted from LLM
self-verification to rule-based checks — eliminating `needs_revision`, `add_revision_message`, and
`call_model_final` nodes and the associated LLM call.

Dependencies: P60 Done

### Batch B-01 — runtime.py quality fixes (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-395 | `packages/agent/runtime.py` — degenerate guard in `run()`: when `final_text` is non-empty and `len(final_text) < _DEGENERATE_RESPONSE_MIN_LEN`, override `output["text"]` to `"Could not produce a complete response. Please try again."` and set `specialist_status = "failed"` (instead of warn-only) | Done |
| T-396 | `packages/agent/runtime.py` — `_call_model_final_node()`: after `await self._call_model_node()`, if the response text is empty or shorter than `_DEGENERATE_RESPONSE_MIN_LEN`, set `result["status"] = "blocked"` and log a warning; otherwise set `result["status"] = "completed"` | Done |
| T-397 | `packages/agent/runtime.py` — convert `_verify_findings_node()` to rule-based: delete `_VERIFIER_PROMPT`, `_parse_verifier_status`; implement rules: (a) `tool_results` empty AND conclusion contains digit or "no"/"none"/"なし" → "blocked"; (b) `tool_results` non-empty AND `len(conclusion) < _DEGENERATE_RESPONSE_MIN_LEN` → "blocked"; (c) otherwise → "pass"; remove `needs_revision` status, `_after_verify` revise branch, `add_revision_message` node, `call_model_final` node; update graph wiring accordingly | Done |

Dependencies: none

### Batch B-02 — Tests (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-398 | Update `tests/unit/test_agent_runtime_degenerate_guard.py` — replace `status == "completed"` with `status == "failed"` assertion; assert `result.output["text"] == "Could not produce a complete response. Please try again."` | Done |
| T-399 | New `tests/unit/test_agent_runtime_verifier_rule_based.py` — 4 unit tests: (a) no tool calls + conclusion with number → blocked; (b) no tool calls + conclusion "no stockouts" → blocked; (c) tool calls present + short conclusion → blocked; (d) tool calls present + long conclusion → pass | Done |
| T-400 | `make test-unit && make lint && make typecheck` — all pass | Done |

Dependencies: B-01

---

## P62 — Verifier Rule 1b: Nil-Claim Guard for Non-Empty Tool Results

**Goal:** Extend `_rule_based_verify` with Rule 1b — block conclusions that claim "no exceptions / no risks / 例外なし" when tool results contain a non-zero `count` field or a non-empty `items` list, closing the gap where a fabricated nil answer slipped past the existing rules.

### Batch B-01 — Rule 1b implementation + unit tests (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-401 | Add Rule 1b to `_rule_based_verify` in `packages/agent/runtime.py`: walk `tool_results` list; if any result dict has `"count"` (int > 0) or `"items"` (non-empty list) AND conclusion matches nil-claim regex → "blocked" | Done |
| T-402 | Add 3 unit tests for Rule 1b in `tests/unit/test_agent_runtime_verifier_rule_based.py` | Done |
| T-403 | `make test-unit && make lint && make typecheck` — all pass | Done |

Dependencies: none

---

## P63 — ControlAgent Intent-to-Tool Subset Alignment

**Goal:** Fix `_INTENT_TOOL_SUBSET` in `control_agent.py` — replace dead keys (`"demand"`, `"inventory"`, `"finance"`) with actual `INTENT_REGISTRY` categories (`"lookup"`, `"domain_analysis"`, `"cross_domain_analysis"`, `"decision_support"`) so tool narrowing activates for every intent, not just `"supply_chain"`.

Root cause: key names in `_INTENT_TOOL_SUBSET` were written for hypothetical domain-specialist routing (pre-P38 architecture); after P38 consolidated routing to ControlAgent with INTENT_REGISTRY categories, the subset keys were never updated.

Dependencies: P62 Done

### Batch B-01 — Fix _INTENT_TOOL_SUBSET + unit test (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-404 | `packages/agent/control/control_agent.py` — replace `_INTENT_TOOL_SUBSET` body: keep `"supply_chain"` as-is; add `"lookup"` (7 tools), `"domain_analysis"` (24 tools), `"cross_domain_analysis"` (28 tools), `"decision_support"` (22 tools) | Done |
| T-405 | `tests/unit/test_control_agent_intent_tool_subset.py` — assert every key in `_INTENT_TOOL_SUBSET` is in `INTENT_REGISTRY`; assert every tool name in each subset is in the set returned by `create_tool_registry()._tools.keys()`; assert `"supply_chain"` subset is unchanged | Done |
| T-406 | `make test-unit && make lint && make typecheck` — all pass | Done |

Dependencies: none

---

## P64 — Agent Architecture Gap Closure (5 Gaps)

**Goal:** Close all 5 gaps documented in `docs/AGENT_ARCHITECTURE.md`:
(1) add `plan_tools` node for complex intents,
(2) parallelize independent tool calls with `asyncio.gather()`,
(3) enforce structured response format in `_SYSTEM_PROMPT`,
(4) make `_ROLE_TOOL_ALLOWLIST["control"]` auto-derived from `_INTENT_TOOL_SUBSET`,
(5) remove `write_audit_log`, `job_dispatch`, `train_forecast` from LLM-callable registry.

Dependencies: P63 Done

### Batch B-01 — Gap 3: Response format constraint in _SYSTEM_PROMPT (App Builder) — Done

Highest ROI. Add a structured output format section to `ControlAgent._SYSTEM_PROMPT` that
constrains responses to: Situation → Root Cause → Recommended Actions (numbered, data-backed)
→ Confidence Level. This is purely additive to the existing system prompt.

| Task | Description | Status |
|---|---|---|
| T-407 | `packages/agent/control/control_agent.py` — append a `## Response Format` section to `_SYSTEM_PROMPT` after the existing tool-use block. Format: `"**Situation:** [summary of what the data shows]\n**Root Cause:** [identified cause(s) with data evidence]\n**Recommended Actions:**\n1. [action] — [data rationale]\n2. ...\n**Confidence Level:** [High / Medium / Low] — [one sentence justification]"`. Section must appear after the tool-use priority block and before any trailing whitespace. | Done |

Dependencies: none

### Batch B-02 — Gap 5: Remove write_audit_log / job_dispatch / train_forecast from registry (App Builder) — Done

Remove three tools from `create_tool_registry()` so they are no longer LLM-callable. Wire
`AuditLogTool` into `AgentRuntime.run()` as an automatic post-completion step. Keep
`AuditLogTool`, `JobDispatchTool`, `TrainForecastTool` class files intact — they are still
used by other paths.

| Task | Description | Status |
|---|---|---|
| T-408 | `packages/tools/__init__.py` — remove `AuditLogTool()`, `JobDispatchTool()`, and `TrainForecastTool(runner=runner)` from `create_tool_registry()`; keep all three imports and `__all__` entries intact (classes still usable, just not in the registry) | Done |
| T-409 | `packages/tools/base.py` — remove `"write_audit_log"` from all `_ROLE_TOOL_ALLOWLIST` entries that contain it (currently `"evaluator"`); remove `"job_dispatch"` from `"orchestrator"` and `"simulation_optimizer"`; remove `"train_forecast"` from `"demand"` | Done |
| T-410 | `packages/agent/runtime.py` — in `run()`, after the final assembly block (after `specialist_status` and output are set and `run_status != "failed"`), call `await AuditLogTool().handle({"session_id": task.session_id, "agent_role": self.role, "status": specialist_status, "tool_count": len(final_state.get("tool_results") or [])}, tool_ctx)` inside a `try/except Exception` block that logs a warning on failure (non-fatal); import `AuditLogTool` from `packages.tools.audit_tool` at the top of the file | Done |

Dependencies: B-01

### Batch B-03 — Gap 4: Auto-derive _ROLE_TOOL_ALLOWLIST["control"] from _INTENT_TOOL_SUBSET (App Builder) — Done

Replace the hand-maintained `_ROLE_TOOL_ALLOWLIST["control"]` list in `packages/tools/base.py`
with a computed union of all tools in `_INTENT_TOOL_SUBSET`, making Layer 3 the single source
of truth. The union is computed at import time to avoid circular imports.

| Task | Description | Status |
|---|---|---|
| T-411 | `packages/tools/base.py` — replace the static `"control": [...]` entry in `_ROLE_TOOL_ALLOWLIST` with a sentinel `"control": []` placeholder that is filled at the bottom of the module after `_ROLE_TOOL_ALLOWLIST` is defined, using a dedicated helper: `def _build_control_allowlist() -> list[str]`. The helper imports `_INTENT_TOOL_SUBSET` from `packages.agent.control.control_agent` inside the function body (deferred import to avoid circular dependency), unions all tool lists, and returns the sorted unique list. Call it once: `_ROLE_TOOL_ALLOWLIST["control"] = _build_control_allowlist()`. | Done |

Dependencies: B-02

### Batch B-04 — Gap 2: Parallelize independent tool calls with asyncio.gather() (App Builder) — Done

Replace the sequential `for` loop in `_execute_tools_node` in `packages/agent/runtime.py`
with `asyncio.gather()`. HITL tools (those with `safety_level != "read_only"` or name ==
`"request_approval"`) must remain sequential (called one at a time and awaited before
proceeding). Non-HITL tools in the same LLM response can be gathered.

| Task | Description | Status |
|---|---|---|
| T-412 | `packages/agent/runtime.py` — in `_execute_tools_node()`, split `response.tool_calls` into `hitl_calls` (safety_level in ("hitl", "write") or name == "request_approval") and `parallel_calls` (all others); execute `parallel_calls` with `await asyncio.gather(*[_run_single_tool(call) for call in parallel_calls])` where `_run_single_tool` is a local async helper that calls `await tool.handle(args, tool_ctx)` and returns the result dict; execute `hitl_calls` sequentially after `parallel_calls`; preserve existing error handling and result accumulation | Done |

Dependencies: B-01

### Batch B-05 — Gap 1: plan_tools node for complex intents (App Builder) — Done

Add a `plan_tools` node to `AgentRuntime`'s LangGraph graph. The node fires only for
`domain_analysis`, `cross_domain_analysis`, and `decision_support` intents. It calls the LLM
with a structured output schema `[{tool, purpose, depends_on}]` and stores the result in
`AgentState`. The plan is injected as a context block at the start of the next `call_model`
invocation.

| Task | Description | Status |
|---|---|---|
| T-413 | `packages/agent/runtime.py` — add `ToolPlan` TypedDict: `{"tool": str, "purpose": str, "depends_on": list[str]}`; add `"tool_plan"` key to `AgentState` (`list[ToolPlan]`, default empty); add `_plan_tools_node()` async method: builds a message asking the LLM to produce a JSON array of `ToolPlan` objects given the task instruction and available tool names; calls `await self._lc_model.with_structured_output(list[ToolPlan]).ainvoke(messages)` (or fallback to plain `ainvoke` + JSON parse if structured output fails); stores result in `state["tool_plan"]`; skip if intent_category not in `{"domain_analysis", "cross_domain_analysis", "decision_support"}` or tool_plan already populated | Done |
| T-414 | `packages/agent/runtime.py` — wire `plan_tools` node into the LangGraph graph. Method `_plan_tools_node` already exists. In `_build_graph()` (~line 1010): add `sg.add_node("plan_tools", self._plan_tools_node)` after existing `add_node` calls; change `sg.add_edge("compress_history", "call_model")` to `sg.add_edge("compress_history", "plan_tools")` + `sg.add_edge("plan_tools", "call_model")`. In `_call_model_node()` (~line 349): after `lc_msgs` is built from `effective_messages`, if `state.get("tool_plan")`: append `HumanMessage("## Tool Plan\n\n" + json.dumps(state["tool_plan"], indent=2))` to `lc_msgs` before the `bound_model.ainvoke(lc_msgs)` call. | Done |

Dependencies: B-04

### Batch B-06 — Tests + quality gate (Test/Review) — Done

| Task | Description | Status |
|---|---|---|
| T-415 | `tests/unit/agent/test_control_agent_response_format.py` — assert `_SYSTEM_PROMPT` contains `"**Situation:**"`, `"**Root Cause:**"`, `"**Recommended Actions:**"`, `"**Confidence Level:**"` | Done |
| T-416 | `tests/unit/test_tool_registry_gap5.py` — assert `create_tool_registry()._tools` does NOT contain keys `"write_audit_log"`, `"job_dispatch"`, `"train_forecast"`; assert these tool classes can still be instantiated directly | Done |
| T-417 | `tests/unit/test_control_allowlist_derived.py` — assert `_ROLE_TOOL_ALLOWLIST["control"]` equals the sorted union of all values in `_INTENT_TOOL_SUBSET`; assert no manual list in `base.py` diverges from this | Done |
| T-418 | `tests/unit/test_agent_runtime_parallel_tools.py` — mock two read-only tool calls in a single LLM response; assert `asyncio.gather` is called (or that both tools are called without awaiting each other sequentially); assert a HITL tool call is NOT gathered | Done |
| T-419 | `tests/unit/agent/test_plan_tools_node.py` — mock `_lc_model.with_structured_output().ainvoke()` to return a `[ToolPlan]`; assert `state["tool_plan"]` is populated for `domain_analysis` intent; assert `plan_tools` node is skipped for `supply_chain` and `lookup` intents | Done |
| T-420 | `make test-unit && make lint && make typecheck` — all pass. Note: `tests/unit/test_tool_allowlists.py` has stale assertions referencing `train_forecast` (demand role) and `write_audit_log` (evaluator role) that were removed by T-409; remove those specific assertions before running. | Done |

Dependencies: B-01, B-02, B-03, B-04, B-05

---

# Full Refactoring Programme (P65–P70)

**Scope decision (2026-06-10):** production infra code (`infra/terraform/`, `infra/databricks/`,
`packages/lakehouse/`, `AcaJobsRunner`, Celery worker, `celery`/`redis` dependencies) is
**explicitly preserved** per user decision — it is out of scope for all phases below.
Targets are application-code waste only: dead agent classes, unreachable orchestration paths,
registry/allowlist drift, unused frontend modules, config hygiene, and doc bloat.

**Evidence base (survey 2026-06-10):** `VALID_AGENT_ROLES == {"control"}` and
`CROSS_DOMAIN_AGENT_CLASSES == {}` since P38/P45 — `_make_agent()` can only ever instantiate
`ControlAgent`, yet 15 legacy agent class files and the multi-agent execution machinery
(`sequential_agents` / `planned_execution` / DAG, `decision.py` `simulation_optimizer` gating)
remain in the tree.

**Phase ordering:** P65 → P66 → P67 (sequential — each removes the context the next audits).
P68 and P69 are independent and parallel-eligible after P65. P70 runs last.

---

## P65 — Dead Agent Class Removal — Not Started

**Goal:** Delete all agent classes unreachable from any runtime path, and the dead branches
that reference them. Lowest-risk, highest-volume deletion; establishes a clean base for P66.

Dependencies: P64 Done

### Batch B-01 — Delete dead agent class files (App Builder) — Done

| Task | Description | Status |
|---|---|---|
| T-421 | Delete `packages/agent/deprecated/` entirely (demand, inventory, supply_planning, finance_impact, sop + `__init__.py`). P38 kept them "until they create problems"; they now carry stale `sql_query` references (tool deleted in P55) and are imported only by a unit test of deprecated code. | Done |
| T-422 | Delete `packages/agent/cross_domain/` entirely (AnomalyDetectorAgent, DataEngineerAgent, EvaluatorAgent, SimulationOptimizerAgent). `CROSS_DOMAIN_AGENT_CLASSES == {}` means none are instantiable at runtime; only `tests/unit/test_output_builders.py` imports the module. | Done |
| T-423 | Delete unused `packages/agent/domain/` agent files: `exception.py`, `logistics.py`, `procurement.py`, `production.py`, `replenishment.py`, `supplier.py` — classes defined but never imported anywhere. Afterward audit `AgentBasedSpecialist` in `packages/agent/base.py`; if `ControlAgent` is its sole remaining subclass, keep the base class but remove any branches that exist only for deleted subclasses. | Done |
| T-424 | Remove the now-dead `CROSS_DOMAIN_AGENT_CLASSES` branch in `packages/agent/orchestrator/runtime.py::_make_agent`; simplify `packages/agent/orchestrator/roles.py` accordingly (keep `VALID_AGENT_ROLES` as the public lookup). | Done |

#### Defect: D-001

- Status: Open
- Severity: Medium
- Repro: `make typecheck`
- Observed: 4 mypy errors pre-dating P65 — `packages/tools/base.py:50` (no-any-return), `packages/tools/base.py:52`, `packages/agent/runtime.py:698`, `packages/agent/runtime.py:809` (unused-ignore). Discovered during P65 B-01 batch check; verified pre-existing via stash/restore.
- Expected: `make typecheck` exits 0 (P64 T-420 sign-off claimed all gates pass).
- Area: packages/tools, packages/agent
- Owner: App Builder
- Acceptance: `make typecheck` exits 0.

Dependencies: none

### Batch B-02 — Remove tests of deleted code + quality gate (Test/Review) — Not Started

| Task | Description | Status |
|---|---|---|
| T-425 | Delete `tests/unit/agent/test_sop_agent.py` and `tests/unit/test_output_builders.py`; audit `tests/unit/test_sop_roles.py` and any other test importing removed modules — delete or trim to surviving behavior only. | Not Started |
| T-426 | `make test-unit && make lint && make typecheck` — all pass. | Not Started |

Dependencies: B-01

---

## P66 — Orchestration Routing Simplification — Not Started

**Goal:** With ControlAgent as the only runtime agent, the multi-agent execution modes are
degenerate: `sequential_agents` and `planned_execution` can only ever produce a 1-element
control-agent sequence, and `decision.py` gates on `simulation_optimizer` results that can
never exist (`packages/agent/orchestrator/decision.py:97,241`). Collapse routing to the paths
that actually execute, without changing intent categories (they drive `_INTENT_TOOL_SUBSET`)
or the SSE event contract.

Dependencies: P65 Done

### Batch B-01 — ADR: routing collapse (Orchestrator) — Not Started

| Task | Description | Status |
|---|---|---|
| T-427 | ADR `docs/adr/2026-06-XX-orchestrator-routing-collapse.md` — document removal of `sequential_agents`/`planned_execution`/DAG execution modes and `simulation_optimizer`-dependent decision logic; state that the 6 intent categories and SSE `graph_node` event shape are preserved. | Not Started |

Dependencies: none

### Batch B-02 — Remove unreachable orchestration branches (App Builder) — Not Started

| Task | Description | Status |
|---|---|---|
| T-428 | `packages/agent/orchestrator/decision.py` — remove `simulation_optimizer`-gated candidate logic and any code reachable only from it; fold `weights.py` usage: if `resolve_weights` becomes dead, delete `weights.py`; if `decision_support` ranking survives via ControlAgent output, keep the minimal live path. | Not Started |
| T-429 | Collapse `_INTENT_MODE_MAP` in `routing.py` so every non-chat intent routes through the single-ControlAgent path; remove `run_dag_execution` and sequential multi-agent loops from `planning.py` and the corresponding `_node_run_planned`/`_node_run_dag` nodes in `session_orchestrator.py` (keep `_node_run_sequential` only if it is the surviving single-agent executor). SSE event shape must not change. | Not Started |
| T-430 | Update `packages/agent/orchestrator/prompts.py` intent-classification text and `validate_route` in `routing.py` to match the surviving modes. Keep all 6 intent categories. | Not Started |

Dependencies: B-01

### Batch B-03 — Test updates + quality gate (Test/Review) — Not Started

| Task | Description | Status |
|---|---|---|
| T-431 | Update or delete tests bound to removed paths: `test_dag_parallel_execution.py`, `test_decision_rank_candidates.py`, `test_routing.py`, `test_tool_isolation.py` (imports `orchestrator.weights`), `test_session_orchestrator_*` cases covering planned/DAG nodes. | Not Started |
| T-432 | `make test-unit && make lint && make typecheck && make test-playwright` — Playwright confirms the execution-trace UI is unaffected. | Not Started |

Dependencies: B-02

---

## P67 — Tool Layer Rationalization — Not Started

**Goal:** ~40 tool modules exist; P64 made the control allowlist derived from
`_INTENT_TOOL_SUBSET`, but the registry may still register tools no intent can reach
(candidate: `EvaluatorTool`). Make `create_tool_registry()` ↔ allowlists ↔ `docs/TOOLS.md`
mutually consistent and delete what nothing can call.

Dependencies: P66 Done

### Batch B-01 — Reachability audit + dead tool removal (App Builder) — Not Started

| Task | Description | Status |
|---|---|---|
| T-433 | Reachability audit: for every tool registered in `create_tool_registry()`, verify it appears in at least one `_ROLE_TOOL_ALLOWLIST` entry / `_INTENT_TOOL_SUBSET` list; produce the unreachable list in the batch report. | Not Started |
| T-434 | Delete unreachable tool modules and their registry entries. Keep classes used by non-LLM paths (`AuditLogTool` post-completion hook, `JobDispatchTool`, `TrainForecastTool` — per P64 B-02). | Not Started |
| T-435 | Update `docs/TOOLS.md` to exactly match the post-cleanup registry and allowlists. | Not Started |

Dependencies: none

### Batch B-02 — Orphaned tool tests + quality gate (Test/Review) — Not Started

| Task | Description | Status |
|---|---|---|
| T-436 | Delete unit tests for removed tools (`tests/unit/tools/`); confirm no cassette files in `tests/cassettes/` reference removed tools. | Not Started |
| T-437 | `make test-unit && make lint && make typecheck` — all pass. | Not Started |

Dependencies: B-01

---

## P68 — Frontend Dead Code Cleanup — Not Started

**Goal:** Remove unused frontend modules and exports accumulated across the P6–P44 UI
iterations. Parallel-eligible with P66/P67 (no shared files).

Dependencies: P65 Done (parallel-eligible with P66, P67)

### Batch B-01 — Unused module deletion (App Builder) — Not Started

| Task | Description | Status |
|---|---|---|
| T-438 | Delete `apps/web/data/mockInventoryShortageAnalysis.ts` — zero imports (only appears in `tsconfig.tsbuildinfo` cache). | Not Started |
| T-439 | Run an unused-export audit (`npx knip` or `ts-prune`) across `apps/web/`; manually verify and delete confirmed-unused components, hooks, feature modules, schemas, and types (audit candidates: `schemas/evaluations.ts`, `types/workspace.ts`, unused `features/*` hooks). Dynamic-import and Next.js convention files (`page.tsx`, `layout.tsx`) are exempt from deletion on tool output alone. | Not Started |
| T-440 | Dedupe overlapping execution-trace components if the audit confirms overlap (`components/ExecutionProgressPanel.tsx` vs `components/agent/ExecutionPanel.tsx`, `AgentNodeCard.tsx`); keep the variant the chat page renders. | Not Started |

Dependencies: none

### Batch B-02 — Quality gate (Test/Review) — Not Started

| Task | Description | Status |
|---|---|---|
| T-441 | Vitest suite (via Makefile target), `make test-playwright`, and `make build` — all pass. | Not Started |

Dependencies: B-01

---

## P69 — Dependency & Config Hygiene — Not Started

**Goal:** Align declared dependencies and config files with what the code actually uses.
Infra services themselves (Celery, Redis, compose definitions) are preserved per the
2026-06-10 scope decision.

Dependencies: P65 Done (parallel-eligible with P66–P68)

### Batch B-01 — pyproject / .env.example / Makefile audit (Infra) — Not Started

| Task | Description | Status |
|---|---|---|
| T-442 | `pyproject.toml`: move `pytest` and `pytest-asyncio` from `[project] dependencies` to `[tool.uv] dev-dependencies`; audit remaining runtime deps against actual imports (`celery`/`redis` stay — preserved infra). | Not Started |
| T-443 | `.env.example`: verify every variable against an actual `os.environ` read in the codebase; delete entries nothing reads; fix stale comments. | Not Started |
| T-444 | `Makefile`: remove targets referencing deleted paths; verify every target still runs after P65–P68 deletions. | Not Started |

Dependencies: none

### Batch B-02 — Quality gate (Test/Review) — Not Started

| Task | Description | Status |
|---|---|---|
| T-445 | `uv sync` succeeds from a clean lock state; `make test-unit && make lint && make typecheck` — all pass. | Not Started |

Dependencies: B-01

---

## P70 — Test Suite & Documentation Consolidation — Not Started

**Goal:** Final pass once all deletions land: remove redundant test coverage, then bring the
documentation set back in sync with the slimmed codebase.

Dependencies: P66 Done, P67 Done, P68 Done, P69 Done

### Batch B-01 — Test suite rationalization (Test/Review) — Not Started

| Task | Description | Status |
|---|---|---|
| T-446 | Remove any leftover `@pytest.mark.asyncio` decorators (`asyncio_mode = "auto"` is global — `.claude/rules/testing.md`). | Not Started |
| T-447 | Duplicate-coverage audit across `tests/unit/` (84 files; the control-agent and agent-runtime clusters are the largest). Merge or delete tests whose assertions are fully covered elsewhere; no unique assertion may be lost. | Not Started |
| T-448 | `make test-unit && make lint && make typecheck` — all pass; record test count before/after in the batch report. | Not Started |

Dependencies: none

### Batch B-02 — TASKS.md archive (Orchestrator) — Not Started

| Task | Description | Status |
|---|---|---|
| T-449 | Move P24–P64 phase detail sections from `docs/TASKS.md` to `docs/archive/v4/TASKS.md`, keeping only the Completed Phases summary table (~1,650 → ~200 lines). | Not Started |

Dependencies: none

### Batch B-03 — Doc reference sweep (App Builder) — Not Started

| Task | Description | Status |
|---|---|---|
| T-450 | Sweep `docs/DESIGN.md`, `docs/AGENT_ARCHITECTURE.md`, `docs/TOOLS.md`, `docs/ORCHESTRATOR.md` for references to modules removed in P65–P68 (deprecated/cross-domain agents, `sql_query`, removed routing modes, deleted tools/components) and update them to the post-refactoring state. | Not Started |

Dependencies: P65–P68 Done

