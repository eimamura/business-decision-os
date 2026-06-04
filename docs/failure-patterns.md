# Failure Patterns

Accumulated root causes from resolved Defect Tasks. Written by `/analyze-failure`.
Escalation actions tracked in `docs/prevention-policy.md §Applied Lever Log`.

---

## Pattern Table

| ID | Date | Defect | Root Cause Class | Pattern | Count | Lever Applied |
|---|---|---|---|---|---|---|

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
