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

## Decision: SessionOrchestrator is a single runtime component, not split into Planner + Router

Date: 2026-05-21

Reason: For the current system size, separating Planner and Router creates unnecessary complexity without measurable benefit. A single SessionOrchestrator that handles intent classification, chat/QA handling, goal resolution, planning, routing, execution control, state management, aggregation, conflict detection, and response generation is simpler to reason about and maintain.

Consequence: Planner and Router remain internal responsibilities of SessionOrchestrator. They MUST NOT be extracted into separate runtime agents without revisiting this decision.

Reversal cost: medium (requires new inter-agent protocol and state handoff)

---

## Decision: Runtime orchestrator is named SessionOrchestrator

Date: 2026-05-21

Reason: The runtime orchestrator operates over a user session, not only over implementation phases, goals, or final decisions. It receives utterances and distinguishes chat, question answering, exploration, consultation, and explicit goal-directed tasks before planning, routing, executing, aggregating, and synthesizing responses.

Consequence: `PhaseOrchestrator` is renamed to `SessionOrchestrator`. Planner, Router, Executor, Aggregator, Intent Classifier, Chat / QA Handler, Goal Resolver, and Response Synthesizer remain internal responsibilities rather than independent runtime agents.

Reversal cost: low (rename imports and public documentation)

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

## Decision: Phase 4 specialist → classified agent mapping

Date: 2026-05-21

Reason: Phase 4 required explicit documentation of how pre-classification `specialists/` roles map to the DESIGN.md agent table.

Mapping:
- `forecast` → `DemandAgent` (demand forecasting is the primary demand-domain capability)
- `inventory` → `InventoryAgent`
- `procurement` → `ProcurementAgent`
- `production` → `ProductionAgent`
- `cost` — removed as a standalone role; supply-cost reasoning is distributed across domain agents
- `domain_expert` — remains an orchestrator-internal role; not a classified agent
- `data_engineer`, `simulation_optimizer`, `evaluator`, `anomaly_detector` — are active Cross-Domain Agents under `packages/agent/cross_domain/`

New agents added with no pre-existing equivalent: `ReplenishmentAgent`, `SupplierAgent`, `LogisticsAgent` (Domain); `ExceptionAgent`, `ScenarioAgent`, `RankingAgent`, `RootCauseAgent` (Analytical).

Consequence: `packages/agent/specialists/` and the legacy `packages/agent/pipeline/` package are deleted. All base classes live in `packages/agent/base.py`. Cross-domain runtime agents live in `packages/agent/cross_domain/` and are instantiated by SessionOrchestrator.

Reversal cost: low (the base classes and patterns are unchanged; only the directory structure moved)

---

## Decision: Guardrail is an explicit layer, not scattered if-checks

Date: 2026-05-21

Reason: Ad-hoc permission and approval checks scattered across agent and router code are invisible to auditors, difficult to test in isolation, and create implicit coupling. A dedicated Guardrail module makes the safety boundary visible and testable.

Consequence: All permission checks, approval routing, and audit decisions MUST go through the Guardrail Layer API (`can_execute`, `needs_approval`, `audit_required`). Scattered checks are a defect.

Reversal cost: medium (requires consolidating all existing checks and updating callers)

---

## Decision: Guardrail module placed in packages/tools/, not a new packages/guardrails/

Date: 2026-05-21

Reason: DESIGN.md Monorepo Layout does not list `packages/guardrails/`. Adding a new top-level package requires an ADR. Placing `guardrail.py` inside `packages/tools/` avoids that overhead while still centralising the three public functions.

Consequence: `packages/tools/guardrail.py` is the single source of truth for `can_execute()`, `needs_approval()`, `audit_required()`, `classify_risk()`. A future ADR may promote it to its own package.

Reversal cost: low (rename/move the file and update imports)

---

## Decision: Phase 3 checkpoint grep has 3 known-acceptable residual hits

Date: 2026-05-21

Reason: The P3-5 grep (`requires_approval\|can_execute` in `packages/agent/`) matches three lines in `packages/agent/orchestrator/__init__.py` — all are Pydantic keyword args or SSE event dict keys referencing the `Recommendation.requires_approval` schema field. The inline logic `risk_level in ("high","medium")` has been extracted to `needs_approval()` in guardrail. These hits are schema field references, not scattered approval logic.

Consequence: The 3 hits at orchestrator lines 420, 610, 626 are permanently acceptable. Renaming the `Recommendation.requires_approval` field would require touching the DB schema and multiple callers — not worth the churn.

Reversal cost: n/a (accepted exception, not a reversible decision)

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
