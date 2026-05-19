---
name: bdos
description: Use this skill when working on BDOS planning, implementation, infrastructure, testing, or review workflows. Entry point for all BDOS development tasks.
---

# BDOS Skill

## When to use

Use when the user asks to plan, implement, modify, test, review, or operate the Business Decision OS.

## Workflow

1. Read `CLAUDE.md` for project-wide rules.
2. Use the `bdos-orchestrator` subagent for task decomposition and routing.
3. The orchestrator reads `agents/orchestrator-planner/SPEC.md` before acting.
4. The orchestrator selects the appropriate specialized subagent:
   - `bdos-app-builder` → `agents/app-builder/SPEC.md`
   - `bdos-infra` → `agents/infra-devops/SPEC.md`
   - `bdos-test-review` → `agents/test-review/SPEC.md`
5. Each specialized subagent reads its own SPEC.md before taking any action.

## Source of truth

Detailed execution behavior lives in `agents/*/SPEC.md`.
Do not duplicate agent-specific behavior in this SKILL.md.
