# ADR: Ollama Local LLM Provider

Date: 2026-06-04

## Status

Accepted

## Context

Every development and test run that touches the LLM layer incurs Anthropic API costs. Engineers
working on features that involve repeated LLM round-trips (agent loops, tool call parsing, streaming
output) pay real money per iteration even when correctness, not quality, is the concern. A local LLM
provider that costs zero would allow faster iteration and reduce the friction for contributors who do
not have a funded Anthropic key.

Three local-inference alternatives were evaluated:

| Candidate | Install complexity | OpenAI-compat API | Tool call support | Notes |
|---|---|---|---|---|
| **Ollama** | Single binary (`curl | sh`) | Yes — `/v1/chat/completions` | Yes (model-dependent) | Default model qwen2.5-coder:7b |
| LM Studio | GUI + manual model download | Yes | Limited | Requires graphical desktop |
| vLLM | Docker + GPU recommended | Yes | Yes | Heavy; impractical on laptops |

`MOCK_LLM=true` / `ScenarioStubClaudeClient` already covers cost-free testing of the agent logic.
Ollama fills a different gap: real LLM inference at zero cost, useful when the developer needs to
validate prompt quality or observe how the model navigates tool call sequences without paying per
token.

## Decision

Add `OllamaClient` to `packages/agent/llm/__init__.py`. Route to it when the environment variable
`LLM_PROVIDER=ollama` is set. The default model is `qwen2.5-coder:7b` (overridable via
`OLLAMA_MODEL`). The base URL defaults to `http://localhost:11434` (overridable via
`OLLAMA_BASE_URL`).

### Selected model: qwen2.5-coder:7b

qwen2.5-coder:7b is selected as the default because:

1. It is strong on code-related tasks (the primary workload of this system).
2. The 7 B parameter size fits in 8 GB of unified memory (common on developer laptops).
3. Ollama publishes a pre-quantized GGUF that downloads with a single `ollama pull` command.
4. It supports the OpenAI tool-call format exposed by Ollama's `/v1/chat/completions` endpoint.

Other models (llama3.2, mistral, phi3) are valid substitutes via `OLLAMA_MODEL` — the client is
model-agnostic.

### API compatibility

Ollama exposes an OpenAI-compatible REST API at `{base_url}/v1/chat/completions`. The request and
response shapes mirror `POST /v1/chat/completions` in the OpenAI spec:

- `messages`: role/content array (system / user / assistant / tool)
- `tools`: `[{"type": "function", "function": {"name", "description", "parameters"}}]`
- `tool_calls` in the assistant message (when the model chooses a tool)
- `usage.prompt_tokens` / `usage.completion_tokens`
- `finish_reason`: `"stop"` | `"tool_calls"` | `"length"`

`OllamaClient` translates `LLMMessage` / `LLMToolSpec` to these shapes and maps the response back
to `LLMResponse`.

### Cost tracking

`LLMUsage.total_cost_usd` is set to `Decimal("0")` for every Ollama call. Local inference has no
per-token billing. Budget guards (`BudgetGuard`, `BudgetedClaudeClient`) still work correctly —
they accumulate zero cost and never trigger soft or hard limits.

### Embedding

`OllamaClient.embed()` returns `[[0.0] * 1536 for _ in texts]` — a zero-vector stub. No local
embedding model is bundled. This matches the existing `StubClaudeClient.embed()` behavior and is
not a "smart stub" — it makes no attempt to approximate semantic similarity. If a developer needs
real embeddings locally they should configure a dedicated embedding model and override the
implementation, or use `OPENAI_API_KEY` with the real `PgVectorMemoryStore`.

### Public interface

The `LLMClient` Protocol signature is **unchanged**:

```python
async def complete(messages, tools, temperature, max_tokens, prompt_cache,
                   agent_step_id, specialist_role) -> LLMResponse
async def stream(messages, tools, temperature, max_tokens, prompt_cache,
                 agent_step_id, specialist_role) -> AsyncIterator[LLMStreamEvent]
async def embed(texts, model, agent_step_id) -> list[list[float]]
```

No ADR upgrade is required for that contract. This ADR covers the new provider addition only.

### Fail-fast configuration

Per AGENTS.md prohibitions, missing or empty config must raise `RuntimeError` — no silent
fallback. `OllamaClient.__init__` raises `RuntimeError` if `base_url` is an empty string. The
`create_llm_client()` factory reads `OLLAMA_BASE_URL` and `OLLAMA_MODEL` from the environment and
passes them to the constructor; an empty `OLLAMA_BASE_URL` triggers the constructor guard.

## Consequences

- Developers can run the full agent loop locally with no API key by setting `LLM_PROVIDER=ollama`
  and starting Ollama (`ollama serve`).
- Response quality and latency differ from Anthropic Claude. Ollama is suitable for prompt
  development and tool-call parsing validation, not production.
- `httpx.AsyncClient` is used for HTTP calls; `httpx>=0.27.0` is already a project dependency —
  no new packages are needed.
- The `LLM_PROVIDER` env var is new. Existing deployments that do not set it default to
  `"anthropic"`, preserving backward compatibility.
- Usage writer is called with `provider="ollama"` and zero cost, so observability dashboards will
  correctly show local calls as free.

## Reversibility

Low reversal cost. To remove Ollama support: delete the `OllamaClient` class, remove the
`"ollama"` branch from `create_llm_client()`, remove the three env vars from `.env.example`. No
database schema changes were made.
