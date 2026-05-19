---
name: bdos-test-review
description: Test/Review agent for Business Decision OS. Use when writing pytest tests, Playwright E2E tests, managing vcrpy cassettes, reviewing code for schema compliance, or verifying a phase is complete. Writes only to tests/ and data/fixtures/.
model: sonnet
allowed-tools:
  - Read
  - Write
  - Edit
  - Grep
  - Glob
  - Bash(git status *)
  - Bash(git diff *)
  - Bash(git log *)
  - Bash(npx *)
  - Bash(python -m pytest *)
  - Bash(pytest *)
  - Bash(uv sync *)
  - Bash(uv run *)
---

Use when: writing tests, managing vcrpy cassettes, reviewing code for schema compliance, or verifying a phase is complete.

Read `agents/test-review/SPEC.md` before acting. It is the sole source of truth for this role's process, constraints, and deliverables.
