# ADR: Context Engineering — render_* Functions over ContextBuilder Class

- Date: 2026-06-13
- Status: Accepted
- Phases: P107, P108, P109
- Decision owner: User (approved 2026-06-13)

## Context

As the system prompt grew (P107–P109), three maintainability problems emerged:

1. **Prompt rot** — hardcoded tool names and table/column literals in `_SYSTEM_PROMPT`
   were not tracked by the compiler, type checker, or test runner. A tool rename would
   silently leave the prompt referencing a non-existent name.

2. **Flat structure** — business guidelines, routing policy, schema context, and response
   format were concatenated in a single string with no conceptual boundaries, making each
   section hard to locate and edit in isolation.

3. **Unclear extension points** — future sections (user permissions, screen state, RAG
   context, conversation summary) had no defined place to attach.

The canonical design pattern for addressing these problems in LLM applications is
*context engineering*: treating the system prompt not as a fixed document but as a
**runtime view assembled from code, schema, and configuration**.

Two implementation strategies were considered:

**Option A — render_* functions (chosen)**

```python
def _build_system_prompt(intent, user_role, schema_context) -> str:
    return "\n\n".join(filter(None, [
        render_business_guidelines(),
        render_routing_policy(intent),
        render_tool_catalog(intent),
        render_schema_context(schema_context),
        render_response_format(),
    ]))
```

**Option B — ContextBuilder class**

```python
class AgentContextBuilder:
    def build(self, request: ChatRequest) -> AgentContext:
        intent = classify_intent(request.message)
        tools  = get_tools_for_intent(intent)
        prompt = _build_system_prompt(intent, ...)
        return AgentContext(messages=[...], tools=tools, intent=intent)
```

## Decision

**Option A** — render_* functions, no ContextBuilder class — for the current phase.

## Rationale

At the time of this decision, the only variables driving prompt composition are `intent`
and `schema_context`. Memory context (`DecisionMemoryStore`, `LongTermMemoryStore`) is
already injected as **conversation messages** inside `ControlAgent.run()`, not as
prompt sections, so it is outside the scope of the prompt builder.

A ContextBuilder class would be justified when the prompt builder must incorporate
**multiple request-level states that vary independently**. That threshold is not met:

| Signal | Status |
|---|---|
| `intent` (supply_chain / lookup / domain_analysis) | ✅ in scope |
| `schema_context` (DB tables/columns) | ✅ in scope |
| `user_role` (analyst / manager / admin) | Reserved — param exists, `render_user_permissions()` not yet implemented |
| Screen state (selected SKU, active view) | Not yet injected |
| RAG context | Not present |
| Conversation summary | Not present (memory is messages, not prompt) |

Introducing a ContextBuilder now would create a class with largely empty methods,
increase indirection without reducing complexity, and complicate testing of the async
memory path (which `ContextBuilder.build()` would need to `await`).

The render_* functions are already individually testable as pure functions. The
`test_control_prompt.py` suite covers:

- All backtick-quoted tool names in the assembled prompt exist in the `ToolRegistry`
- `render_routing_policy` output contains every tool in `_INTENT_TOOL_SUBSET`
- `render_business_guidelines` contains no tool names (separation of concerns)
- `render_response_format` contains the four required section headers

## Escalation Trigger

Revisit this decision and introduce a `ContextBuilder` (or equivalent assembly layer)
when **any two** of the following become true simultaneously:

1. `render_user_permissions(user_role)` is implemented and changes the tool subset or
   prompt content based on the caller's role
2. Screen state (selected SKU, active page, filter state) is injected into the prompt
3. A RAG retrieval step (embedding search over domain knowledge) feeds a prompt section
4. Conversation summary or session memory is injected as a prompt section (not only as
   a message in the conversation history)

At that point the prompt builder requires **request-level async state** and consolidating
it into a `ContextBuilder` prevents the wiring from scattering across `chat.py`,
`agent.py`, and `sessions.py`.

## Consequences

- `_INTENT_TOOL_SUBSET` remains the single source of truth for intent → tool mapping;
  `render_routing_policy()` and `render_tool_catalog()` generate the prompt text from it.
- `_build_system_prompt()` signature is `(intent, user_role, schema_context)`;
  `user_role` is accepted but unused — this reserves the parameter without coupling to
  a not-yet-implemented permission system.
- The `_SYSTEM_PROMPT_TEMPLATE` string is deprecated (empty stub, backward-compat only).
- Any new context signal (screen state, permissions, RAG) gets its own `render_*()`
  function first; if two or more such functions require async I/O, that is the trigger
  to introduce the ContextBuilder layer.
