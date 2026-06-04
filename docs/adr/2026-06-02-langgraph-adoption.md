# ADR: LangGraph Adoption Decision

**Date:** 2026-06-02
**Status:** Rejected (for current phase) — revisit when conditions are met
**Reversal cost:** Low (no code changes made)

---

## Context

Two reference projects were reviewed: `lang-graph-agent-mvp` and `agentic-system-mvp`.
Both use LangGraph as their orchestration framework and demonstrate patterns that
address known gaps in the current bdos implementation:

- `AsyncPostgresSaver` PostgreSQL checkpointing — solves in-memory session state
- `interrupt()` + `Command(resume=...)` — proper HITL execution pause
- Built-in DAG parallel execution via graph edges
- `verify_findings` node pattern — hallucination prevention after tool loop
- `ask_clarification` node with interrupt loop — bidirectional HITL before execution

The question was whether to adopt LangGraph as the orchestration framework for bdos.

---

## Decision

**Do not adopt LangGraph at this time.**

---

## Reasons

### 1. The most critical problems are not in the orchestration layer

The issues that violate AGENTS.md rules and block production readiness are
domain-layer problems:

- Stub candidate fallback in `_rank_candidates` (prohibited by AGENTS.md)
- SHA-256 fake embeddings in `PgVectorMemoryStore._make_embedding()`
- Thin domain agents with no meaningful tool or prompt differentiation
- Guardrail with hardcoded roles and single-KPI risk classification

LangGraph adoption does not fix any of these.

### 2. High migration cost relative to benefit at this stage

Adopting LangGraph requires changing multiple public interfaces locked by DESIGN.md §Public Interfaces:

| Interface | Change required | ADR required |
|---|---|---|
| `LLMClient` | Must become or wrap LangChain `BaseChatModel` | Yes |
| `Tool` protocol | Must adopt `@tool` decorator; loses `requires_approval`, `audit_payload` | Yes |
| `Orchestrator` / `SessionOrchestrator` | Replaced by `StateGraph` | Yes |
| `Specialist` protocol | Becomes a LangGraph subgraph | Yes |
| `MemoryStore` | Must integrate with LangGraph checkpoint state | Yes |

Five concurrent ADRs plus a full rewrite of `packages/agent/` during a phase when
domain logic is incomplete creates unacceptable scope risk.

### 3. Every beneficial pattern is adoptable without the framework

| Pattern | LangGraph required? | Low-cost alternative |
|---|---|---|
| Session persistence | No | `sessions` table + persistence repo (T-005) |
| DAG parallelism | No | `asyncio.gather` in `run_dag_execution` (T-002) |
| Verify findings | No | Additional LLM call in `AgentRuntime.run()` (T-007) |
| 3-block prompt caching | No | `LLMMessage.content_blocks` already supports this (T-008) |
| LLM cost tracking | No | `llm_usage` table write after each `complete()` call (T-009) |

### 4. LangGraph prefers LangChain model abstractions

bdos intentionally uses a custom `LLMClient` that wraps the Anthropic SDK directly.
This enables fine-grained control over prompt caching (`cache_control` blocks),
per-call cost accounting, and specialist role metadata. Migrating to `BaseChatModel`
would require reimplementing these capabilities at the LangChain adapter boundary
or accepting reduced observability.

---

## Conditions for Reconsideration

Revisit LangGraph adoption when ALL of the following are true:

1. Domain logic layer is stable (T-001 through T-010 complete and tested)
2. Session persistence via a `sessions` table is proven insufficient — e.g., complex
   multi-step resumption logic that a simple status column cannot model
3. DAG parallel execution via `asyncio.gather` hits a performance wall — e.g., need
   for distributed execution across Celery workers rather than in-process concurrency
4. The team is ready to commit to 5 concurrent ADRs and a full `packages/agent/` rewrite

---

## Consequences

- Specific patterns from reference projects are adopted incrementally without framework
  dependency (see DECISIONS.md entries dated 2026-06-02)
- No public interface changes in the Domain Integrity phase
- LangGraph remains a viable option for a future architectural phase once the domain
  layer is production-ready
