---
name: analyze-failure
description: Analyze a resolved Defect Task to extract root cause and record it in docs/failure-patterns.md. Invoked after Orchestrator marks a Defect Resolved. Usage: /analyze-failure <D-NNN>
---

# Failure Analyst — SKILL

## Purpose

Separate learning from fixing. After a defect is resolved, extract why it happened, classify the root cause, and record it in `docs/failure-patterns.md`. Detect recurrence. Trigger prevention escalation when Count reaches 2.

This skill handles **analysis only**. The fix is already managed by the Defect Task. Do not re-open or modify the Defect Task block in `docs/TASKS.md`.

## Invocation

```
/analyze-failure <D-NNN>
```

## Process

1. **Read the defect** — read D-NNN from `docs/TASKS.md`. Confirm Status is `Resolved`.
2. **Read the fix** — run `git log --oneline -10` to find the resolution commit, then `git show <hash>` to read the diff.
3. **Fill the failure anatomy**:
   - **Symptom**: what was observed (copy from Defect `Observed:` field)
   - **Root cause**: *why* it happened — dig past the surface to the mechanism. "Agent used an f-string" is surface. "No structural enforcement prevented direct schema construction outside the canonical provider" is root cause.
   - **Root cause class**: one of `agent-behavior | design-contract | test-gap | spec-ambiguity`
   - **Pattern**: one sentence — "X happened because Y was not enforced at Z"
4. **Check for recurrence** — read `docs/failure-patterns.md`. Does an existing pattern row describe the same root cause mechanism?
5. **If new pattern**: append a new row to `docs/failure-patterns.md` (Count=1, Lever Applied=—). Assign next FP-NNN in sequence.
6. **If existing pattern**: increment Count in that row. If Count reaches **2**, print: `"Pattern FP-NNN has recurred. Invoke /harden-system FP-NNN before the next phase begins."`
7. **Cluster check** — recount rows sharing this root cause class dated within the trailing 30 days. If the count reaches **3**, print: `"Same-class cluster detected (<class> x N within 30 days). Run a preventive class audit per docs/prevention-policy.md §Escalation Rule before the next phase begins."`
8. **Output analysis summary** (see Output Format below).

## Root Cause Classes

| Class | Meaning |
|---|---|
| `agent-behavior` | Agent violated an existing rule or made an incorrect inference — the spec was correct |
| `design-contract` | Public interface, schema, or contract was ambiguous or missing a constraint |
| `test-gap` | Behavior was correct but no test caught the regression |
| `spec-ambiguity` | Requirement was underspecified; the agent had no way to know the right behavior |

## What NOT to Classify as a Pattern

Do not add a row to `docs/failure-patterns.md` for:
- Build/environment flukes (DB not started, network timeout, Docker not running) — these are infrastructure issues, not agent failure patterns
- One-off typos in generated code with no systemic root cause
- Spec-ambiguity defects where the spec has since been clarified and the same ambiguity cannot recur

## Output Format

```
## Failure Analysis: D-NNN

**Symptom:** <copied from Defect Observed field>
**Root cause:** <mechanism, not surface>
**Root cause class:** agent-behavior | design-contract | test-gap | spec-ambiguity
**Pattern:** <one sentence>

**failure-patterns.md update:**
  Row: FP-NNN | YYYY-MM-DD | D-NNN | <class> | <pattern> | <count> | —

**Next action:** record-only | Invoke /harden-system FP-NNN
```

## Required Reading

- `docs/TASKS.md` — locate D-NNN and read the Defect block
- `docs/failure-patterns.md` — check for existing patterns before appending

## Write Authority

- May write to: `docs/failure-patterns.md` (append rows only)
- Must not modify: `docs/TASKS.md`, `AGENTS.md`, `.claude/rules/`, or any code files
