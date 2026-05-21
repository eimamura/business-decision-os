# DECISIONS.md

## Purpose

Lightweight daily log of key design decisions.
Write here first; promote to `docs/ADR/` when a decision is architectural, affects public interfaces, or requires future accountability.

See `AGENTS.md` §Design Records for the two-tier decision system.

---

## Decision format

```
## Decision: <title>
Date: YYYY-MM-DD
Reason: <why this was chosen over alternatives>
Consequence: <what this decision locks in>
Reversal cost: low | medium | high
```

---

## Decision: Orchestrator is a single agent, not split into Planner + Router

Date: 2026-05-21

Reason: For the current system size, separating Planner and Router creates unnecessary complexity without measurable benefit. A single Orchestrator that handles intent analysis, planning, routing, state management, aggregation, conflict detection, and response generation is simpler to reason about and maintain.

Consequence: Planner and Router remain internal responsibilities of Orchestrator. They MUST NOT be extracted into separate runtime agents without revisiting this decision.

Reversal cost: medium (requires new inter-agent protocol and state handoff)

---

## Decision: Tool Layer is separate from Agent implementation

Date: 2026-05-21

Reason: Embedding data access or calculation logic inside agents creates tight coupling and makes testing, reuse, and responsibility analysis harder. Tools are execution primitives; agents are reasoning and routing units.

Consequence: Agents MUST NOT contain direct SQLAlchemy models, database queries, or external API calls. All execution capability lives in `packages/tools/`. Any violation is a defect, not a style issue.

Reversal cost: high (requires restructuring every agent that currently holds execution logic)

---

## Decision: Memory is six typed stores, not raw conversation history

Date: 2026-05-21

Reason: A flat conversation history is insufficient for a decision-support system that must track reasoning, domain knowledge, user context, and working state separately. Typed stores make the memory model explicit and auditable.

Consequence: `packages/memory/` must export: `ShortTermMemory`, `WorkingMemory`, `LongTermMemory`, `DecisionMemory`, `UserMemory`, `DomainMemory`. Raw `dict`-typed memory parameters in agent interfaces are prohibited.

Reversal cost: medium (requires migrating existing memory usage across agents)

---

## Decision: Domain Agents are a capability map first, runtime units second

Date: 2026-05-21

Reason: Creating 7+ independent runtime agents from the start adds operational overhead before the domain responsibilities are well-understood. Responsibility boundaries should be clear in code structure before they are enforced by process separation.

Consequence: Multiple domain capabilities MAY share a single runtime agent in early phases. However, class and module boundaries MUST reflect the DESIGN.md agent classification table, so future separation is a structural refactor, not a rewrite.

Reversal cost: low (splitting a class boundary into a runtime boundary is incremental)

---

## Decision: Guardrail is an explicit layer, not scattered if-checks

Date: 2026-05-21

Reason: Ad-hoc permission and approval checks scattered across agent and router code are invisible to auditors, difficult to test in isolation, and create implicit coupling. A dedicated Guardrail module makes the safety boundary visible and testable.

Consequence: All permission checks, approval routing, and audit decisions MUST go through the Guardrail Layer API (`can_execute`, `needs_approval`, `audit_required`). Scattered checks are a defect.

Reversal cost: medium (requires consolidating all existing checks and updating callers)

---

## Decision: Lakehouse schema is frozen during this refactoring

Date: 2026-05-21

Reason: `packages/lakehouse/` (bronze/silver/gold) schema changes require a separate data migration plan with impact analysis on downstream consumers. Bundling schema changes into the architecture refactoring would expand scope and risk.

Consequence: `packages/lakehouse/` bronze, silver, and gold layer schemas are not modified during Phases 0–6. Any lakehouse change requires a separate plan.

Reversal cost: n/a (decision is about scope boundary, not architecture)

---

## Decision: Test execution deferred to Phase 6 during Phases 1–5

Date: 2026-05-21

Reason: Running the full test suite at each phase checkpoint (1–5) creates long feedback loops during rapid structural refactoring. The test suite takes meaningful time and some tests depend on infrastructure (PostgreSQL, live endpoints) that complicates CI during intermediate states. Phase 0 already locked all external contracts with 10 dedicated contract tests; re-running them at each phase would catch nothing that a well-scoped grep cannot catch faster.

Consequence: Phase 1–5 checkpoints use static analysis only (grep, mypy, ruff). The full pytest suite, including Phase 0 contract tests, runs exactly once in Phase 6. Any regression introduced during Phases 1–5 will be detected at that point. Agents must not invoke `pytest` as a phase checkpoint step during Phases 1–5.

Reversal cost: low (add `pytest` back to individual phase checkpoints if the deferred approach is insufficient)
