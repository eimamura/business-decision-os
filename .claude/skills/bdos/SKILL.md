---
name: bdos
description: Use this skill when working on BDOS planning, implementation, infrastructure, testing, or review workflows. Entry point for all BDOS development tasks.
---

# BDOS Skill

## When to use

Use when the user asks to plan, implement, modify, test, review, or operate the Business Decision OS.

## Workflow

1. Read `CLAUDE.md` and `AGENTS.md` for project-wide rules.
2. Invoke `bdos-orchestrator` to decompose and route the task:
   - Human invocation: `/bdos-orchestrator`
   - Programmatic: `Agent(subagent_type="bdos-orchestrator", prompt="<task description>")`
3. The orchestrator reads `agents/orchestrator-planner/SPEC.md` and routes to:
   - `bdos-app-builder` → application code tasks
   - `bdos-infra` → infrastructure and CI/CD tasks
   - `bdos-test-review` → test authoring and phase verification
4. Each specialized agent reads its own `agents/<role>/SPEC.md` before acting.

## Source of truth

Detailed execution behavior lives in `agents/*/SPEC.md`.
Do not duplicate agent-specific behavior in this SKILL.md.
