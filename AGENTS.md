# AGENTS

Canonical instruction file for AI coding agents working on this repository.

## Project Purpose

Build the **Business Decision OS** — an agent with a simulatable learning model. The LLM acts as control tower, not calculation engine. Domain: supply chain end-to-end optimization. See `docs/PRODUCT_SPEC.md` for the full goal and `docs/DESIGN.md` for architecture.

## Terminology: Two Kinds of "Agent"

This repository uses the word "agent" in two distinct contexts. Do not confuse them.

| Term | What it means | Where defined |
|---|---|---|
| **Coding agent** (or **subagent**) | A Claude Code harness agent that **builds** this system. Runs during development only. Never ships in production. | This file (`AGENTS.md`) and `agents/*/SPEC.md` |
| **Product agent** | An AI agent that **is** the Business Decision OS system. Runs in production; processes user requests and calls tools. | `docs/DESIGN.md` §Agent Classification |

When this file says "agent" it means a coding agent.
When `docs/DESIGN.md` says "agent" it means a product agent.

See `docs/DESIGN.md` §Terminology for the full disambiguation.

---

## Coding Agent Architecture

This project uses a SPEC-centered Claude Code architecture. Your full execution contract is in your role's `agents/*/SPEC.md`.

| Subagent | SPEC | Model | Role |
|---|---|---|---|
| `bdos-orchestrator` | `agents/orchestrator/SPEC.md` | sonnet | Plan, decompose, route |
| `bdos-app-builder` | `agents/app-builder/SPEC.md` | sonnet | Implement app code |
| `bdos-infra` | `agents/infra/SPEC.md` | sonnet | Infrastructure, CI/CD |
| `bdos-test-review` | `agents/test-review/SPEC.md` | sonnet | Tests, code review |

**Invocation:**
- Skill (human): `/bdos-orchestrator` — runs in the current Claude context; use for planning sessions and ADR reviews.
- Subagent (agent-triggered): `Agent(subagent_type="bdos-orchestrator", prompt="...")` — spawns a separate instance; keeps main context clean and enables parallel specialist runs.
- Direct specialist: `Agent(subagent_type="bdos-app-builder", prompt="...")` etc.

## Required Reading (in order)

1. `docs/PRODUCT_SPEC.md` — what to build and why
2. `docs/DESIGN.md` — architecture, components, data flow, public interfaces
3. `docs/TASKS.md` — implementation tasks with priorities and phases
4. `docs/DECISIONS.md` — lightweight daily decision log; why key decisions were made

Read these before any task. Do not start implementation without them in context.

## Design Records

Two tiers of decision documentation:

| File | Role | Weight | Examples |
|---|---|---|---|
| `docs/DECISIONS.md` | Lightweight daily decision log | Light | "UI is English-only", "Use Postgres" |
| `docs/ADR/` | Formal records of important architectural decisions | Heavy | "Why Temporal instead of Celery" |

**Rule of thumb:**
- Write everything in `docs/DECISIONS.md` first — it is the inbox for in-flight judgments.
- Promote to `docs/ADR/` when the decision is architectural, affects public interfaces, or requires future accountability ("Why did we do this?").
- `docs/DECISIONS.md` = working notes. `docs/ADR/` = design case law.

## Prohibitions

The following are explicitly forbidden across all agents:

- Adding new top-level modules outside the layout in `docs/DESIGN.md` §Monorepo Layout.
- Changing public interface signatures (`LLMClient`, `Tool`, `JobRunner`, `MemoryStore`, `Orchestrator`, `Specialist`) without an ADR.
- Reading or referencing `data/sample/ground_truth/`.
- Hardcoded secrets in source code or committed `.env` files.
- Sending raw inventory rows to LLM context.
- Mutating closed `approvals` rows.
- Bypassing `LLMClient` to call the LLM provider SDK directly.
- Single-agent simplifications of the Orchestrator + Specialist split.
- Collapsing per-KPI scores into a single weighted total inside the Evaluator.
- Smart stubs that approximate real behavior instead of conforming to the schema contract.
- Fail-silent fallbacks for external service clients: missing config (API keys, packages) MUST raise `RuntimeError` at the call site, not silently degrade to a stub or no-op.
- Force-pushing to `main`; direct pushes to `main`; non-linear history.
- Using `--no-verify` or skipping commit hooks without explicit ADR justification.
- Using a plain HTTP stub for the web container; `compose web.build.context` must be the monorepo root.

## Commit Convention

Format: `<type>(<scope>): <description>`

Types: `feat` `fix` `refactor` `docs` `test` `chore` `perf` `ci`

Scopes — pick the one that matches the files changed:

| Scope | Changed paths |
|---|---|
| `agent` | `agents/*/SPEC.md`, agent config |
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

- Working rules (stubs, cost discipline, approvals, multi-agent constraints): `agents/*/SPEC.md`
- ADR triggers, authorship rules, TASKS.md write authority: `agents/orchestrator/SPEC.md`
- Local dev, Makefile, DATABASE_URL: `docs/DEVELOPMENT.md`
- Test tiers, cassettes, CI: `docs/TESTING.md`

## When in Doubt

- Read `docs/DESIGN.md` §Public Interfaces and §Phase Progression first.
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
| `SPEC.md`, `AGENTS.md`, `CLAUDE.md` | English |
| All user-visible UI strings | English |
| Chat messages and agent narrative responses | Match the user's language; Japanese when the user writes in Japanese, otherwise English |
| Log messages, error messages, metric labels | English |
| Test names and assertion messages | English |

**Exception:** Existing Japanese reference documents (`docs/business_decision_os_spec.md`, `docs/domain.md`) are preserved as-is. English official docs supersede them on conflict. Coding agent chat and narrative responses may use Japanese only when responding to Japanese user messages.

This convention is enforced at code review. PRs containing non-English identifiers, log messages, documentation, or UI strings will be returned for correction.
