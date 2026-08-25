# AGENTS

Canonical instruction file for AI coding agents working on this repository.

## Project Purpose

Build the **Business Decision OS** — an agent with a simulatable learning model. The LLM acts as control tower, not calculation engine. Domain: supply chain end-to-end optimization. See `docs/DESIGN.md` for architecture and design decisions.

## Terminology: Two Kinds of "Agent"

This repository uses the word "agent" in two distinct contexts. Do not confuse them.

| Term | What it means | Where defined |
|---|---|---|
| **Coding agent** (or **subagent**) | A Claude Code harness agent that **builds** this system. Runs during development only. Never ships in production. | This file (`AGENTS.md`) and `.claude/skills/bdos-*/SKILL.md` |
| **Product agent** | An AI agent that **is** the Business Decision OS system. Runs in production; processes user requests and calls tools. | `docs/DESIGN.md` §Agent Classification |

When this file says "agent" it means a coding agent.
When `docs/DESIGN.md` says "agent" it means a product agent.

See `docs/DESIGN.md` §Terminology for the full disambiguation.

---

## Coding Agent Architecture

This project uses a skill-centered Claude Code architecture. Your full execution contract is in your role's `.claude/skills/bdos-*/SKILL.md`.

| Subagent | SKILL | Model | Role |
|---|---|---|---|
| `bdos-orchestrator` | `.claude/skills/bdos-orchestrator/SKILL.md` | sonnet | Plan, decompose, route |
| `bdos-app-builder` | `.claude/skills/bdos-app-builder/SKILL.md` | sonnet | Implement app code |
| `bdos-infra` | `.claude/skills/bdos-infra/SKILL.md` | sonnet | Infrastructure, CI/CD |
| `bdos-test-review`      | `.claude/skills/bdos-test-review/SKILL.md`   | sonnet | Tests, code review              |
| `failure-analyst`       | `.claude/skills/analyze-failure/SKILL.md`    | sonnet | Post-defect root cause analysis |
| `prevention-architect`  | `.claude/skills/harden-system/SKILL.md`      | sonnet | Recurring pattern → prevention  |
| `bdos-judge`            | `.claude/skills/bdos-judge/SKILL.md`         | sonnet | LLM-as-a-Judge: response quality evaluation, root cause diagnosis, task creation |

**Invocation:**
- Skill (human): `/bdos-orchestrator plan <PhaseX>` or `/bdos-orchestrator run <PhaseX>` — plan a new phase (full context) or execute an already-planned phase (lean context).
- Subagent (agent-triggered): `Agent(subagent_type="bdos-orchestrator", prompt="...")` — spawns a separate instance; keeps main context clean and enables parallel specialist runs.
- Direct specialist: `Agent(subagent_type="bdos-app-builder", prompt="...")` etc.

## Required Reading (in order)

1. `docs/DESIGN.md` — architecture, components, data flow, public interfaces
2. `docs/TASKS.md` — implementation tasks with priorities and phases
3. `docs/DECISIONS.md` — lightweight daily decision log; why key decisions were made

Read these before any task. Do not start implementation without them in context.

## Design Records

Two tiers of decision documentation:

| File | Role | Weight | Examples |
|---|---|---|---|
| `docs/DECISIONS.md` | Lightweight daily decision log | Light | "UI is English-only", "Use Postgres" |
| `docs/adr/` | Formal records of important architectural decisions | Heavy | "Why Temporal instead of Celery" |

**Rule of thumb:**
- Write everything in `docs/DECISIONS.md` first — it is the inbox for in-flight judgments.
- Promote to `docs/adr/` when the decision is architectural, affects public interfaces, or requires future accountability ("Why did we do this?").
- `docs/DECISIONS.md` = working notes. `docs/adr/` = design case law.

## Prohibitions

The following are explicitly forbidden across all agents. Every item is one sentence; incident narratives live in `docs/failure-patterns.md` / `docs/ORCHESTRATOR.md`, never here.

### Code, Data & Interfaces

- Adding new top-level modules outside the layout in `docs/DESIGN.md` §Monorepo Layout.
- Changing public interface signatures (`LLMClient`, `Tool`, `JobRunner`, `MemoryStore`, `Orchestrator`, `Specialist`) without an ADR.
- Reading or referencing `data/sample/ground_truth/`.
- Committing any violation listed in `.claude/rules/security.md` (secrets, SQL injection, CORS widening, etc.).
- Hardcoding table column names or schemas as string literals in tool code, agent prompts, or raw SQL outside `packages/persistence/` — use `get_schema_context()` for LLM prompts and the repository layer for DB queries.
- Writing any hand-maintained schema description (`DB_SCHEMA` strings included) that duplicates what `information_schema` already provides.
- Sending raw inventory rows to LLM context.
- Mutating closed `approvals` rows.
- Bypassing `LLMClient` to call the LLM provider SDK directly.
- Shipping fail-silent fallbacks for external service clients — missing config must raise `RuntimeError` at the call site.

### Agent Role Boundaries

- Collapsing the Orchestrator + Specialist split into a single agent.
- Writing outside your role's canonical writable-target set (Orchestrator's forbidden-write set: `.claude/skills/bdos-orchestrator/SKILL.md` HARD STOP block) — violations are reverted and re-delegated.
- Shipping smart stubs that approximate real behavior instead of conforming to the schema contract.

### Quality Gates & Measurement

- Collapsing per-KPI scores into a single weighted total inside the Evaluator.
- Self-certifying phase completion — Test/Review verifies before any phase is marked Done.
- Fixing a gate/test failure meeting a `docs/ORCHESTRATOR.md §Defect Task Format` trigger without first registering a D-NNN Defect Task.
- Marking a D-NNN Defect Task `Resolved` without immediately invoking `/analyze-failure D-NNN`.
- Advancing to the next phase while any Defect Task in the current phase is `Open`.
- Signing off a quality gate as passed without captured command, exit code, and output-tail evidence in the Proof Output block. (← FP-003)
- Omitting a `make test-integration` gate row from any phase sign-off — omission invalidates the sign-off. (← FP-003)
- Using SUM token accumulators (e.g. `state["input_tokens"]`) for context-saturation checks or live verification — `peak_input_tokens` (per-call max) is authoritative, and any new SUM metric documents "sum-not-peak" at its definition site. (← FP-011)

### Git & Delivery

- Force-pushing to `main`, direct-pushing to `main`, or producing non-linear history.
- Using `--no-verify` or skipping commit hooks without explicit ADR justification.
- Using a plain HTTP stub for the web container; `compose web.build.context` must be the monorepo root.

## Commit Convention

Format: `<type>(<scope>): <description>`

Types: `feat` `fix` `refactor` `docs` `test` `chore` `perf` `ci`

Scopes — pick the one that matches the files changed:

| Scope | Changed paths |
|---|---|
| `agent` | `.claude/skills/bdos-*/SKILL.md`, agent config |
| `api` | `apps/api/` |
| `web` | `apps/web/` |
| `schemas` | `packages/schemas/` |
| `tools` | `packages/tools/` |
| `knowledge` | `packages/knowledge/` |
| `simulation` | `packages/simulation/` |
| `optimization` | `packages/optimization/` |
| `prediction` | `packages/prediction/` |
| `memory` | `packages/memory/` |
| `persistence` | `packages/persistence/` |
| `infra` | `docker-compose.yml`, `Makefile`, `.claude/`, `Dockerfile` |
| `data` | `data/`, seed scripts, migrations |
| `docs` | `docs/`, `AGENTS.md`, `CLAUDE.md` |
| `ci` | `.github/workflows/` |
| `deps` | `pyproject.toml`, `package.json`, lockfiles |

Agent commit boundary: `git add` + `git commit` only. Never `git push` or `gh pr create` — those are the human's responsibility.

## References

- Working rules (stubs, cost discipline, approvals, multi-agent constraints): `.claude/skills/bdos-*/SKILL.md`
- ADR triggers, authorship rules, TASKS.md write authority: `.claude/skills/bdos-orchestrator/SKILL.md`
- Test tiers, cassettes, CI: `.claude/rules/testing.md` (SSoT); operational How-to: `docs/TESTING.md`
- Failure pattern log and prevention lever policy: `docs/failure-patterns.md`, `docs/prevention-policy.md`
- Tool contracts and access control: `docs/TOOLS.md`
- Agent runtime graph and RAG design: `docs/RAG.md`
- Coding-orchestrator process formats (handoff, gate set, proof output, ADR triggers): `docs/ORCHESTRATOR.md`
- Product requirements and target-state agent catalog: `docs/SPEC.md`

## When in Doubt

- Read `docs/DESIGN.md` §Public Interfaces first.
- If a decision conflicts with current code, the code is the runtime truth; `docs/DECISIONS.md` and ADRs are the design truth. File an ADR before changing either.
- Ask the user before any irreversible action: destructive git operations, schema migrations that drop data, API contract changes, public repo settings.

## Language Convention

All code, documentation, and user-visible product surfaces use English only.
Coding agent chat messages and narrative responses should match the user's language; when the user writes in Japanese, respond in Japanese.

| Surface | Language |
|---|---|
| Source code, identifiers, comments | English |
| Commit messages, PR titles and bodies | English |
| `docs/` (all files including ADRs, DESIGN.md, TASKS.md, etc.) | English |
| `SKILL.md`, `AGENTS.md`, `CLAUDE.md` | English |
| All user-visible UI strings | English |
| Chat messages and agent narrative responses | Match the user's language; Japanese when the user writes in Japanese, otherwise English |
| Log messages, error messages, metric labels | English |
| Test names and assertion messages | English |

**Exception:** Coding agent chat and narrative responses may use Japanese only when responding to Japanese user messages.

This convention is enforced at code review. PRs containing non-English identifiers, log messages, documentation, or UI strings will be returned for correction.
