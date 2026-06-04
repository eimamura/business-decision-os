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

---

## Active Phase

None.

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

## Next Phase

To be defined. Use bdos-orchestrator to plan the next phase.
