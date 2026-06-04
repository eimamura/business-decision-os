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

### Batch B-02 — Backend abort race: stale run silently dropped (App Builder) — Not Started

| Task | Description | Status |
|---|---|---|
| T-163 | `state.py` に `session_run_ids: dict[str, str]` を追加し、`POST /messages` の `_run_and_signal` 内の各 `queue.put()` 前に run_id チェックを実施。セッション削除時にも run_id をクリーンアップ | Not Started |

Dependencies: B-01

### Batch B-03 — Frontend: sendAskUserAnswer missing invalidateQueries (App Builder) — Not Started

| Task | Description | Status |
|---|---|---|
| T-164 | `sendAskUserAnswer` の `done` ハンドラに `queryClient.invalidateQueries({ queryKey: queryKeys.sessions.all })` を追加 | Not Started |

Dependencies: none

### Batch B-04 — Tests (Test/Review) — Not Started

| Task | Description | Status |
|---|---|---|
| T-165 | broadcaster cleanup・run_id stale drop・SSE error break に対するユニットテスト | Not Started |
| T-166 | 既存ユニットテスト全通過確認（`make test-unit`） | Not Started |

Dependencies: B-01, B-02, B-03
