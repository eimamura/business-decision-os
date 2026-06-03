# ADR: Remove `Tool.requires_approval` from Public Protocol

**Date:** 2026-06-03  
**Status:** Accepted

---

## Context

The `Tool` Protocol (public interface, `packages/tools/base.py`) declares two overlapping
fields for tool safety classification:

```python
requires_approval: bool          # original field
safety_level: Literal["read_only", "write", "hitl"]   # added in T-018
```

`requires_approval` was the original way to flag tools that need human approval before
execution. T-018 (P2 phase) introduced `safety_level` as a richer 3-level classification.
At that time, `requires_approval` was kept for backwards compatibility.

Audit (2026-06-03) confirmed: **no production code reads `requires_approval`** after the
`safety_level` migration. All routing in `ToolRegistry.filter_for_user_role()` branches
exclusively on `safety_level`. The field exists in every tool implementation but is never
consumed by any caller.

---

## Decision

Remove `requires_approval: bool` from the `Tool` Protocol and from all concrete tool
implementations.

---

## Rationale

- **Dead code:** No production code path reads this field.
- **Simpler Protocol:** Removing it reduces the surface area of the `Tool` public interface.
- **No migration risk:** The field has no DB column, no SSE event, and no frontend binding.
  Its removal is purely a Python type/attribute deletion.

---

## Candidates Considered

**A. Remove `requires_approval` entirely** ← chosen  
All routing uses `safety_level`. No consumer needs `requires_approval`.

**B. Keep both fields indefinitely**  
Adds noise to the Protocol and every tool implementation. Dead code that future
maintainers must reason about.

**C. Derive `requires_approval` from `safety_level` as a property**  
Unnecessary indirection. No caller needs it.

---

## Trade-offs

| Aspect | Impact |
|---|---|
| Breaking change | Yes — any external tool implementation that declares `requires_approval` will need updating |
| Internal impact | Low — all tool implementations in `packages/tools/` are updated atomically |
| Test changes | Unit tests that reference `requires_approval` on tool fixtures must be updated |

---

## Consequences

- `Tool` Protocol loses `requires_approval: bool`
- All concrete tools (`SqlTool`, `ForecastTool`, `SimulationTool`, `JobDispatchTool`,
  `ApprovalTool`, `MemoryWriteTool`, `NlQueryTool`, `GuardrailTool`, `SchemaContextTool`)
  remove the field declaration
- `ToolRegistry` and all routing logic: unchanged (already uses `safety_level` only)
- Frontend recommendations page that reads `requires_approval` from the DB response:
  that value comes from `decision_sessions` table, not the `Tool` Protocol — unaffected

## Re-evaluation Triggers

- If an external plugin system is introduced that depends on `Tool.requires_approval`
