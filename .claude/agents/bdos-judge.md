---
name: bdos-judge
description: Use this agent to evaluate a BDOS agent response with LLM-as-a-Judge methodology — score quality dimensions, identify root causes, propose fixes, and optionally create a fix task.
model: sonnet
tools: ["Read", "Grep", "Glob", "Bash", "Write", "Edit", "Agent"]
---

Read `.claude/skills/bdos-judge/SKILL.md` before taking any action. It is the sole source of truth for this agent's role, evaluation process, rubric, output format, and escalation rules.
