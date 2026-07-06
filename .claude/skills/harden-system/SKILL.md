---
name: harden-system
description: Escalate a recurring failure pattern (Count >= 2 in docs/failure-patterns.md) to a permanent prevention mechanism. Usage: /harden-system <FP-NNN>
---

# Prevention Architect — SKILL

## Purpose

Convert a recurring failure pattern into the strongest possible prevention mechanism.
Structural changes beat rules; tests beat documentation.

## Invocation

```
/harden-system <FP-NNN>
```

## Process

1. **Read the pattern** — read FP-NNN from `docs/failure-patterns.md`. Read its root cause class, pattern text, and current Count.
2. **Read lever policy** — read `docs/prevention-policy.md §Prevention Priority`.
3. **Select lever** — ask: "Can we make this mistake physically impossible?" Work down the priority list until you find the strongest feasible lever:
   - `structural-change` → `new-test` → `prohibition` → `claude-md-entry` → `doc-update`
4. **Implement the lever**:
   - `structural-change`: describe the required structural change. If it touches `apps/` or `packages/`, hand off to App Builder with a specific task description. If it only touches `.claude/` or `docs/`, implement directly.
   - `new-test`: describe the required autouse fixture, lint rule, or CI check. Hand off to Test/Review if it touches `tests/`.
   - `prohibition`: draft the one-line addition to `AGENTS.md §Prohibitions`. Format: `"Never X because Y."` Check that the prohibition is not already covered by an existing entry. Implement directly.
   - `claude-md-entry`: draft the short always-on entry for `CLAUDE.md`. Implement directly.
   - `doc-update`: clarify the relevant spec in `docs/`. Implement directly.
5. **Update `docs/failure-patterns.md`** — set `Lever Applied` to the chosen lever name in the FP-NNN row.
6. **Append to `docs/prevention-policy.md §Applied Lever Log`** — `FP-NNN | YYYY-MM-DD | <lever> | <one-line description of change made>`.

## Output Format

```
## Harden System: FP-NNN

**Pattern:** <copied from failure-patterns.md>
**Root cause class:** <class>
**Lever selected:** <lever>
**Why this lever:** <reason this is the strongest feasible option>

**Change made:**
<description of what was changed and where>

**failure-patterns.md:** Lever Applied = <lever> (row FP-NNN updated)
**prevention-policy.md Applied Lever Log:** FP-NNN | <date> | <lever> | <change>
```

## Required Reading

- `docs/failure-patterns.md` — pattern to harden
- `docs/prevention-policy.md` — lever priority and applied log
- `AGENTS.md §Prohibitions` — check for existing prohibitions before adding a duplicate

## Write Authority

- May write to: `docs/failure-patterns.md`, `docs/prevention-policy.md`, `AGENTS.md §Prohibitions`, `CLAUDE.md`, `.claude/rules/*.md`
- Structural code changes (`apps/`, `packages/`): hand off to App Builder — describe task, do not implement directly
- Test changes (`tests/`): hand off to Test/Review — describe required test, do not implement directly
