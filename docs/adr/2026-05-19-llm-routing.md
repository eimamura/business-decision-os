# ADR: LLM-Based Specialist Routing in PhaseOrchestrator

**Date:** 2026-05-19  
**Status:** Accepted  
**Deciders:** Engineering Team

## Context

`PhaseOrchestrator.run()` originally hardcoded `role_sequence = ["domain_expert", "data_engineer", "sim_opt", "evaluator"]` and ran all 4 specialists unconditionally for every user message. This meant:

- A minimum of 4 LLM API calls per message (up to 40 if each specialist exhausted its 10-iteration loop).
- `sim_opt` and `evaluator` executed even for simple data queries (e.g., "What is the current inventory level?") where they produce no useful output.
- The Orchestrator was a broadcaster, not a coordinator — contradicting the design intent stated in `docs/DESIGN.md §Multi-Agent Architecture`.

## Decision

Add a single LLM routing call (`_route_specialists`) at the start of `PhaseOrchestrator.run()` that returns a JSON array of the specialist roles required for the given goal. Only those specialists are invoked.

## Rationale

- **One call, not four:** A routing call costs one small LLM request (max 256 output tokens) but can eliminate 3 unnecessary specialist calls (each up to 10 iterations). Net saving is positive for any non-full-pipeline query.
- **LLM over rules:** Keyword-based routing would need maintenance as goal phrasing varies. The LLM understands intent and handles novel phrasings naturally.
- **Stable interface:** `Specialist.run()` and `ToolContext` are unchanged. Routing is entirely internal to `PhaseOrchestrator`; no public interface signature changed.
- **Safe fallback:** Any routing failure (parse error, empty result, LLM error) falls back to the full 4-specialist sequence and logs a warning. This keeps the system correct under all conditions.

## Trade-offs

- **Benefit:** Reduces LLM API calls and latency for simple queries; makes the Orchestrator behave as the coordinator it was designed to be.
- **Cost / risk:** Adds one LLM call per session. For full-pipeline goals the net cost is marginally higher (+1 routing call). Routing may misclassify ambiguous goals.
- **Mitigation:** The fallback guarantees correctness. The `selected_roles` field in the `step_completed` SSE event makes routing decisions observable in the Reasoning Panel for debugging.

## Consequences

- `packages/agent/orchestrator/__init__.py`: `_route_specialists()` method added; `_ROUTING_SYSTEM` prompt, `_VALID_ROLES`, `_ALL_ROLES` constants added at module level; `run()` replaced hardcoded sequence with dynamic routing + SSE events.
- `tests/unit/test_phase1_integration.py`: 4 new routing tests added; all existing 132 unit tests continue to pass.
- `docs/DESIGN.md §Orchestrator Routing`: new section documents routing rules, invariants, and SSE events.
- No follow-up ADRs required. Phase 9 `AgentBasedSpecialist` migration will supersede routing when parallel execution is introduced.
