# Agent Harness Playbook

How to drive the Business Decision OS agent harness from documented requirements to working source code.

---

## 1. Prerequisites

The following artifacts must exist and be committed before the harness can run:

| Artifact | Location | Purpose |
|---|---|---|
| Product spec | `docs/PRODUCT_SPEC.md` | What to build and why |
| Architecture | `docs/DESIGN.md` | Components, public interfaces, monorepo layout, phase progression |
| Task registry | `docs/TASKS.md` | Batches with dependencies and statuses |
| Execution state | `docs/STATE.md` | Runtime state: active lease, last completed batch, blockers |
| Decision log | `docs/DECISIONS.md` + `docs/adr/` | Why key choices were made |
| Agent metadata | `.claude/agents/*.md` | Model selection and tool allowlists per agent |
| Agent contracts | `agents/*/SPEC.md` | Each agent's responsibilities, non-responsibilities, and constraints |

Do not start the harness without all of the above in place.

---

## 2. Entry Point

### Option A — Autonomous (recommended)

```
/goal Phase 0 is complete. Claude must show in this conversation:
1. grep output proving all Phase 0 batches (B01–B05) contain "Done"
2. make build exit code 0
3. git diff --stat showing committed artifacts
4. no line in docs/TASKS.md or docs/STATE.md showing Blocked or In Progress
Stop after 30 turns if not complete.
```

The `/goal` evaluator (Haiku) checks the conversation transcript after each turn. Claude keeps working turn by turn until all evidence items appear. Pair with **auto mode** in `settings.json` to remove per-tool-call prompts:

```json
{ "autoApproveTools": true }
```

**Warning:** auto mode + `/goal` inside a sandbox with explicit forbidden operations and hooks is powerful. Outside a sandbox it is not safe — the classifier may miss dangerous file-edit operations. Ensure `agents/orchestrator/SPEC.md` prohibitions are in place before enabling auto mode.

### Option B — Interactive (single phase trigger)

```
/bdos-orchestrator Implement Phase 0 — B01 repo-scaffold
```

Invoke once per batch. Orchestrator runs one turn, spawns the appropriate specialist, runs Test/Review, updates `docs/TASKS.md` and `docs/STATE.md`, and returns control to you.

---

## 3. Human Roles

There are three distinct human roles. One person can hold all three, or they can be split across a team.

### Requirement Author

**When:** Before the harness starts — and any time a new phase begins that requires new design decisions.

**Actions:**
- Write or approve `docs/PRODUCT_SPEC.md`, `docs/DESIGN.md`, `docs/TASKS.md`
- Author or approve Architecture Decision Records under `docs/adr/`
- Confirm public interface signatures (`LLMClient`, `Tool`, `JobRunner`, `MemoryStore`, `Orchestrator`, `Specialist`) before Phase 0 begins

Agents do not change public interfaces without an approved ADR. If an ADR is needed and not yet authored, the Orchestrator will stop and escalate.

### Gate Keeper

**When:** The Orchestrator signals a phase is complete (all tasks `Done` in `TASKS.md`, Test/Review sign-off received).

**Actions:**
- Review the `git diff` for the completed phase
- Run `git push -u origin <branch>` (agents never push)
- Run `gh pr create` to open a pull request (agents never create PRs)
- Confirm the phase is shippable before the next phase starts

Agents commit locally. Pushing and PR creation are always human-only steps.

### Escalation Resolver

**When:** The Orchestrator sends a structured escalation message (see §6).

**Actions:**
- Read the escalation: blocker description, what was already attempted, and the concrete question
- Answer the question or make the decision
- Re-invoke the Orchestrator with the resolved context: `/bdos-orchestrator <updated scope or decision>`

---

## 4. Agent Loop (1 turn = 1 atomic batch)

```
Human: /goal <condition with proof requirements>
  │
  [Each turn]
  Orchestrator:
  ├─ Step 1: Read docs/TASKS.md + docs/STATE.md
  ├─ Step 2: Acquire lease → STATE.md Active Lease = B0X
  ├─ Step 3: Select next Not Started batch (respect dependencies)
  ├─ Step 4: Spawn ONE specialist with scoped handoff
  │           └─ batch task IDs + relevant DESIGN.md interface section only
  ├─ Step 5: Specialist edits code OR returns structured blocker
  ├─ Step 6: Test/Review runs relevant checks (unit test / build / lint)
  ├─ Step 7: Orchestrator updates TASKS.md + STATE.md; clears lease
  └─ Step 8: Emit proof output in turn (for /goal Haiku evaluator)
  │
  [Haiku evaluator reads transcript]
  ├─ Evidence missing or incomplete → feedback to next turn
  └─ All evidence present → goal clear
  │
Human: reviews diff → git push → gh pr create
```

**Batch granularity:**

| | Example | Verdict |
|---|---|---|
| ✅ Right | B03: db-migration (6 tasks, 1 Alembic migration + repo layer) | One deliverable |
| ❌ Too small | "create folder", "add `__init__.py`" | Merge into batch |
| ❌ Too large | "Implement all of Phase 0" | Split into B01–B05 |

---

## 5. Human Checkpoints

These are the moments where the harness pauses and waits for a human action.

| # | Checkpoint | Trigger | Human Action |
|---|---|---|---|
| 1 | **Phase start** | You type `/bdos-orchestrator <scope>` | Confirm the scope is correct before pressing Enter |
| 2 | **ADR required** | Orchestrator lists required ADRs in its plan output | Author or approve the ADR; then re-invoke |
| 3 | **Escalation received** | Orchestrator sends a structured escalation (see §6) | Answer the concrete question; re-invoke |
| 4 | **Phase sign-off** | Test/Review agent outputs quality gate results | Review the output; push only if gates pass |
| 5 | **Interface change** | Any PR touching a public interface signature | Review the ADR that justifies the change before merging |

---

## 6. Escalation Triggers

The Orchestrator stops and waits for a human when:

- A specialist agent returns the same blocker twice with no progress.
- A phase dependency conflict requires a product decision (not a technical one).
- An ADR is needed but the Orchestrator lacks sufficient context to author it.
- Any of the following are involved: destructive git operations, schema migrations that drop data, API contract changes, public repository settings.

**Escalation message format** (what the Orchestrator will send):

```
## Escalation

**Blocker:** <description of what is blocked>
**Already attempted:** <what was tried>
**Question:** <the specific decision or information needed to proceed>
```

Respond to the question directly. If you need the Orchestrator to re-plan, re-invoke it with the new information.

---

## 7. Done Criteria (per phase)

A phase is complete when all of the following are true:

- [ ] All phase tasks are marked `Done` in `docs/TASKS.md`
- [ ] Test/Review agent has produced a passing quality gate report
- [ ] No open blockers remain
- [ ] Human has reviewed the diff and confirmed it is shippable
- [ ] `git push` and PR have been created by the human

Only after these criteria are met should the next phase begin.

---

## 8. Autonomous Execution via /goal

`/goal` requires Claude Code v2.1.139+. Evaluator: Haiku reads transcript only — it does not run tools or read files. **Write the condition so Claude's own output proves it.**

### Condition template

```
/goal Phase 0 is complete. Claude must show in this conversation:
1. grep output: all Phase 0 batches (B01–B05) show "Done" in docs/TASKS.md
2. make build exit code 0 (show terminal output)
3. git diff --stat showing committed Phase 0 artifacts
4. grep docs/STATE.md showing no Blocked or In Progress entries
Stop after 30 turns if not complete.
```

### /goal vs /loop

| | `/goal` | `/loop` |
|---|---|---|
| Next turn starts | After previous turn finishes | On time interval |
| Stops when | Haiku confirms condition | Manual stop or Claude decides |
| Right for | "Complete Phase 0" | "Check CI every 5 min" |

### auto mode safety

`auto mode` automates tool-call approval within one turn. It does **not** guarantee dangerous operations are blocked. Use only when:
- Prohibited operations are explicitly listed in `agents/orchestrator/SPEC.md`
- PreToolUse hooks block destructive operations (force-push, reset --hard, DROP TABLE)
- Human checkpoint exists at phase boundary (before git push)

❌ `auto mode + /goal = safe autonomous execution` — overstatement
✅ `auto mode + /goal inside a tightly scoped sandbox = fast autonomous loop`

### Quick reference

```bash
# Autonomous: run to completion
/goal Phase 0 is complete. Claude must show [evidence list]

# Interactive: one batch at a time
/bdos-orchestrator Implement Phase 0 — B01 repo-scaffold

# Check execution state
cat docs/STATE.md

# Check batch progress
grep -E "B0[0-9]|Done|Blocked" docs/TASKS.md

# After phase completes — human pushes
git push -u origin <branch>
gh pr create --title "Phase 0: Repository Foundation" --body "..."

# Re-invoke after resolving escalation
/bdos-orchestrator Continue Phase 0 — ADR approved, resume from B03
```

---

## References

- `AGENTS.md` — working rules, prohibitions, commit convention (canonical for all agents)
- `docs/STATE.md` — runtime execution state (active lease, last completed batch, blockers)
- `agents/orchestrator/SPEC.md` — Orchestrator's loop model, proof output format, write authority
- `agents/app-builder/SPEC.md` — App Builder's implementation constraints
- `agents/infra/SPEC.md` — Infra agent's scope and tooling
- `agents/test-review/SPEC.md` — Test/Review quality gates and sign-off process
- `docs/DESIGN.md §Public Interfaces` — interface signatures agents cannot change without an ADR
- `docs/DESIGN.md §Phase Progression` — phase ordering rules
- https://code.claude.com/docs/en/goal — `/goal` command specification
