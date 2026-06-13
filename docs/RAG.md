# RAG Architecture

## 1. RAG Classification and Implementation Status

| Type | Status | Notes |
|---|---|---|
| Database RAG / Tool RAG | Implemented (core) | All tools under `packages/tools/` |
| Memory RAG | Partial | `PgVectorMemoryStore` (vector 1536-dim) implemented. `LongTermMemoryStore.search()` uses recency-ordered fallback — pgvector similarity search is Post-MVP |
| Document RAG | Not implemented | Out of scope |
| Agentic RAG | Fully implemented | LangGraph multi-node graph in `packages/agent/runtime.py` |

## 2. Agentic RAG Loop Structure

`packages/agent/runtime.py` — `AgentRuntime._build_graph()` constructs the following LangGraph `StateGraph`:

```
START
  ↓
compress_history
  ↓
plan_tools
  ↓
call_model
  ↓ (tool_calls present)
execute_tools  ──→ call_model (loops up to _MAX_ITERATIONS=10)
  ↓ (finish_reason == "stop")
verify_findings
  ↓ (needs_revision)
add_revision_message → call_model_final
  ↓
END
```

The `add_revision_message → call_model_final` branch runs only when `verify_findings` returns a groundedness verdict of `needs_revision`. On all other exits (`blocked` or `completed`), the graph proceeds directly to `END`.

Human-in-the-loop nodes (`prepare_hitl` / `wait_for_approval`) are inserted between `call_model` and `execute_tools` when the tool call requires approval. The edge from `call_model` to `prepare_hitl` fires when `_call_model_node` routes to `"prepare_hitl"`.

Loop safeguards (all implemented):

| Safeguard | Mechanism |
|---|---|
| Intent-based tool restriction | `_INTENT_TOOL_SUBSET` in `control_agent.py`; further narrowed by `ContextBuilder` |
| Maximum iterations | `_MAX_ITERATIONS = 10` in `runtime.py` |
| Human approval | `prepare_hitl` / `wait_for_approval` nodes |
| Duplicate tool call guard (post-exec) | D-011: `loop_guard_triggered=True` → `synthesize_from_tools` |
| Duplicate tool call guard (pre-exec) | D-012: pre-execution check in `_call_model_node` routing; routes to `synthesize_from_tools` or `verify_findings` |
| Fallback forced synthesis | `synthesize_from_tools` → `verify_findings` forced termination |

## 3. RAG Result Placement Design

Placement policy:

| Layer | Content |
|---|---|
| `system` | Immutable role definition, safety rules, response policy only |
| `role="user"` | User question + Memory RAG results (past decisions, domain knowledge, DB schema) |
| `role="tool"` | Tool execution results (Database RAG / SQL / API) |

Implementation mapping:

| RAG Type | Delivery | Implementation |
|---|---|---|
| Tool execution results (Database RAG) | `role="tool"` | `runtime.py:960-964` — `LLMMessage(role="tool", ...)` |
| Past decisions (DecisionMemory) | `task.instruction` → `role="user"` | `control_agent.py` `_inject_past_decisions()` |
| Domain knowledge (LongTermMemory) | `task.instruction` → `role="user"` | `control_agent.py` `_inject_domain_knowledge()` |
| DB schema | `task.instruction` → `role="user"` | `control_agent.py` `_inject_schema_context()` — added in P117-B-02 |

Before P117-B-02, DB schema was injected via `_build_system_prompt()` into the `system` message. That was a design error: schema is request-scoped data, not a fixed role instruction. P117-B-02 moves it to `task.instruction` so it flows through `role="user"` alongside the other Memory RAG content.

## 4. Memory RAG Detail

`packages/memory/` contains three stores:

**`PgVectorMemoryStore`** (`packages/memory/__init__.py`)
- Backed by the `memories` table (migration 0001).
- Embeddings: OpenAI `text-embedding-3-small`, 1536-dimensional cosine similarity (`embedding <=> $1::vector`).
- Requires `OPENAI_API_KEY`; raises `RuntimeError` at call site if not set.
- `search()` returns `list[tuple[Memory, float]]` filtered by `min_similarity`.

**`DecisionMemoryStore`** (`packages/memory/decision.py`)
- Backed by the `decision_log` table.
- `write()` inserts decisions and failures per session.
- `search()` uses recency-ordered fallback. pgvector similarity search is Post-MVP.
- Called by `control_agent.py` `_inject_past_decisions()` with `task.instruction` as the search query (semantic key — changed from session-ID key in P116-B-03, T-673).

**`LongTermMemoryStore`** (`packages/memory/long_term.py`)
- Backed by the `long_term_memory` table.
- `write()` accepts `memory_type`, `content`, `scope`, and `metadata`.
- `search()` uses recency-ordered fallback. pgvector similarity search is Post-MVP.
- Called by `control_agent.py` `_inject_domain_knowledge()` with `scope:{intent_category}` as the search key.
