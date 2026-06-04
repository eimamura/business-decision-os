# ADR: S&OP Specialist Roles — SpecialistRole Extension

**Date:** 2026-06-04  
**Status:** Accepted  
**Phase:** P32–P35

---

## Background

The Business Decision OS requires a full S&OP (Sales & Operations Planning) cycle:
Demand → Inventory → Supply → Finance → Integrated Decision.

Two new domain agents are needed (`SupplyPlanningAgent`, `FinanceImpactAgent`) plus a synthesis agent (`SopAgent`). Each maps to a new role value in the `SpecialistRole` Literal defined in `packages/agent/base.py`. The `SpecialistRole` type is used in both the `Specialist` protocol (`role: SpecialistRole`) and `ToolContext` (`specialist_role: SpecialistRole`).

---

## Candidates Considered

**Option A — Widen SpecialistRole Literal (chosen)**  
Add `"supply_planning"`, `"finance_impact"`, `"sop"` to the existing Literal. Existing values and all downstream usage are unchanged. `AgentBasedSpecialist.__init__` accepts `role: str` (not `SpecialistRole`) so no runtime breakage.

**Option B — Use existing roles with a sub-role tag**  
Map supply planning → `"procurement"`, finance → existing cross-domain agent. Rejected: the responsibilities of SupplyPlanning (supply feasibility, lead times, gap analysis) and Finance (cost impact, scenario comparison) are distinct enough from existing roles to warrant dedicated roles. Forcing them into `"procurement"` would pollute the tool allowlist and system prompt design.

**Option C — Cross-domain agent pattern**  
Add to `CROSS_DOMAIN_AGENT_CLASSES` rather than `DOMAIN_AGENT_ROLES`. Rejected: supply planning and finance impact are domain-owned responsibilities, not reusable cross-domain utilities. SopAgent is an integrating agent, not a cross-domain capability.

---

## Decision

Widen `SpecialistRole` Literal with three new values:
- `"supply_planning"` — supply feasibility and gap analysis against demand
- `"finance_impact"` — cost impact analysis (holding, stockout, expedite scenarios)
- `"sop"` — final S&OP synthesis after all domain agents have run

---

## Rationale

- Backwards-compatible: widening a Literal does not break any existing code path
- Consistent: follows the same pattern as all existing domain roles
- Isolation: each role gets its own tool allowlist and system prompt; no role leaks into another
- Testable: each agent is independently unit-testable without other agents

---

## Tradeoffs

- `SpecialistRole` Literal grows from 12 to 15 values — minor maintenance overhead
- Revenue impact analysis is out of scope in this ADR (no `price_history` table in schema); a follow-on ADR will cover it when that table is added

---

## Reversibility

Low-risk. Removing a Literal value would be a breaking change, but all three roles are needed for the S&OP MVP. Re-evaluation trigger: if S&OP is replaced by a different orchestration architecture.
