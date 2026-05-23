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

## Decision: Specialist wire fields remain stable while internal planning uses execution roles

Date: 2026-05-21

Superseded for SSE/API orchestrator events by `docs/ADR/2026-05-21-user-query-orchestrator-flow.md`.
`SpecialistTask`, `SpecialistResult`, `ToolContext.specialist_role`, and LLM usage fields remain stable.

Reason: `specialist_role`, `SpecialistTask`, and `SpecialistResult` are already used as API, SSE, persistence, and Python contract surfaces. Renaming those public fields would create churn without improving runtime behavior. The remaining internal DAG-planning vocabulary should still match the current DESIGN.md model, where work is routed to execution roles implemented by domain agents and cross-domain agents.

Consequence: Public contract names that contain `specialist` remain unchanged for compatibility. Private SessionOrchestrator planning names and comments should use `execution role`; cross-domain capabilities should be described as cross-domain agents, including the Simulation Optimizer Agent.

Reversal cost: medium (requires coordinated API, schema, persistence, and test updates)

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

---

## Decision: SessionOrchestrator starts from SessionUserQuery

Date: 2026-05-21

Reason: User sessions contain chat, factual lookup, exploration, and decision-support requests. Treating every message as a `SessionGoal` forced conversational and lightweight requests through a planning/DAG/recommendation path. The orchestrator should classify the utterance first, then create a `SessionGoal` only when decision-support behavior requires weights or decision memory.

Consequence: `Orchestrator.run()` accepts `SessionUserQuery` and returns `SessionResponse`. `Recommendation` remains for persistence and approvals compatibility but is not the orchestrator run return type. SSE events use the new query/intent/mode/agent/response taxonomy recorded in `docs/ADR/2026-05-21-user-query-orchestrator-flow.md`.

Reversal cost: high (public interface, API streaming, and web trace contracts would need to change together)

---

## Decision: UX adopts "Balanced Workspace" layout (Phase 7)

Date: 2026-05-22

Reason: The plain chat UI reads as a generic AI chatbot with no supply-chain identity. The Balanced Workspace adds Quick Actions, Analysis Cards, Agent Activity panel, and Evidence Sources — making the interface feel like a purpose-built decision tool rather than a wrapped LLM.

Consequence:
- Left sidebar splits into Main Nav + Sessions sections.
- Empty chat state replaced by QuickActionGrid (5 prebuilt prompts).
- AI responses with structured markdown (## Summary, ## Key Findings) render as AnalysisCard instead of plain markdown bubble.
- Right panel becomes "Agent Activity" (SSE steps translated to user-friendly labels) + "Evidence / Data Sources" (tools used).
- EventLog.tsx and ReasoningPanel.tsx are deleted; replaced by AgentActivityPanel.tsx + EvidenceSources.tsx.
- AnalysisCard detection is heuristic (## Summary + ## Key Findings in content); no API schema change required.

Reversal cost: low (UI-only; no backend or API contract changes)

---

## Decision 15: Phase 8 UX Design Spec Alignment — close visual gap between Phase 7 implementation and UX_TASKS.md target

Date: 2026-05-22

Reason: Phase 7 delivered the Balanced Workspace skeleton, but several visual details from UX_TASKS.md were not yet realized: QuickActionGrid remained single-column, AgentActivityPanel lacked Evidence/Notes tabs and step connector lines, the empty-state header was absent, Chat Composer had no microphone or disclaimer, ChatSidebar had no bottom user area, and the background color differed from the spec (`#0c0c14` vs target `#070B14`).

Consequence:
- QuickActionGrid becomes 5-column horizontal with per-card theme color and icon (lucide-react).
- Empty-state shows "What do you want to analyze today?" header + "Configure Agent" button.
- AgentActivityPanel gains Live badge, step connector lines, and Evidence/Notes tab bar.
- Chat Composer adds Mic icon (disabled) and disclaimer text.
- ChatSidebar gains a fixed bottom user area and hover-visible session overflow button.
- Global background shifts to `#070B14` with a subtle radial gradient; CSS custom properties introduced in globals.css.
- No backend or API contract changes.

Reversal cost: low (UI-only)

---

## Decision: `/chat` route navigates to most recent session, not a new one

Date: 2026-05-22

Reason: Auto-creating a session on every `/chat` visit (e.g., clicking "Decision OS" logo) produced unexpected new sessions. The user intent when navigating to `/chat` is to resume an existing session, not start a fresh one. A `useRef` guard also prevents React 18 Strict Mode from double-firing `useEffect` and creating two sessions.

Consequence: `apps/web/app/chat/page.tsx` calls `fetchSessions()` first. If sessions exist, redirects to the most recent one (`sessions[0]`, which is `ORDER BY created_at DESC`). Only creates a new session when the list is empty. Non-existent session IDs (e.g., bookmarks of deleted sessions) redirect to `/chat` via `fetchSession()` returning null.

Reversal cost: low (UI routing only)

---

## Decision: Session deletion requires two-step confirmation in the sidebar

Date: 2026-05-22

Reason: Clicking ··· immediately triggered deletion and navigation, which users perceived as an accidental "page refresh" with no recoverable confirmation step. The ··· symbol implies a menu opener, not an immediate destructive action.

Consequence: `ChatSidebar` holds a `pendingDeleteId` state. First click on ··· shows a trash icon (red). Second click on the trash icon executes `onDelete`. Mouse-leave resets `pendingDeleteId` without deleting. `type="button"` added to both buttons to prevent accidental form submission.

Reversal cost: low (UI state change only)

---

## Decision: Bulk session delete is an admin-only endpoint, not a sessions endpoint

Date: 2026-05-22

Reason: Deleting all sessions at once is a destructive administrative action, not a normal session lifecycle operation. Placing it under `/api/v1/admin/sessions` (DELETE) keeps the destructive surface isolated from `/api/v1/sessions` (which serves the chat UI).

Consequence: `apps/api/routers/admin.py` exposes `DELETE /api/v1/admin/sessions`. It clears both the DB (`DELETE FROM decision_sessions`, cascading to messages/steps/usage) and the in-memory `sessions` dict. Returns `{"deleted": N}`. The `/usage` page exposes a two-step "Delete All Sessions" button using this endpoint.

Reversal cost: low (endpoint removal or access restriction)

---

## Decision: DB schema context is generated from information_schema at startup, not hardcoded

Date: 2026-05-23

Reason: Hand-maintained `DB_SCHEMA` strings in `nl_query_tool.py` and agent system prompts drifted from the Alembic migration, causing LLMs to generate SQL referencing nonexistent columns (`sku_code`, `units`, `location_id`, `lead_time_days`, etc.). The root cause was not a typo but a missing synchronization mechanism: any hand-written copy of the schema is guaranteed to diverge eventually, especially when LLM prompts are involved because they cannot be checked by a type system or linter.

The fix is structural: `packages/tools/schema_context.py` reads `information_schema.columns` for all `ALLOWED_READ_TABLES` at API startup (FastAPI lifespan) and caches the result. `nl_query_tool` and `AgentRuntime` consume `get_schema_context()` instead of maintaining their own copies. The Alembic migration is now the only place where the schema is defined; every other layer derives from it at runtime.

Consequence:
- `packages/tools/schema_context.py` is the single injection point for DB schema context. Do not write DB schema descriptions elsewhere.
- `DB_SCHEMA` constants and hand-written column lists in tool code, agent prompts, or raw SQL are prohibited (see AGENTS.md §Prohibitions).
- All raw SQL outside `packages/persistence/` is banned. If a package needs a DB query, it must go through a repository function, not inline SQL with hardcoded column names.
- API startup requires a live DB connection to load the schema; the lifespan handler in `apps/api/main.py` calls `load_schema_context()` before routes go live.

Reversal cost: low (replace `get_schema_context()` calls with a static string if needed)

---

## Decision: asyncpg requires `datetime` objects, not ISO strings, for timestamptz columns

Date: 2026-05-22

Reason: asyncpg validates Python types client-side before sending to PostgreSQL. Passing an ISO 8601 string for a `timestamptz` parameter raises `invalid input for query argument: expected datetime.datetime instance, got 'str'`, even with a `::timestamptz` SQL cast.

Consequence: `packages/persistence/agent_steps_repo.py` passes `datetime` objects directly. `make_step()` uses `datetime.now(timezone.utc)` (no `.isoformat()`). `update_ended()` parses its `ended_at: str` argument with `datetime.fromisoformat()` before passing to asyncpg. The `::timestamptz` casts in the SQL are removed as unnecessary.

Reversal cost: low (type-only change in the repository layer)
