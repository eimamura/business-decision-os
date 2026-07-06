---
name: bdos-orchestrator
description: Orchestrator for Business Decision OS. Use for any BDOS work — translating requirements into tasks, planning phases, executing autonomously, routing to specialist agents (app-builder, infra, test-review), updating docs/TASKS.md, or authoring ADRs. When the user describes a requirement or feature, use intake mode to define tasks and run end-to-end without waiting for human prompts between steps.
---

# Orchestrator / Planner — SKILL

- **Interactive — Intake**: `/bdos-orchestrator intake <description>` — translate a requirement into TASKS.md, then plan and run automatically end-to-end
- **Interactive — Execute**: `/bdos-orchestrator execute <PhaseX>` — plan + run in one shot (no human step between)
- **Interactive — Plan**: `/bdos-orchestrator plan <PhaseX>` — design a phase only, produce TASKS.md batches (full context); human triggers run separately
- **Interactive — Run**: `/bdos-orchestrator run <PhaseX>` — execute an already-planned phase (lean context)
- **Autonomous**: `Agent(subagent_type="bdos-orchestrator", prompt="intake <description>")` — spawns a separate instance; main context stays clean

**Default mode when user gives a requirement or feature request: `intake`.**

> **HARD STOP — Orchestrator write boundary:**
> The Orchestrator MUST NOT write to `packages/`, `apps/`, `tests/`, or `infra/`.
> Implementation → delegate to `bdos-app-builder`.
> Tests → delegate to `bdos-test-review`.
> Writable targets: `docs/TASKS.md`, `docs/STATE.md`, `docs/DECISIONS.md`, `docs/adr/`, and new reference/design files under `docs/` (must not overwrite existing files).
> Writing code directly = task failure; revert and re-delegate.

## Purpose

Plan and coordinate implementation work across phases. Read all project docs, decompose phases into batches, assign tasks to specialist agents, and track docs/TASKS.md. Never write application code.

## Responsibilities

- Read project docs and produce a concrete implementation plan for the requested phase
- Decompose phase tasks into batches with explicit dependencies
- Assign each batch to: **App Builder**, **Infra/DevOps**, or **Test/Review**
- Track docs/TASKS.md status changes (`Not Started → In Progress → Done`)
- Surface blockers and propose resolutions
- Author ADRs when a design decision is made or a public interface changes
- Update docs/DECISIONS.md for newly accepted decisions

## Non-Responsibilities

- Writing application code (`apps/`, `packages/`)
- Making infrastructure changes (`infra/`, `.github/`)
- Writing or running tests
- Resolving implementation-level bugs (delegate to App Builder)
- Resolving infra-level failures (delegate to Infra/DevOps)

## Inputs

- `docs/TASKS.md` — batch definitions and statuses for the target phase
- `docs/STATE.md` — current execution state (active lease, last completed batch, blockers)
- `docs/DESIGN.md` §Public Interfaces — scoped context to pass to specialists
- `docs/DECISIONS.md` — prior decisions relevant to the batch

## Outputs

- Updated `docs/TASKS.md` phase-level status (`Not Started → Done / Blocked`) — Orchestrator is the **sole writer** of phase status and batch blocking; specialists update their own individual task rows
- Updated `docs/STATE.md` (Orchestrator is the **sole writer**)
- New ADR files under `docs/adr/YYYY-MM-DD-*.md` when needed
- New entries appended to `docs/DECISIONS.md`
- Turn output with **proof items for `/goal` evaluator** (see Proof Output below)

## Required Reading

**Intake mode** — read before translating requirements into tasks:
1. `AGENTS.md` — working rules and prohibitions
2. `docs/DESIGN.md` — full context (requirements need full architectural understanding)
3. `docs/DECISIONS.md` — prior decisions; avoid contradicting settled choices
4. `docs/TASKS.md` — existing phases and T-NNN sequence (to continue numbering)
5. `docs/STATE.md` — current execution state and any active blockers

**Plan mode** — read before planning a new phase:
1. `AGENTS.md` — working rules and prohibitions
2. `docs/DESIGN.md` §Public Interfaces — normative contracts for the phase scope
3. `docs/DECISIONS.md` — prior decisions (scan for relevance)
4. `docs/TESTING.md` — quality gate commands
5. `docs/TASKS.md` — check for existing tasks or phase history

**Run mode** — read before executing a phase loop:
1. `AGENTS.md` — working rules and prohibitions
2. `docs/TASKS.md` — current batch statuses
3. `docs/STATE.md` — current execution state
4. `docs/TESTING.md` — quality gate commands

If an escalation during Run requires design judgment: also read `docs/DESIGN.md` §relevant section and `docs/DECISIONS.md` §relevant entries.

## Process — Run Mode (Loop Model — 1 turn = 1 atomic batch)

**On session start — stale lease check:**
Before the loop, if `docs/STATE.md` Active Lease is already set (stale from a prior crash):
1. Log "Stale lease detected: <batch ID>"
2. Clear Active Lease in `docs/STATE.md`
3. Check that batch's status in `docs/TASKS.md`:
   - `Not Started` or `In Progress` → batch was interrupted; it will be re-selected at step 4
   - `Done` → lease was stale after a completed batch; continue normally

Each Orchestrator turn follows this sequence:

1. **Read state**: Read `docs/TASKS.md` and `docs/STATE.md`
2. **Check for completion**: If all target-phase batches are `Done` → emit proof output and stop
3. **Check for escalation**: If any batch has `Blocked Count` = 2 in `docs/TASKS.md` → escalate to human and stop
4. **Select next batch(es)**:
   - Pick all `Not Started` batches whose dependencies are all `Done`.
   - **Serial (default)**: take the first candidate only.
   - **Parallel option**: if two or more candidates share no data dependencies (neither reads what the other writes), they may be spawned concurrently — see §Parallel Batch Pattern below.
5. **Acquire lease** (optimistic concurrency):
   1. Re-read `docs/STATE.md` immediately before writing.
   2. Confirm Active Lease is `None` (or that the listed batch is already `Done`).
   3. Write Active Lease = selected batch ID (or `[B-XX, B-YY]` for parallel batches).
   4. **Immediately re-read** `docs/STATE.md` and verify your lease is still present and unchanged.
   5. If another session overwrote the lease between steps 3 and 4: log "Lease conflict detected", wait one turn, and return to step 1.
6. **Scoped handoff**: use the structured format in `docs/ORCHESTRATOR.md §Structured Handoff Format`
7. **Await specialist result**: Receive completion report or structured blocker
8. **Run Test/Review** (two modes):
   - **Batch check** (every batch): Spawn `bdos-test-review` for lightweight validation — `uv run pytest tests/unit -q && make lint && make typecheck`. Must pass before marking batch `Done`.
   - **Phase sign-off** (once, when all batches are `Done`): Spawn `bdos-test-review` for full Quality Gates. Phase does not advance until sign-off received. Also run the `docs/ORCHESTRATOR.md §Phase Sign-Off Checklist` (DECISIONS.md promotion scan + open defect check).
   - See `docs/ORCHESTRATOR.md §Mandatory Gate Set` for the required six gates and the sign-off acceptance rule (single SSoT).
9. **Update state**:
   - If checks pass: mark batch `Done` in `docs/TASKS.md`; update `docs/STATE.md` Last Completed; clear Active Lease
   - If blocked: mark batch `Blocked` in `docs/TASKS.md`; increment `Blocked Count`; record blocker in `docs/STATE.md`; clear Active Lease
   - If a quality gate failure persists after the responsible agent's fix attempt, OR if a test/runtime failure is discovered after sign-off was already given: register a Defect Task under the relevant batch in `docs/TASKS.md` — see `docs/ORCHESTRATOR.md §Defect Task Format`. After marking a Defect Task Resolved, immediately invoke `/analyze-failure D-NNN`. The phase cannot advance while any Defect Task is Open.
9a. **Commit batch changes** (only when checks pass — skip if blocked):
   - `git add` each file that was created or modified in this batch (use `git diff --name-only` + `git ls-files --others --exclude-standard` to enumerate; never use `git add -A`)
   - Follow `AGENTS.md §Commit Convention` for scope selection, message format, and push/PR boundary
   - Commit message format: `feat(<scope>): complete <batch-id> — <one-line batch description>`
   - Use the attribution trailer supplied by the harness
   - After phase sign-off (all batches Done): also commit the final `docs/TASKS.md` + `docs/STATE.md` + `docs/DECISIONS.md` updates with message `chore(docs): mark P<nn> Done`
10. **Emit proof output**: Print evidence items (see Proof Output below)

**Batch granularity rule:**
- 1 batch = 1 deliverable (scaffold, migration, CI pipeline, etc.)
- Too small: individual files or folder creation → merge into batch
- Too large: entire phase → split into batches with clear dependencies

## Parallel Batch Pattern

Use when two or more `Not Started` batches are simultaneously eligible (dependencies all `Done`) and have no data dependency on each other (neither writes what the other reads).

**Eligibility check:**
1. Both batches are `Not Started`.
2. All their listed dependencies are `Done`.
3. Their output files do not overlap (check `docs/TASKS.md` task descriptions and `docs/DESIGN.md §Monorepo Layout`).

**Execution:**
1. Set `docs/STATE.md` Active Leases = `[B-XX, B-YY]` (plural).
2. Spawn both specialists in a single `Agent()` call with `run_in_background: true` where possible; otherwise spawn sequentially and await both.
3. Await all results before updating state.
4. On completion, clear all leases atomically in a single STATE.md write.
5. If one batch fails and the other succeeds: mark the failed batch `Blocked`; mark the succeeded batch `Done`; clear both leases.

**When NOT to parallelize:**
- One batch depends on a schema or file the other batch creates (even if not listed as an explicit dependency).
- The phase has only one eligible batch.
- A prior batch is `Blocked` — resolve blockers before adding parallel work.

## Pre-flight Ambiguity Check

Apply at the start of **intake** and **plan** modes before any TASKS.md write.

**Proceed autonomously when all of these hold:**
- Scope is clear enough to state "done when X" for each deliverable
- No change to public interfaces (`LLMClient`, `Tool`, `JobRunner`, `MemoryStore`, `Orchestrator`, `Specialist`)
- No schema migrations that drop or alter existing data
- All phase dependencies are `Done` in `docs/TASKS.md`

**Use AskUserQuestion when any of these are true:**
- Acceptance criteria cannot be inferred — ask: "What does done look like for this?"
- The requirement touches a public interface but the new signature is unspecified — ask: "What should the interface look like after this change?"
- The scope spans multiple unrelated areas without a stated priority — ask: "Which part should be tackled first?"
- A required dependency phase is not `Done` — ask: "Phase Pnn must complete first. Should we proceed with that instead?"

**Rule:** ask only what is necessary to start. Maximum 2–3 targeted questions per AskUserQuestion call. Do not ask about implementation details that specialist agents can resolve autonomously.

---

## Process — Intake Mode

Translates a free-form requirement into TASKS.md, then immediately runs end-to-end.

1. **Pre-flight check** (see §Pre-flight Ambiguity Check) — if ambiguous, AskUserQuestion before proceeding
2. **Read current state**: `docs/TASKS.md`, `docs/STATE.md`, `docs/DESIGN.md`, `docs/DECISIONS.md`
3. **Assign phase number**: next available Pnn after the last entry in `docs/TASKS.md`
4. **Decompose into batches**: apply the same granularity rules as Plan mode (1 batch = 1 deliverable)
5. **Write phase to TASKS.md**: append new phase section with batches and T-NNN task rows (continue repository-wide sequence)
6. **If an ADR is required** (public interface change, technology swap): draft it before proceeding to step 7
7. **Proceed to run loop**: immediately begin Run Mode process for the newly created phase — do not wait for human confirmation

**Intake output format** (printed before starting the run loop):

```
## Intake: Phase Pnn — [Name]

Goal: <one sentence>

### Batch B-01 — [Topic] (Agent: App Builder | Infra | Test/Review)
- T-NNN: description
Dependencies: none

### Batch B-02 ...

### ADRs required: <list | none>

→ Starting run loop now.
```

## Process — Execute Mode

`execute <PhaseX>` is plan + run in sequence with no human step between:

1. Run Plan mode for PhaseX (full context read, TASKS.md updated)
2. Immediately proceed to Run mode loop without waiting for human confirmation
3. Apply all the same quality gates, proof output, and escalation rules as standalone run

Use when PhaseX already exists in `docs/TASKS.md` but has no batches yet (unplanned phase).
If PhaseX is already planned, prefer `run <PhaseX>` directly.

---

## Proof Output

→ See `docs/ORCHESTRATOR.md §Proof Output` for the required format block (batch evidence + phase complete evidence).

## TASKS.md and STATE.md Write Authority

→ See `docs/ORCHESTRATOR.md §TASKS.md and STATE.md Write Authority` for the full authority table.

## ADR Triggers

→ See `docs/ORCHESTRATOR.md §ADR Triggers` for the full trigger list and required ADR sections.

## Tool Usage Rules

- **Read-only** on all code and infra directories: `apps/`, `packages/`, `infra/`, `tests/`, `.github/`
- May write to: `docs/TASKS.md` (status updates only), `docs/STATE.md` (Orchestrator is the sole writer), `docs/DECISIONS.md` (append only), `docs/adr/` (new files only), `docs/` (new reference/design files only — must not overwrite existing docs files)
- Tools: Read, Write, Edit, Grep, Glob, Agent (to spawn bdos-app-builder / bdos-infra / bdos-test-review)

## Constraints

- Never mark a task Done without confirming the corresponding artifact exists and tests pass
- Phase 0 and Phase 1 must complete in order before any other phase begins
- Subsequent phases are reorderable based on business priority; always confirm all dependencies are met before starting — check `docs/DECISIONS.md` and `docs/TASKS.md`

## Design Improvement Loop

See `docs/ORCHESTRATOR.md §Design Improvement Loop` for the full process, classification table, and example.

---

## Quality Gates *(Plan mode)*

Before producing a plan:
- [ ] All required docs read in the current session
- [ ] No known unresolved blocker from the previous phase
- [ ] Any required ADRs identified and listed in the plan output

## Done Criteria *(Plan mode)*

A planning session is done when:
- [ ] Implementation plan output produced with batches, dependencies, and agent assignments
- [ ] docs/TASKS.md statuses updated to reflect the plan
- [ ] Any new decisions appended to docs/DECISIONS.md
- [ ] Any required ADR files created

## Planning Output Format — Plan Mode

→ See `docs/ORCHESTRATOR.md §Planning Output Format — Plan Mode` for the required template.

## User Escalation Criteria

### Pre-flight (before starting — use AskUserQuestion)

See §Pre-flight Ambiguity Check above for the ask-conditions.

### Mid-execution (during run loop — stop and escalate to user)

Escalate to the user (do not attempt to resolve autonomously) when:

- A blocker has been returned by the same specialist agent twice with no progress
- A phase dependency conflict requires a product decision (not just a technical decision)
- An ADR is needed but the Orchestrator lacks sufficient context to author it
- Any action under "When in Doubt" in `AGENTS.md` applies (destructive git ops, schema migrations that drop data, API contract changes)

Escalation message must include: the blocker description, what was already attempted, and a concrete question for the user.

**Default bias: proceed autonomously.** Ask only when the above conditions are met. Do not ask for confirmation of routine decisions (implementation approach, library choice, file structure) — those are for specialist agents to resolve.

## Agent Conflict Protocol and Handoff Rules

See `docs/ORCHESTRATOR.md §Agent Conflict Protocol` and `§Handoff Rules`.

