# ADR: Risk-Classified Auto-Execution Policy

**Date:** 2026-05-20
**Status:** Accepted
**Scope:** T-8001 (Phase 8 — Semi-Autonomous Execution)

## Context

Prior to Phase 8, every recommendation emits `awaiting_approval` and blocks on human review regardless
of risk level. This creates friction for routine low-risk decisions (service_level ≥ 0.95).

The DESIGN.md §Phase Progression lists Phase 8 as "Semi-Autonomous Execution: Risk-classified
auto-execution policy". The `recommendation_ready` SSE event already carries `risk_level` and
`requires_approval`. A new field `auto_execute` is needed to communicate the disposition to the client.

## Decision

1. **Policy**: LOW-risk recommendations (`service_level ≥ 0.95`) are auto-executed without human review.
   MEDIUM/HIGH-risk recommendations continue to require human approval.

2. **SSE schema change** (additive, backward-compatible):
   - `recommendation_ready` gains `auto_execute: bool`
   - New event type `auto_executed` is added to signal completion without an approval gate

3. **Orchestrator change**: when `auto_execute=True`, skip the `awaiting_approval` emission; emit
   `auto_executed` event with the same `recommendation_id`.

4. **No DB change**: `approvals` table is only written when `requires_approval=True`. Auto-executed
   decisions write directly to `completed` status on the session.

## Consequences

- LOW-risk decisions complete in one SSE round-trip
- The `awaiting_approval` event is only emitted for MEDIUM/HIGH risk
- Web client must handle the new `auto_executed` event type
- `requires_approval` on `Recommendation` remains the ground truth; `auto_execute` on the SSE event
  is derived from it (inverted: `auto_execute = not requires_approval`)
