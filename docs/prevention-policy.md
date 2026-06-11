# Prevention Policy

Governs how recurring failure patterns are translated into durable prevention mechanisms.
Referenced by `/harden-system`.

---

## Prevention Priority (Strongest to Weakest)

| Priority | Lever | Description | When to use |
|---|---|---|---|
| 1 | `structural-change` | Make the mistake physically impossible — schema constraint, type system, required abstraction, import guard | Defect was caused by an incorrect value or call that the type system or architecture could block |
| 2 | `new-test` | Make the mistake immediately visible — autouse fixture, lint rule, pre-commit hook, CI check | Defect is detectable by automated check but is not currently tested |
| 3 | `prohibition` | Explicit "Never X because Y" added to `AGENTS.md §Prohibitions` | Agent behavioral mistake that can't be structurally prevented; needs a named rule |
| 4 | `claude-md-entry` | Short rule in `CLAUDE.md` for always-on context | Cross-cutting behavioral reminder; not role-specific |
| 5 | `doc-update` | Clarify the relevant spec in `docs/` | Root cause class is `spec-ambiguity` — the spec itself was missing or wrong |

---

## Lever Selection Rule

Before applying lever 3–5 (rules/docs), answer: **"Can we make this mistake physically impossible?"**
- Yes → apply lever 1 or 2 instead.
- No → proceed to lever 3, then 4, then 5.

Rationale: rules can be forgotten across session boundaries; structural constraints cannot.

---

## Escalation Threshold

`Count >= 2` for any pattern in `docs/failure-patterns.md` → invoke `/harden-system <FP-NNN>`.

---

## Applied Lever Log

Actions taken by `/harden-system`. Append-only.

| FP-ID | Date | Lever | Change Made |
|---|---|---|---|
| FP-003 | 2026-06-10 | `new-test` + `prohibition` | Added `uv run mypy` step to `.github/workflows/lint-test.yml` (CI now blocks on typecheck); added proof-of-execution requirement (gate + exit_code + output_tail) to `bdos-test-review` SKILL.md §Quality Gates and `bdos-orchestrator` SKILL.md §Run Mode step 8; added prohibition to `AGENTS.md §Prohibitions` banning sign-offs without exit-code evidence |
| FP-003 | 2026-06-11 | `structural-change` | Escalated after Count=3 (D-009): replaced vague "full Quality Gates" description in `bdos-orchestrator` SKILL.md §Run Mode step 8 with an explicit mandatory gate set (six named commands including `make test-integration`); sign-off acceptance rule now requires a `make test-integration` gate row by name — omission or "N/A" is a structural rejection. Added complementary prohibition to `AGENTS.md §Prohibitions` naming integration tests as non-omissible at every phase sign-off |
