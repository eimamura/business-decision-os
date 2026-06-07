# ADR: LangChain ChatModel Migration — Phase 1

**Date:** 2026-06-07  
**Status:** Accepted  
**Deciders:** Erielcio Imamura

---

## Context

The current `LLMClient` custom protocol wraps Anthropic and Ollama APIs directly. This works, but leaves several concerns at the application layer:

1. **Manual JSON parsing** — `_json_obj()` / `LLMResponseParseError` in every orchestrator call  
2. **Provider-specific workarounds** — `think=False`, `response_format=json_object` scattered in `OllamaClient`  
3. **No structured output primitive** — schema validation is ad-hoc  
4. **Coupling** — intent classifiers and router logic depend on raw text output and parsing details

LangChain `BaseChatModel` provides:
- `.with_structured_output(PydanticModel)` — eliminates manual JSON parsing and parse errors  
- `.bind_tools()` — standard tool-calling interface  
- Provider-independence via a uniform interface (`ChatAnthropic`, `ChatOllama`, etc.)  
- Callback/tracing hooks for future observability

---

## Decision

**Add LangChain as a core dependency and migrate in phases:**

### Phase 1 (P52 — this ADR)

1. Add `langchain-core`, `langchain-anthropic`, `langchain-ollama` to `pyproject.toml`
2. Introduce `ModelRegistry` (`packages/agent/model_registry.py`) — maps role names to `BaseChatModel` instances with provider-specific configuration
3. Migrate the three orchestrator-role LLM calls to `with_structured_output()`:
   - `classify_intent()` → `SessionIntent`
   - `select_execution_mode()` → `AgentRoute`
   - `_node_prepare_ask_user()` ask/no-ask decision → `AskUserDecision`
4. **`LLMClient` protocol is NOT removed in this phase** — still used by `ControlAgent` and Planner

### Subsequent phases (not in scope here)

- P53: Migrate `ControlAgent` to `bind_tools()` + `BaseChatModel`
- P54: Migrate Planner to `with_structured_output()`
- P55: Migrate usage tracking to LangChain Callbacks
- P56: Delete `LLMClient` protocol after all callers migrated

---

## ModelRegistry Design

```python
class ModelRegistry:
    def get(self, role: str) -> BaseChatModel: ...
```

Roles: `"orchestrator"`, `"planner"`, `"control"`

Provider configuration is encapsulated in the registry factory (`create_model_registry()`), not in application code. Ollama-specific parameters (`think`, `num_predict`) are set at factory time per role.

| Role | Anthropic | Ollama |
|------|-----------|--------|
| orchestrator | `ChatAnthropic(model=claude-sonnet-4-6, temperature=0)` | `ChatOllama(model=..., temperature=0, think=False)` |
| planner | same | `ChatOllama(model=..., temperature=0, think=False)` |
| control | same | `ChatOllama(model=..., temperature=0)` |

---

## Consequences

**Positive:**
- Structured output eliminates `_json_obj`, `LLMResponseParseError`, `_normalize_llm_text` usage in orchestrator calls
- `think=False` and `response_format` complexity moves into `ModelRegistry` factory
- Clear migration path toward full LangChain adoption

**Negative / Risks:**
- LangChain adds ~3 packages to the dependency tree  
- `ChatOllama.with_structured_output()` reliability with 2B models (e.g., `qwen3.5:2b`) is unproven — recommend using `qwen2.5:7b` or larger for orchestrator role
- Parallel existence of `LLMClient` and `BaseChatModel` during migration increases complexity temporarily

---

## Alternatives Considered

**Add `complete_structured()` to `LLMClient`** — avoids LangChain dependency but reinvents what `with_structured_output()` already provides.

**Full immediate migration** — too risky; `ControlAgent` tool calling and streaming require careful testing.
