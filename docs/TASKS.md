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
