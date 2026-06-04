# DECISIONS.md

Lightweight daily log of key design decisions.

Historical decisions (2026-06-02 – 2026-06-03, P0–P23) archived at `docs/archive/v3/DECISIONS.md`.

| Date | Decision | Rationale |
|---|---|---|
| 2026-06-04 | Add Ollama as dev LLM provider (`LLM_PROVIDER=ollama`) | Eliminate Anthropic API costs during local development; qwen2.5-coder:7b runs comfortably on 8 GB RAM in WSL2. `LLMClient` protocol unchanged. ADR: `docs/adr/2026-06-04-ollama-local-llm-provider.md` |
