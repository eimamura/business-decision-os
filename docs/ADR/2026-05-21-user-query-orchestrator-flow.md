# ADR: User Query Orchestrator Flow

Date: 2026-05-21

## Status

Accepted

## Context

`SessionOrchestrator.run()` previously accepted `SessionGoal` and always drove execution toward a DAG and `Recommendation`. That forced conversational messages, factual lookups, and lightweight analysis through a decision-oriented path.

The product design requires the SessionOrchestrator to receive user utterances first, classify intent, choose an execution mode, and create a decision goal only when the user request actually needs decision support.

## Decision

Change the public orchestrator contract to:

```python
run(session_id: UUID, query: SessionUserQuery) -> SessionResponse
```

`SessionUserQuery` is the entry type for all user messages. `SessionGoal` remains available internally for weight resolution and decision-memory writes when a request becomes decision-support work.

`SessionResponse` replaces `Recommendation` as the run return value and unifies direct chat replies, routed agent results, and decision outputs.

Execution modes are:

- `direct_chat`
- `single_agent`
- `sequential_agents`
- `planned_execution`
- `dag_execution`

The SSE event taxonomy changes to:

`query_received`, `intent_classified`, `execution_mode_selected`, `plan_created`, `agent_started`, `agent_completed`, `tool_started`, `tool_completed`, `response_ready`, `approval_requested`, `auto_executed`, `error`, `done`.

## Consequences

API routers construct `SessionUserQuery` from request bodies and use `SessionResponse.reply` for assistant messages and terminal `done.reply`.

`Recommendation` remains in the schema package for persistence and approval compatibility, but it is no longer the return type of `Orchestrator.run()`.

`SpecialistTask` and `SpecialistResult` remain the existing agent execution contract. Routing and SSE vocabulary uses `agent_role`.

## Reversal Cost

High. Reverting would require changing the public orchestrator interface, API streaming contract, and web reasoning trace model back to a decision-only flow.
