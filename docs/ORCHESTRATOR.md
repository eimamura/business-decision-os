# Orchestrator Reference

Detailed workflows and processes for the `bdos-orchestrator` coding agent.
See `.claude/skills/bdos-orchestrator/SKILL.md` for the role definition and phase loop.

---

## Design Improvement Loop

Use this loop when a design deficiency is discovered in an **already-completed phase** — through conversation, code review, or runtime observation. This is an amendment to the standard Phase Loop, not a new phase.

### Trigger Conditions

A Design Improvement is warranted when **all** of the following hold:
- The target phase is already `Done` in `docs/TASKS.md`
- The problem is a design deficiency (coupling, missing abstraction, incorrect separation of concerns)
- The fix requires code changes beyond a trivial bug fix

Do **not** use this loop for: runtime bugs (use Defect Task), new product features (use a new Phase), or infra-only changes (route directly to Infra/DevOps).

### Step-by-Step Process

1. **Identify and classify**

   Determine whether the improvement touches a public interface:

   | Change type | ADR required? |
   |---|---|
   | `JobSpec.kind` Literal addition | Yes — `JobRunner` public interface |
   | `Predictor` Protocol signature change | Yes — public interface |
   | Internal implementation swap (e.g. `LinearRegressionPredictor` → `TrainedModelPredictor`) | No — same Protocol |
   | New `kind` value in existing `JobSpec` | Yes |

2. **Draft ADR (if required)**

   Before touching code, author `docs/adr/YYYY-MM-DD-<slug>.md`.
   Required sections: Context, Decision, Rationale, Trade-offs, Consequences (affected interfaces and files).
   Append a one-line entry to `docs/DECISIONS.md`.

3. **Add amendment task to `docs/TASKS.md`**

   Orchestrator (sole writer) appends to the relevant completed phase section:

   ```
   | T-XXXX | <short description> | Not Started |
   ```

   Task ID format: continue the repository-wide T-NNN sequence (e.g., if the last task in `docs/TASKS.md` is T-146, the next is T-147).

4. **Acquire lease**

   Set `docs/STATE.md` Active Lease = `T-XXXX` before spawning specialist.

5. **Scoped handoff to App Builder**

   Include:
   - Task ID and description
   - ADR reference (if authored)
   - The specific `docs/DESIGN.md` §Public Interfaces subsection relevant to the change
   - Constraint: do not change the public interface Protocol itself unless ADR explicitly approves it

6. **Await result and run Test/Review**

   Same quality gate as the standard loop:
   `make test-unit && make lint && make typecheck && make test-integration`
   Note: includes `make test-integration` because design improvements amend completed phases where integration regressions carry higher risk (see FP-003).

7. **Update state**

   - Pass: mark `T-XXXX` as `Done` in `docs/TASKS.md`; update `docs/STATE.md` Last Completed; clear Active Lease
   - Blocked: mark `Blocked`; record blocker; clear Active Lease

8. **Emit proof output**

   Use the standard Proof Output block from §Proof Output below.

### Example: Forecast Training/Inference Separation (Phase 6 Amendment)

| Step | Action |
|---|---|
| Classify | `JobSpec.kind` gets new value `"train_forecast"` → ADR required |
| ADR | `docs/adr/2026-05-20-forecast-training-job.md` — separating offline training from online inference |
| Task | T-147 added to Phase 6 amendment section of TASKS.md (continuing repository-wide sequence) |
| Handoff | App Builder: add `kind="train_forecast"` to `JobSpec`; implement `TrainedModelPredictor`; keep `Predictor` Protocol unchanged |
| No change | `ForecastTool` — already depends only on `Predictor` Protocol |

---

## TASKS.md Structure

### Batch Table (Orchestrator writes; one table per active phase)

| Batch | Tasks | Status | Blocked Count |
|---|---|---|---|
| B-01 — name | T-147, T-148 | Not Started | 0 |

- **Status values**: `Not Started` | `In Progress` | `Done` | `Blocked`
- **Blocked Count**: incremented by the Orchestrator each time a batch is marked `Blocked`; never decremented. Reaches 2 → escalate to human.

### Task Rows (specialists write their own rows)

| T-XXXX | description | Not Started |

- **Status values**: `Not Started` | `In Progress` | `Done` | `Blocked`
- Task IDs are repository-wide sequential (T-001, T-002, …); never reused.

---

## Defect Task Format

Register a Defect Task in **any** of these situations:

- A quality gate failure persists after the responsible agent's first fix attempt.
- A test or runtime failure is discovered in an already-completed phase (i.e., not caught during normal phase execution).
- A `fix(...)` commit is required in a phase after Test/Review sign-off was already given.

In all cases, append a Defect block directly under the relevant batch heading in `docs/TASKS.md`:

```
#### Defect: D-NNN

- Status: Open | Resolved
- Severity: High | Medium | Low
- Repro: `<exact command to reproduce>`
- Observed: <what actually happened>
- Expected: <what should happen>
- Area: <package or directory>
- Owner: App Builder | Infra/DevOps
- Acceptance: <test or check that proves it is resolved>
```

Defect IDs are D-001, D-002, … (repository-wide sequence; never reused).
The phase cannot advance while any Defect in the current phase has `Status: Open`.
Orchestrator marks the block `Resolved` once Test/Review confirms the Acceptance criterion passes.

**After marking Resolved:**
Invoke `/analyze-failure <D-NNN>` to record the root cause in `docs/failure-patterns.md`.
If the pattern reaches Count 2, `/harden-system <FP-NNN>` must be invoked before the next phase begins.

---

## ADR Triggers

Author an ADR under `docs/adr/YYYY-MM-DD-<slug>.md` whenever:

- A public interface signature changes (`LLMClient`, `Tool`, `JobRunner`, `MemoryStore`, `Orchestrator`, `Specialist`).
- A technology choice is added or replaced (LLM provider, framework, DB, etc.).
- Risk thresholds, KPI weight defaults, or schema CHECK constraints change.
- `llm_pricing` seed values are updated.
- The SQL Tool allowlist is modified.

Each ADR must include: background, candidates considered, decision, rationale, tradeoffs, reversibility / re-evaluation triggers.

---

## Agent Conflict Protocol

When two agents disagree or a handoff is rejected:

1. **Specialist rejects Orchestrator task**: Specialist returns a rejection with reason; Orchestrator re-evaluates the task scope, resolves the conflict (or escalates to user), and re-issues.
2. **App Builder ↔ Infra conflict** (e.g., missing env var, Dockerfile disagreement): the agent that discovered the gap files a blocking note in `docs/TASKS.md` and notifies Orchestrator. Orchestrator assigns the fix to the correct owner.
3. **Test/Review vs. App Builder disagreement** (bug vs. design intent): Test/Review files the issue with expected and actual behavior. App Builder must either fix or author an ADR explaining the intent. Orchestrator arbitrates if unresolved after one round.
4. **ADR authorship**: Domain experts (App Builder, Infra) may create a draft ADR at `docs/adr/DRAFT-YYYY-MM-DD-<slug>.md` when they need a design decision to unblock implementation. The Orchestrator reviews the draft, removes the `DRAFT-` prefix to confirm, and appends a summary to `docs/DECISIONS.md`. The Orchestrator authors ADRs directly when the decision spans multiple agents or requires product-level judgment.

---

## Structured Handoff Format

All Orchestrator → specialist handoffs must use this format. Prose-only handoffs are rejected.

```
### Handoff: <batch-id> → <agent-role>

batch: <B-NN>
tasks: [T-NNN, T-NNN, ...]
scope: <one sentence describing the deliverable>
mode: implementation | stub | infra | batch-check | phase-sign-off
design_sections:
  - docs/DESIGN.md §<section name>   # list only what this batch needs
adr_dependencies:
  - docs/adr/YYYY-MM-DD-<slug>.md    # or: none
known_risks:
  - <optional: edge cases, blockers the specialist should know about>
```

**Rules:**
- Include only the `docs/DESIGN.md` sections the batch touches. Do not paste full docs.
- `mode` determines how Test/Review runs: `batch-check` = unit+lint+typecheck only; `phase-sign-off` = full Quality Gates.
- If `adr_dependencies` is non-empty, specialist must read those ADRs before coding.

---

## Handoff Rules

### Handing off to specialist agents

Use the Structured Handoff Format above for every handoff. Quick reference for which `design_sections` to include:

| Specialist | design_sections to include |
|---|---|
| App Builder | `§Public Interfaces` (when touching an interface), `docs/TESTING.md §Stub Conformance` (stub tasks), `§Monorepo Layout` (new files) |
| Infra/DevOps | `§Deployment Design` |
| Test/Review | list of components to test + stub-vs-real status; set `mode` appropriately |

### Failure handling

- If a specialist reports a blocker (missing ADR, unresolved dependency): pause the phase, resolve the blocker first, then re-issue the task
- If Test/Review reports failing Quality Gates: do not advance the phase; return the specific issues to the responsible agent (App Builder or Infra)
- If two phases have a dependency conflict under reordering: resolve via ADR before proceeding; document the resolution in `docs/DECISIONS.md`

---

## Phase Sign-Off Checklist

Run during phase sign-off (after all batches are `Done`, before marking phase `Done`):

1. All mandatory Quality Gates pass (see SKILL.md §Run Mode step 8).
2. **DECISIONS.md promotion scan**: read `docs/DECISIONS.md` and check for entries that:
   - Mention a public interface, technology swap, or schema change, **AND**
   - Have no corresponding file under `docs/adr/`.
   For each match, emit: `"WARNING: DECISIONS.md entry '<date>: <summary>' mentions a public interface but has no ADR. Promote to docs/adr/ in the next phase intake."`
   This is a BLOCKING gate — a phase MUST NOT be marked Done if any DECISIONS.md entry mentions a public interface, technology swap, or schema change without a corresponding file under docs/adr/. Resolve by authoring the ADR before closing the phase.
3. No `Defect Task` in the current phase has `Status: Open`.
4. `docs/STATE.md` Active Lease is `None`.

### Mandatory Gate Set

This subsection is the single source of truth for the mandatory phase sign-off gate set and the
sign-off acceptance rule. `.claude/skills/bdos-orchestrator/SKILL.md` and other skills point here
rather than restating these rules.

**Mandatory gate set (non-negotiable — applies to every phase sign-off without exception):**

```
make test-unit
make test-integration
make test-e2e        (or make test-playwright for Playwright-only phases)
make build
make lint
make typecheck
```

These six commands (or their equivalents) MUST appear as named gate rows in the sign-off report. A
sign-off that omits `make test-integration` is structurally incomplete regardless of what other gates
passed.

**Sign-off acceptance rule**: The Orchestrator MUST NOT accept a sign-off unless ALL of the following
are true:

1. The report contains a gate row for `make test-integration` (exact command name required).
2. Every gate row includes `gate`, `exit_code`, and `output_tail` fields.
3. Every gate has `exit_code: 0`.

A report that omits `make test-integration` entirely, or that lists it as "skipped", "not applicable",
or "N/A", is NOT a valid sign-off — reject it and re-request execution with the full mandatory gate set.

---

## Proof Output (for `/goal` evaluator)

The `/goal` evaluator reads only what appears in the conversation transcript. Every Orchestrator turn must end with this block so the evaluator has evidence to judge:

```
## Proof Output

**Batch completed:** <batch ID and name>
**Validation:**
  - command: <e.g. make test>
  - exit code: <0 or non-zero>
  - output: <relevant lines>

**Phase progress:**
<paste batch status rows from docs/TASKS.md — exclude "Not Started" rows>

**STATE.md snapshot:**
  - Active Lease: None
  - Last Completed: <batch>
  - Blockers: <None or list>
```

When all batches are Done, also emit:
```
**Phase complete evidence:**
  - All batches Done: <grep proof>
  - make build: exit 0
  - git diff --stat: <output>
  - No Blocked or In Progress remaining: <grep proof>
```

---

## TASKS.md and STATE.md Write Authority

| File | Who writes | What they write |
|---|---|---|
| `docs/TASKS.md` — phase/batch status | **Orchestrator only** | `Not Started → Done / Blocked`; new Defect Task rows |
| `docs/TASKS.md` — individual task rows | Specialists | `In Progress / Done`; blocking notes on their assigned rows |
| `docs/STATE.md` | **Orchestrator only** | Active lease, last completed batch, validation results, blockers |

Specialists update only their own assigned task rows. They MUST NOT change batch-level status, mark a batch `Blocked`, or write to `docs/STATE.md` — report blockers to Orchestrator instead.

In addition to `docs/TASKS.md` and `docs/STATE.md`, the Orchestrator's writable targets include `docs/DECISIONS.md` (append-only), `docs/adr/` (new files only), and new reference/design files under `docs/` — the Orchestrator must not overwrite existing docs files; edits to existing reference docs are delegated to a specialist. This matches AGENTS.md §Prohibitions and `.claude/skills/bdos-orchestrator/SKILL.md`.

---

## Planning Output Format — Plan Mode

```
## Phase X — [Name]

### Batch 1 — [Topic] (Agent: App Builder | Infra | Test/Review)
- T-XXXX: description
- T-XXXX: description
Dependencies: none | Batch N

### Batch 2 ...

### Blockers
- [any known blockers]

### ADRs needed
- [any decisions requiring an ADR]
```
