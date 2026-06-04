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
   | T-XXXX | <short description> | Medium | Not Started |
   ```

   Task ID format: continue the phase's numeric sequence (e.g., Phase 6 Done has T-6004 → add T-6005).

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

   - Pass: mark `T-XXXX` as `Done` in `docs/TASKS.md`; update `docs/STATE.md` Last Completed + Last Validation; clear Active Lease
   - Blocked: mark `Blocked`; record blocker; clear Active Lease

8. **Emit proof output**

   Use the standard Proof Output block (see SKILL.md §Proof Output).

### Example: Forecast Training/Inference Separation (Phase 6 Amendment)

| Step | Action |
|---|---|
| Classify | `JobSpec.kind` gets new value `"train_forecast"` → ADR required |
| ADR | `docs/adr/2026-05-20-forecast-training-job.md` — separating offline training from online inference |
| Task | T-6005 added to Phase 6 section of TASKS.md |
| Handoff | App Builder: add `kind="train_forecast"` to `JobSpec`; implement `TrainedModelPredictor`; keep `Predictor` Protocol unchanged |
| No change | `ForecastTool` — already depends only on `Predictor` Protocol |
