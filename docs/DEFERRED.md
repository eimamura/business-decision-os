# DEFERRED.md

## Purpose

Explicitly lock out work that is NOT part of this refactoring.

During large-scale refactoring, AI agents and developers tend to expand scope by adding "while we're here" improvements. This document prevents that. If an item is listed here, it MUST NOT be implemented without explicit human authorization and a TASKS.md update.

---

## Deferred Items

### Multi-agent Runtime Separation

**What**: Running each Domain Agent (demand, inventory, replenishment, etc.) as a separate process or service with its own deployment unit.

**Why deferred**: Current system size does not justify the operational overhead of inter-service communication, independent deployment pipelines, and distributed state management. Responsibility boundaries are being established in code structure first.

**Condition to revisit**: When a specific Domain Agent has measurably different scaling, latency, or availability needs from the Orchestrator, and that difference is causing production problems.

---

### Advanced Optimization Engine

**What**: Full MILP, genetic algorithm, or constraint programming optimization replacing the current heuristics in `packages/optimization/replenishment.py`.

**Why deferred**: Existing EOQ/reorder-point heuristics are sufficient for MVP validation of the agent architecture. Building a sophisticated optimization engine now is premature before user value is confirmed.

**Condition to revisit**: When optimization quality (not agent architecture quality) is the measured bottleneck, supported by benchmark data comparing heuristic vs optimal outputs on real data.

---

### Full Autonomous Action Execution

**What**: Agents that execute purchase orders, inventory movements, or supplier actions without human approval.

**Why deferred**: Guardrail Layer and approval workflow must be validated with real user data before removing human-in-the-loop. Autonomous execution without a proven safety net is premature.

**Condition to revisit**: After 3+ months of approval workflow usage data showing false-positive rate (unnecessary human interventions) below 5% on a stable workload.

---

### Complex Multi-approver Workflow

**What**: Multi-step, multi-approver, time-gated, or delegated approval chains beyond the current single-approver model.

**Why deferred**: The current model in `packages/state/approvals.py` (pending → approved/rejected/needs_revision/expired) covers all identified use cases. Complexity here is premature.

**Condition to revisit**: When a real, identified use case requires multi-step approval that cannot be modeled with the current state machine. Must be driven by user need, not architectural preference.

---

### UI Redesign

**What**: New frontend architecture, component library swap, routing redesign, or significant UX overhaul in `apps/web/`.

**Why deferred**: UI quality is not the current constraint. The agent reasoning layer needs to be validated before investing in UI polish or redesign.

**Condition to revisit**: After agent behavior is stable and user research specifically identifies UI as the blocker to adoption. Not before.

---

### Lakehouse Schema Changes

**What**: Modifying bronze, silver, or gold layer schemas in `packages/lakehouse/`.

**Why deferred**: Schema changes at the lakehouse layer require impact analysis on all downstream consumers and a separate data migration plan. Bundling this into the architecture refactoring would expand scope and create migration risk.

**Condition to revisit**: Via a separate, dedicated migration plan. Not in MIGRATION_PLAN.md Phases 0–6.

---

### packages/prediction/ Build-out

**What**: Implementing a first-party demand forecasting model in `packages/prediction/`.

**Why deferred**: `packages/tools/forecast_tool.py` covers current forecasting needs by calling existing data. A first-party prediction model adds ML infrastructure before the need is confirmed.

**Condition to revisit**: When `ForecastTool` latency, accuracy, or data access constraints become the measured bottleneck for agent decision quality.
