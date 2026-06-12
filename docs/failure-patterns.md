# Failure Patterns

Accumulated root causes from resolved Defect Tasks. Written by `/analyze-failure`.
Escalation actions tracked in `docs/prevention-policy.md §Applied Lever Log`.

---

## Pattern Table

| ID | Date | Defect | Root Cause Class | Pattern | Count | Lever Applied |
|---|---|---|---|---|---|---|
| FP-001 | 2026-06-07 | ad-hoc (P54後) | `test-gap` | `StubClaudeClient` が旧カスタム API (`stream(messages=...)`) を実装したまま残ったため、P54 で `_llm_client` が `BaseChatModel` に置き換わった後も `decision.py`・`runtime.py` の呼び出し漏れをユニットテストが検出できなかった | 1 | — |
| FP-002 | 2026-06-07 | ad-hoc (migration 0009後) | `agent-behavior` | `nl_query_tool.py` の `FEW_SHOT_EXAMPLES` にテーブル名をハードコードし AGENTS.md 73-74 の禁止ルールに違反したため、migration 0009 のテーブルリネーム (`inventory`→`inventory_snapshot`, `supply`→`supply_orders`) 後も few-shot 例が更新されず LLM が無効な SQL を生成し続けた | 1 | — |
| FP-003 | 2026-06-10 | D-001, D-002, D-009 | `agent-behavior` | Quality-gate tasks are signed off as Done without the corresponding gate being run against the final committed state: D-001 — `make typecheck` was not run at P64-Done, letting four mypy violations ship; D-002 — `make test-integration` was not run at any sign-off across P52–P54 (2026-06-07 to 2026-06-10), letting a breaking constructor-dependency change in `session_orchestrator.py` go undetected for three phases; D-009 — `make test-integration` was not included in P78's gate, so deterministic-routing changes broke two integration tests that went undetected until P85 sign-off | 3 | `new-test` + `prohibition` + `structural-change` |
| FP-004 | 2026-06-10 | D-003 | `design-contract` | A defect fix (D-002) deliberately duplicated test-stub infrastructure rather than sharing it, creating two independent implementations of the same contract with no synchronization mechanism; when P71 updated the unit-tier stub to be type-aware, the integration-tier copy remained positional, causing 8 integration tests to fail with `AttributeError` silently until programme sign-off | 1 | — |
| FP-005 | 2026-06-10 | D-004 | `test-gap` | A runtime 500 (`JSONResponse(content=<raw repo row>)` crashing on UUID/datetime) shipped because unit-test repo stubs returned pre-stringified JSON-native rows that were type-unfaithful to the real repository's asyncpg rows, so the serialization boundary was never exercised; the one real-stack signal — the failing `job_approval` Playwright spec — was dismissed as "pre-existing flaky (SSE timing)" at P76 sign-off without checking API logs, which showed repeated 500s | 1 | — |
| FP-006 | 2026-06-10 | D-005 | `design-contract` | A request-fatal runtime failure occurred because an LLM structured-output call remained on the critical path for a decision with zero degrees of freedom (`VALID_AGENT_ROLES == {"control"}`, total `_INTENT_MODE_MAP`): local-model output variance (`agents` ≠ exactly 1) violated a hard route invariant with no deterministic fallback; P66's routing collapse special-cased only `supply_chain` instead of removing the decision-free LLM call for all intents | 1 | — |
| FP-007 | 2026-06-10 | D-006 | `design-contract` | An API entry point (`POST /sessions/{id}/answer`) called `Command(resume=...)` unconditionally with no precondition check that a valid LangGraph checkpoint existed for the thread; the engine's silent fresh-start behavior (starting from START with empty state when no checkpoint is found) converted a missing-state precondition into a misleading deep crash (`KeyError: 'session_id'` inside `_node_classify_intent`) rather than an early, actionable rejection | 1 | — |
| FP-008 | 2026-06-10 | D-007 | `design-contract` | Session creation registered state across N stores (in-memory dict, broadcaster, DB row, asyncio task handle) but deletion tore down only a subset because no lifecycle contract enforced symmetric teardown — `asyncio.create_task` handles were never retained so tasks could not be cancelled, orphaning background runs that spammed FK-violation warnings; copy-paste divergence of the DB-recovery fallback (present only in `post_message`, absent from 4 sibling endpoints) compounded the inconsistency | 1 | — |
| FP-009 | 2026-06-10 | D-008 | `design-contract` | A guardrail verdict (rule-based findings verifier) was surfaced through the generic hard-failure path with a hardcoded unrelated reason string ("tool-loop guard" — a path that never sets blocked itself), so every verifier block was misreported AND displaced the prepared soft fallback text; compounding it, the fabrication heuristic (`\d` = any digit, no tool calls → blocked) had no content-type awareness, making legitimate code-writing answers fail stochastically depending on whether prose happened to contain a digit | 1 | — |
| FP-010 | 2026-06-12 | D-010 | `design-contract` | A lazy-resolving dict subclass (`_RoleToolAllowlist`) overrode only the access paths its author anticipated (`__getitem__`, `.get`), leaving the iteration paths (`.items()`, `.values()`) delegating directly to the base dict's empty storage; P85's `get_registry` consumed the allowlist via `.items()` — an unhooked path — so the registry returned `tools: []` on every fresh-process call until any agent run happened to trigger `__getitem__` and populate the cache; the defect shipped signed-off because P85's live verification was deferred to the user rather than exercised as part of the phase gate | 1 | — |

---

## Root Cause Classes

| Class | Meaning |
|---|---|
| `agent-behavior` | Agent violated an existing rule or made an incorrect inference — the spec was correct |
| `design-contract` | Public interface, schema, or contract was ambiguous or missing a constraint |
| `test-gap` | Behavior was correct but no test caught the regression |
| `spec-ambiguity` | Requirement was underspecified; the agent had no way to know the right behavior |

---

## Escalation Rule

When `Count` for any pattern reaches **2**: invoke `/harden-system <FP-NNN>`.
The next phase must not begin until the prevention lever is applied.
