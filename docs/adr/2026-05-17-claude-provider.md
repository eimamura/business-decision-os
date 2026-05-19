# ADR-0001: Claude Sonnet 4.6 as LLM Provider

**Date:** 2026-05-17  
**Status:** Accepted  
**Deciders:** Engineering Team

## Context

The Business Decision OS requires a capable LLM to power multi-agent supply chain reasoning across five specialist roles: Orchestrator, Domain Expert, Data Engineer, Sim/Opt, and Evaluator. The LLM must support reliable tool-calling (function calling), structured JSON output, and streaming for the SSE-based Reasoning Panel. Cost predictability is important given that every session can involve tens of LLM calls.

## Decision

Use **Anthropic Claude Sonnet 4.6** as the sole LLM for all text completion and tool-use calls. The `LLMClient` interface is abstracted so the underlying provider can be swapped without changing call sites. All calls use `temperature=0` and prompt caching is enabled by default.

Azure OpenAI `text-embedding-3-small` (1536 dimensions) is used for embedding calls routed through the same `LLMClient.embed()` method.

## Rationale

- **Tool-calling stability:** Claude Sonnet 4.6 produces well-formed tool-call JSON reliably, which is critical for the schema-driven Tool Layer.
- **Structured output:** Pydantic-shaped outputs require consistent adherence to output schemas across multi-turn agent loops.
- **Prompt caching:** Anthropic's prompt caching feature reduces cost on stable system prompts shared across specialist roles.
- **Partnership alignment:** Anthropic has a commercial partnership with Azure, simplifying billing and support.
- **`temperature=0`:** Deterministic output enables `vcrpy` cassette-based testing and reproducible CI runs.

## Trade-offs

- **Vendor lock-in:** All text completion depends on Anthropic's API. Mitigated by the `LLMClient` Protocol abstraction, which allows an OpenAI-compatible provider to be swapped in without changing call sites.
- **Cache pinning discipline:** Prompt caching requires careful prompt segmentation to maintain high hit rates. Prompts that vary frequently undermine cache savings.
- **No multi-provider comparison:** Committing to a single provider foregoes A/B cost or quality comparisons.

## Consequences

- The `LLMClient` implementation lives in `packages/agent/llm`; all other packages depend on the Protocol, not the concrete class.
- Every LLM call writes one `llm_usage` row in the same DB transaction as the parent `agent_step_id`. No bypass path exists.
- `llm_pricing` is seeded at migration time with verified per-1k-token rates for `claude-sonnet-4-6` (and `claude-opus-4-7` for future use). See `docs/adr/2026-05-17-llm-pricing-seed.md`.
- Anthropic outage renders the service unavailable. Nightly real-API E2E tests catch regressions before they reach users.
- If a provider swap is required in Phase 9+, a new ADR is required and the `LLMClient` concrete class is replaced — no call-site changes needed.
