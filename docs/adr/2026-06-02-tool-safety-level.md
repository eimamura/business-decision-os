# ADR: Add `safety_level` to Tool Protocol

**Date:** 2026-06-02  
**Status:** Accepted  
**Decider:** bdos-orchestrator  

---

## Context

The `Tool` protocol in `packages/tools/base.py` currently carries only a `requires_approval: bool` flag.
As we implement 2-layer role × intent tool access control (T-013), the runtime needs to filter tools
by a tripartite safety classification before applying the per-role allowlist.

Three safety levels are required:

| Level | Meaning |
|---|---|
| `read_only` | Queries and lookups — no side effects. Safe for all user roles. |
| `write` | Mutations or external actions that change state. Restricted to `manager` / `admin`. |
| `hitl` | Human-in-the-loop: the agent pauses and awaits explicit human approval before execution. |

The existing `requires_approval: bool` maps directly to `hitl`; it is retained for backwards
compatibility with existing tool implementations but is superseded by `safety_level` for routing logic.

## Decision

Add `safety_level: Literal["read_only", "write", "hitl"]` as a **required** attribute on the `Tool`
protocol. All registered tools must declare it. `ToolRegistry` gains two new query methods:
`list_read_only()` and `list_hitl_tools()`.

This is a **public interface change** to `Tool` — every concrete tool implementation must be updated
to include `safety_level`.

## Alternatives Considered

1. **Derive safety level from `requires_approval`** — insufficient; `write` and `hitl` are distinct.
   A `write` tool changes state without requiring a pause; a `hitl` tool always pauses for approval.
2. **Separate registry per level** — more data structures, harder to add a new tool in one place.
3. **Policy config file** — decoupled but risks drift between the file and the tool's actual behavior.

## Consequences

- All `Tool` implementations must add `safety_level`.
- `ToolRegistry.list_for_role()` continues to work unchanged; T-013 adds a separate `filter_by_user_role()` that intersects with `safety_level`.
- `requires_approval: bool` is kept for existing tools but treated as a derived hint (`safety_level == "hitl"` implies `requires_approval == True`).
