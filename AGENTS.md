# AGENTS

Canonical instruction file for AI coding agents working on this repository.

## Project Purpose

Build the **Business Decision OS** — an agent with a simulatable learning model. The LLM acts as control tower, not calculation engine. Domain: supply chain end-to-end optimization. See `SPEC.md` for the full goal and `DESIGN.md` for architecture.

## Agent Architecture

This project uses a SPEC-centered Claude Code architecture. If you are running as a subagent, your full execution contract is in your role's SPEC.md.

| Subagent | SPEC | Role |
|---|---|---|
| `bdos-orchestrator` | `agents/orchestrator-planner/SPEC.md` | Plan, decompose, route |
| `bdos-app-builder` | `agents/app-builder/SPEC.md` | Implement app code |
| `bdos-infra` | `agents/infra-devops/SPEC.md` | Infrastructure, CI/CD |
| `bdos-test-review` | `agents/test-review/SPEC.md` | Tests, code review |

Invocation:
- Human slash command: `/bdos-orchestrator`, `/bdos-app-builder`, etc.
- Programmatic subagent: `Agent(subagent_type="bdos-app-builder", prompt="...")`

## Required Reading (in order)

1. `SPEC.md` — what to build and why
2. `DESIGN.md` — architecture, components, data flow, public interfaces
3. `TASKS.md` — implementation tasks with priorities and phases
4. `DECISIONS.md` — why key decisions were made

Read these before any task. Do not start implementation without them in context.

## Working Rules

### Final-Form-First

- All 10 architectural components and their interfaces exist Day 1.
- Phases fill in implementations behind stable interfaces — they **never add new modules**.
- Authentication is the only documented exception to this rule (bolt-on permitted later).
- Public interface signatures listed in `DESIGN.md` §Public Interfaces are normative. **Any change requires an ADR** under `docs/adr/YYYY-MM-DD-title.md`.

### Stubs

- Stubs must be **intentionally trivial** and schema-conformant.
- Tests assert schema conformance, not numerical accuracy.
- Smart stubs hide schema mismatches — they are forbidden.

### Multi-Agent Architecture

- Orchestrator + 4 Specialists (Domain Expert, Data Engineer, Simulator/Optimizer, Evaluator) from Day 1.
- Single-agent simplifications are forbidden — the Specialist split is a load-bearing architectural commitment.
- Phase 1 uses `PromptBasedSpecialist` (shared `LLMClient` + role prompts). Phase 9 swaps to `AgentBasedSpecialist`. The interface is unchanged across phases.

### Cost & Audit Discipline

- Every LLM call must record `llm_usage` from inside `LLMClient` middleware. Call-site logging is forbidden.
- Every tool invocation must write one `tool_calls` row + one `audit_log` row in the same transaction.
- `audit_log` is the single tamper-evident chain. `tool_calls.audit_hash` is a denormalized pointer; never a second chain.
- No raw row data to LLM. Summaries / aggregates only. The LLM context sanitizer enforces this.

### Trade-off Resolution

- Specialists never resolve cross-KPI trade-offs unilaterally.
- Optimizer returns ≥ 3 Pareto-feasible candidates (never single-best).
- Evaluator produces per-KPI scores (never a collapsed weighted total).
- Orchestrator owns weight application and primary + alternative selection.
- Recommendation always includes primary + ≥ 2 alternatives at different trade-off positions.

### Approvals

- Approval state machine: `pending → approved | rejected | needs_revision | expired`. Terminal states are immutable.
- Revisions **never mutate closed rows**. Create a new `approvals` row with `parent_approval_id` set.

### Sample Data

- `data/sample/ground_truth/` is **agent-forbidden**. Never read these files, never load them into the database, never reference them in tool calls.
- SQL Tool allowlist: `sku_master`, `inventory`, `demand_history`, `supply`, `cost`, `customers`. No other tables are queryable.
- Ground-truth tables only exist as CSV under `ground_truth/` and are used by the evaluation harness outside the agent boundary.

### Language Policy

- **English** for code, comments, identifiers, log messages, commit messages, PR titles & bodies, and all official documentation (`SPEC.md`, `DESIGN.md`, `TASKS.md`, `DECISIONS.md`, `AGENTS.md`, `docs/adr/*.md`).
- **English** for all user-visible strings: UI chrome (navigation, titles, buttons, placeholders, `aria-label`s, empty states, Reasoning Panel labels), chat message bodies, agent-generated narrative shown in the UI (e.g. orchestrator `rationale`), and terminal dialogue output presented to the user.

### Currency

- USD throughout the system (data, KPI, UI, recommendations). No JPY, no other currencies.

## Prohibitions

The following are explicitly forbidden:

- Adding new top-level modules outside the layout in `DESIGN.md` §Monorepo Layout.
- Changing public interface signatures (`LLMClient`, `Tool`, `JobRunner`, `MemoryStore`, `Orchestrator`, `Specialist`) without an ADR.
- Reading or referencing `data/sample/ground_truth/`.
- Hardcoded secrets in source code or committed `.env` files.
- Sending raw inventory rows to LLM context.
- Mutating closed `approvals` rows.
- Bypassing `LLMClient` to call the LLM provider SDK directly.
- Single-agent simplifications of the Orchestrator + Specialist split.
- Collapsing per-KPI scores into a single weighted total inside the Evaluator.
- Smart stubs that approximate real behavior instead of conforming to the schema contract.
- Force-pushing to `main`; direct pushes to `main`; non-linear history.
- Using `--no-verify` or skipping commit hooks without explicit ADR justification.
- Using a plain HTTP stub server for the web container instead of a real Next.js standalone build; Compose `web.build.context` must be the monorepo root, not `apps/web` only.

## ADR Update Rules

Author an ADR under `docs/adr/YYYY-MM-DD-title.md` whenever you:

- Change a public interface signature.
- Add or replace a technology choice (LLM provider, framework, DB, etc.).
- Change risk thresholds, KPI weight defaults, or schema CHECK constraints.
- Update `llm_pricing` seed values.
- Modify the SQL Tool allowlist.

Each ADR must include: background, candidates considered, decision, rationale, tradeoffs, reversibility / re-evaluation triggers.

## Pre-Change Checklist

Before opening a PR:

- [ ] `SPEC.md` and `DESIGN.md` consulted; change aligns with both.
- [ ] No new top-level module added.
- [ ] Public interfaces unchanged, or an ADR drafted.
- [ ] `TASKS.md` updated: task marked `In Progress` → `Done`.
- [ ] `DECISIONS.md` updated for any new accepted decision.
- [ ] Tests added or updated; schema conformance asserted for stubs.
- [ ] No raw rows in any new LLM prompt path.
- [ ] No ground-truth path referenced.
- [ ] Conventional Commit message with valid scope (see Commit Discipline).

## Local Development

See [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md) for stack setup, Makefile targets, `DATABASE_URL` conventions, and common failures.

## Test Execution

See [`docs/TESTING.md`](docs/TESTING.md) for tiers, tooling, cassette discipline, and CI behavior.

- Unit + integration: `uv run pytest`
- E2E: `npx playwright test` against the local stack
- `temperature=0` everywhere. Any non-determinism in a test is a bug.

## Commit Discipline

- Conventional Commits format: `<type>(<scope>): <description>`.
- Allowed types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `perf`, `ci`.
- Allowed scopes: `agent`, `api`, `web`, `schemas`, `tools`, `domain`, `simulation`, `optimization`, `prediction`, `memory`, `state`, `infra`, `data`, `docs`, `ci`, `deps`.
- One logical change per commit. Squash noisy WIP commits before review.
- Never amend or force-push to `main`. Create a new commit for fixes.

## When in Doubt

- Read `DESIGN.md` §Public Interfaces and §Phase Progression first.
- If a decision conflicts with current code, the code is the runtime truth, but `DECISIONS.md` and ADRs are the design truth. File an ADR before changing either.
- Ask the user before any irreversible action: destructive git operations, schema migrations that drop data, API contract changes, public repo settings.
