# ADR: Autonomy Loops — Goal Evaluation, Grounded Verification, Feedback Learning

Date: 2026-06-10
Status: Accepted
Phases: P71, P72, P73

## Context

The system today is a single-pass pipeline: classify intent → (ask user) → route → one
ControlAgent run → END. Three structural gaps prevent it from behaving as an autonomous
assistant (analysis 2026-06-10):

1. **No goal loop.** `SessionGoal` is never constructed; `goal_text` is extracted at
   classification and never used. Nothing judges whether the final answer satisfies the
   user's goal, and there is no bounded retry with a corrected strategy.
2. **No grounded verification.** `_verify_findings_node` applies deterministic string rules
   only; `_after_verify` always returns END, leaving the existing
   `add_revision_message → call_model_final` self-correction path unreachable dead wiring.
3. **No learning loop.** UI feedback (+1/−1) is stored on `messages` and never consumed;
   `decision_log` records what was decided but not how it was received, so past-decision
   injection cannot distinguish good answers from bad ones.

Constraint: local 12B-class models. Every added LLM call must be bounded, gated by intent,
and fail-open (graceful skip on parse failure — but missing-config errors still raise per
AGENTS.md).

## Decision

### 1. Goal evaluation loop (SessionOrchestrator — P71)

- After `classify_intent`, for non-chat intents, derive a first-class goal:
  `GoalSpec {goal_text, success_criteria: list[str] (≤3)}` via one structured-output call
  (orchestrator role). Stored in `OrchestratorState`.
- New node `evaluate_goal` after `run_sequential`: structured verdict
  `GoalEvaluation {satisfied: bool, missing: str|None, reroute_category: str|None}`.
- If `satisfied` or `refine_count ≥ 1` → END. Otherwise one refinement pass: re-enter
  `run_sequential` with the `missing` feedback appended to the instruction; if
  `reroute_category` names a different valid intent category, the intent (and therefore the
  tool subset) is updated first — this is the misclassification recovery path.
- `direct_chat` bypasses the loop entirely. Hard bound: **one** refinement per turn.
- `SessionResponse` gains an additive optional field `goal_evaluation: dict | None`.
- New nodes emit standard `graph_node` SSE events (`kind="orchestrator"`); event schema
  unchanged, so the ExecutionPanel renders them without UI changes.

### 2. Grounded verification (AgentRuntime — P72)

- `_verify_findings_node` keeps the rule-based checks as a fast pre-filter, then — only for
  intents in {domain_analysis, cross_domain_analysis, decision_support, supply_chain} with
  non-empty `tool_results` — runs one LLM groundedness check (control role):
  `GroundednessVerdict {grounded: bool, unsupported_claims: list[str]}`.
- `_after_verify` gains the third transition `needs_revision` → the existing
  `add_revision_message → call_model_final` path (currently dead) is reconnected; the
  revision message now embeds the specific unsupported claims. One retry, then END.
- If the verdict call fails (parse error, stub model), verification falls back to
  rule-based only — never blocks the answer on verifier infrastructure.

### 3. Feedback learning loop (P73)

- Additive migration: `decision_log.outcome SMALLINT NULL` (+1 / −1, NULL = unrated).
- `PATCH /messages/{id}/feedback` additionally sets `outcome` on the latest
  `record_type='decision'` row of the session (best-effort, non-fatal; MVP approximation:
  latest decision ≈ the rated answer).
- `DecisionMemoryStore.search` returns `outcome`; ControlAgent's Past Decisions context
  block annotates each entry (`[user feedback: positive/negative]`) and the system prompt
  instructs the agent to avoid approaches that previously received negative feedback.

## Invariants

- SSE event **schema** unchanged (new node names only); HITL flows unchanged.
- `Orchestrator` / `Specialist` protocol signatures unchanged; `SessionResponse` change is
  additive-optional only.
- Migration is additive (no data dropped/altered).
- LLM call budget per turn: +1 (goal spec) +1 (goal eval) +1 (groundedness) worst case,
  each gated and fail-open.

## Consequences

- The orchestrator becomes a closed loop (act → evaluate → refine once) instead of a
  conveyor; misclassification gains a recovery path.
- Dead self-correction wiring in `runtime.py` becomes live and tested.
- decide → observe(feedback) → recall loop closes; full simulate→observe learning
  (prediction vs. actuals) remains future work, as does a persistent cross-turn agenda
  (deferred deliberately — separate ADR when tackled).

## Alternatives considered

- **Multi-step replanning (N retries, plan trees)** — rejected for MVP: latency on local
  models and degenerate-loop risk; one bounded refinement captures most of the value.
- **Linking feedback to decisions via message_id foreign key** — rejected for MVP: decision
  records are written inside the agent run before the assistant message row exists;
  session-latest approximation avoids cross-layer ID plumbing.
- **LLM-as-judge for every turn including chat** — rejected: cost/latency on 12B local
  models; chat needs no goal machinery.
