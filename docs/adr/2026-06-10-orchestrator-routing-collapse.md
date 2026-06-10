# ADR: Orchestrator Routing Collapse — Single ControlAgent Execution Path

Date: 2026-06-10
Status: Accepted
Phase: P66

## Context

Since P38 (specialist routing deactivated) and P45 (Control-Agent-only routing),
`VALID_AGENT_ROLES == {"control"}` and `CROSS_DOMAIN_AGENT_CLASSES == {}`. P65 deleted the
15 dead agent class files. The SessionOrchestrator, however, still carries the multi-agent
execution machinery built for the S&OP specialist era:

- `_INTENT_MODE_MAP` (`routing.py`) routes `cross_domain_analysis` to `sequential_agents`
  and `decision_support` to `planned_execution` — but with one valid role, every "sequence"
  and every "plan" degenerates to a single ControlAgent call.
- `run_dag_execution` / `_build_dag_graph` / `create_task_nodes` (`planning.py`) implement
  fan-out DAG execution that can never fan out.
- `decision.py` (`_extract_candidates`, `_rank_candidates`, `_build_decision_response`)
  gates on results from a `simulation_optimizer` agent that has not been instantiable since
  P38 (`decision.py:97,241`); its candidate-ranking path is unreachable.
- The graph nodes `run_sequential`, `run_planned`, `run_dag` in `session_orchestrator.py`
  are three different wrappers around what is now the same single-agent call.

Dead control flow is not free: every change to the orchestrator must reason about four
execution modes, three of which cannot occur, and the test suite spends files
(`test_dag_parallel_execution.py`, `test_decision_rank_candidates.py`) protecting them.

## Decision

1. Collapse `_INTENT_MODE_MAP` to two execution modes:
   - `direct_chat` — `chat` intent (unchanged).
   - `single_agent` — all other intents (`lookup`, `domain_analysis`,
     `cross_domain_analysis`, `supply_chain`, `decision_support`); one ControlAgent call
     with the intent-scoped tool subset (`_INTENT_TOOL_SUBSET`).
2. Remove `sequential_agents` and `planned_execution` modes: delete `run_planned` and
   `run_dag` graph nodes, `run_planned_execution`, `create_execution_plan`,
   `create_task_nodes`, `_build_dag_graph`, `run_dag_execution`, and `_fan_out_edge`.
   `_node_run_sequential` survives only if it is the surviving single-agent executor;
   otherwise `single_agent` maps to one retained node.
3. Remove the `simulation_optimizer`-gated candidate logic in `decision.py`. If
   `decision_support` synthesis survives via ControlAgent output, keep only that live path;
   `weights.py` is deleted if nothing live consumes `resolve_weights`.
4. `validate_route` keeps rejecting unknown roles; mode validation shrinks to the surviving
   modes.

## Invariants (must not change)

- The **6 intent categories** in `INTENT_REGISTRY` are preserved — they drive
  `_INTENT_TOOL_SUBSET` (P63/P64) and the classifier prompt.
- The **SSE event contract** (`graph_node` start/end, `text_delta`, `response_ready`,
  `awaiting_input`, `done`, `error`, and their `meta` fields including `model_name`) is
  byte-for-byte unchanged; the ExecutionPanel UI must render identically.
- Public interfaces (`Tool`, `JobRunner`, `MemoryStore`, `Orchestrator`, `Specialist`)
  signatures unchanged.
- HITL flows (ask_user interrupt/resume, job approval) unchanged.

## Consequences

- Orchestrator control flow becomes one decision: chat vs. ControlAgent.
- ~600+ lines of unreachable orchestration logic and their tests are removed.
- Re-introducing true multi-agent execution later is a deliberate design act (new ADR), not
  a latent code path; the LangGraph node structure makes adding nodes straightforward.
- `apps/api/routers/admin.py` `_category()` and `roles.py` lose the empty
  `CROSS_DOMAIN_AGENT_CLASSES` indirection.

## Alternatives considered

- **Keep the modes dormant for future multi-agent work** — rejected: P38's "keep until it
  creates problems" policy already expired once (P65); dormant modes cost reasoning and
  test surface every phase, and git history preserves the implementation.
- **Also merge intent categories** — rejected: categories are load-bearing for tool
  subsetting and prompt classification quality; merging them changes LLM-visible behavior,
  which is out of scope for a waste-removal refactoring.
