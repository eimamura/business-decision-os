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
   `uv run pytest tests/unit/ -q && make lint && make typecheck && make build`

7. **Update state**

   - Pass: mark `T-XXXX` as `Done` in `docs/TASKS.md`; update `docs/STATE.md` Last Completed; clear Active Lease
   - Blocked: mark `Blocked`; record blocker; clear Active Lease

8. **Emit proof output**

   Use the standard Proof Output block (see SKILL.md §Proof Output).

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

## Agent Conflict Protocol

When two agents disagree or a handoff is rejected:

1. **Specialist rejects Orchestrator task**: Specialist returns a rejection with reason; Orchestrator re-evaluates the task scope, resolves the conflict (or escalates to user), and re-issues.
2. **App Builder ↔ Infra conflict** (e.g., missing env var, Dockerfile disagreement): the agent that discovered the gap files a blocking note in `docs/TASKS.md` and notifies Orchestrator. Orchestrator assigns the fix to the correct owner.
3. **Test/Review vs. App Builder disagreement** (bug vs. design intent): Test/Review files the issue with expected and actual behavior. App Builder must either fix or author an ADR explaining the intent. Orchestrator arbitrates if unresolved after one round.
4. **ADR authorship**: Domain experts (App Builder, Infra) may create a draft ADR at `docs/adr/DRAFT-YYYY-MM-DD-<slug>.md` when they need a design decision to unblock implementation. The Orchestrator reviews the draft, removes the `DRAFT-` prefix to confirm, and appends a summary to `docs/DECISIONS.md`. The Orchestrator authors ADRs directly when the decision spans multiple agents or requires product-level judgment.

---

## Handoff Rules

### Handing off to specialist agents

- **App Builder**: include task IDs, relevant `docs/DESIGN.md` sections (Public Interfaces, Stub Behavior), phase scope, ADR dependencies
- **Infra/DevOps**: include task IDs, relevant `docs/DESIGN.md §Deployment Design` sections, phase scope
- **Test/Review**: include task IDs, list of components to test, phase scope, which stubs are expected vs. real, and the check mode (`batch check` or `phase sign-off`)

### Failure handling

- If a specialist reports a blocker (missing ADR, unresolved dependency): pause the phase, resolve the blocker first, then re-issue the task
- If Test/Review reports failing Quality Gates: do not advance the phase; return the specific issues to the responsible agent (App Builder or Infra)
- If two phases have a dependency conflict under reordering: resolve via ADR before proceeding; document the resolution in `docs/DECISIONS.md`
