---
name: bdos-orchestrator
description: Orchestrator for Business Decision OS. Use for any BDOS work — planning phases, decomposing tasks, routing to specialist agents (app-builder, infra, test-review), updating docs/TASKS.md, or authoring ADRs. Can run interactively in the current context or be spawned as a subagent via Agent(subagent_type="bdos-orchestrator").
---

## When to use

Use for any BDOS development task: planning a phase, decomposing work, routing to specialist agents, updating docs/TASKS.md, or drafting ADRs.

- **Interactive (in-context)**: invoke `/bdos-orchestrator` — the current Claude instance acts as orchestrator
- **Autonomous (subagent)**: `Agent(subagent_type="bdos-orchestrator", prompt="...")` — spawns a separate Opus instance; main context stays clean

## Workflow

1. Read `CLAUDE.md` and `AGENTS.md` for project-wide rules and prohibitions.
2. Read `agents/orchestrator/SPEC.md` — sole source of truth for this role's process, constraints, and deliverables.
3. Decompose the task and route to specialist agents as needed:
   - `bdos-app-builder` → application code tasks
   - `bdos-infra` → infrastructure and CI/CD tasks
   - `bdos-test-review` → test authoring and phase verification
