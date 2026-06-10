# Failure Patterns

Accumulated root causes from resolved Defect Tasks. Written by `/analyze-failure`.
Escalation actions tracked in `docs/prevention-policy.md §Applied Lever Log`.

---

## Pattern Table

| ID | Date | Defect | Root Cause Class | Pattern | Count | Lever Applied |
|---|---|---|---|---|---|---|
| FP-001 | 2026-06-07 | ad-hoc (P54後) | `test-gap` | `StubClaudeClient` が旧カスタム API (`stream(messages=...)`) を実装したまま残ったため、P54 で `_llm_client` が `BaseChatModel` に置き換わった後も `decision.py`・`runtime.py` の呼び出し漏れをユニットテストが検出できなかった | 1 | — |
| FP-002 | 2026-06-07 | ad-hoc (migration 0009後) | `agent-behavior` | `nl_query_tool.py` の `FEW_SHOT_EXAMPLES` にテーブル名をハードコードし AGENTS.md 73-74 の禁止ルールに違反したため、migration 0009 のテーブルリネーム (`inventory`→`inventory_snapshot`, `supply`→`supply_orders`) 後も few-shot 例が更新されず LLM が無効な SQL を生成し続けた | 1 | — |
| FP-003 | 2026-06-10 | D-001, D-002 | `agent-behavior` | Quality-gate tasks are signed off as Done without the corresponding gate being run against the final committed state: D-001 — `make typecheck` was not run at P64-Done, letting four mypy violations ship; D-002 — `make test-integration` was not run at any sign-off across P52–P54 (2026-06-07 to 2026-06-10), letting a breaking constructor-dependency change in `session_orchestrator.py` go undetected for three phases | 2 | `new-test` + `prohibition` |

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
