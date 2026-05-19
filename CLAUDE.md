# Claude Code Instructions

Read `AGENTS.md` before any task. It is the canonical instruction file for all working rules, prohibitions, conventions, and checklists.

---

## Agent Architecture

This project uses a SPEC-centered Claude Code architecture.

- `agents/*/SPEC.md` is the **sole source of truth** for agent-specific behavior.
- `.claude/skills/bdos-*/SKILL.md` defines workflow entrypoints.
- `.claude/agents/bdos-*.md` defines subagent metadata and delegates to SPEC.md.
- Do not duplicate detailed agent behavior in CLAUDE.md, SKILL.md, or subagent files.

| Subagent | SPEC | Role |
|---|---|---|
| `bdos-orchestrator` | `agents/orchestrator-planner/SPEC.md` | Plan, decompose, route |
| `bdos-app-builder` | `agents/app-builder/SPEC.md` | Implement app code |
| `bdos-infra` | `agents/infra-devops/SPEC.md` | Infrastructure, CI/CD |
| `bdos-test-review` | `agents/test-review/SPEC.md` | Tests, code review |
