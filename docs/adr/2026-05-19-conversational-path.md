# ADR: Conversational Query Path in PhaseOrchestrator

**Date:** 2026-05-19  
**Status:** Accepted  
**Deciders:** Engineering Team

## Context

After adding LLM-based routing (ADR 2026-05-19-llm-routing), the routing step had no "no specialists needed" path. When the LLM returned an empty role list or an unrecognised role for conversational inputs (greetings, chit-chat, off-topic messages), `_route_specialists()` raised `ValueError` and fell back to the full 4-specialist pipeline. This meant a greeting like "Good morning" triggered the entire supply-chain optimisation loop — wasteful and semantically wrong.

## Decision

Add `"none"` as an explicit routing option. When routing returns `["none"]` or `[]`, `PhaseOrchestrator.run()` skips all specialists and calls the LLM once with a brief conversational system prompt, returning a `Recommendation` with `direct_reply` set and `primary = None`. `sessions.py` short-circuits `_format_recommendation()` on `direct_reply`.

`Recommendation.primary` and `Recommendation.tradeoff` are made optional (`None` default) to represent this state cleanly without a separate type.

## Rationale

- **Explicit signal over ambiguity:** `["none"]` is unambiguous — the router intentionally said "no specialists". Distinguishing it from parse errors prevents incorrect fallback behaviour.
- **No Protocol change:** `Orchestrator.run()` still returns `Recommendation`; adding optional fields to the schema is backward-compatible and does not require an ADR for interface signatures.
- **Minimal LLM cost:** 1 routing call + 1 conversational reply call (≤ 512 tokens) for greetings, versus 1 routing + up to 40 specialist calls previously.
- **Frontend unchanged:** The existing `done` event `reply` field already carries plain text — no frontend changes needed.

## Trade-offs

- **Benefit:** Eliminates the full-pipeline trigger for non-decision queries; makes the system feel natural for conversational use.
- **Cost / risk:** `Recommendation.primary` is now `Optional` — callers that access `rec.primary.action` without a null check will raise `AttributeError`. `_format_recommendation()` is the only such caller and is guarded.
- **Mitigation:** Type checker (`mypy`) will flag any future unguarded access to `rec.primary` or `rec.tradeoff`.

## Consequences

- `packages/schemas/recommendation.py`: `primary`, `tradeoff` now `| None = None`; `direct_reply: str | None = None` added.
- `packages/agent/orchestrator/__init__.py`: `_ROUTING_SYSTEM` gains `"none"` option and rule 5; `_route_specialists()` returns `[]` for `["none"]`/`[]` without triggering fallback; `run()` gains early-return conversational branch.
- `apps/api/routers/sessions.py`: `_format_recommendation()` short-circuits on `direct_reply`.
- `tests/unit/test_phase1_integration.py`: 2 new tests added; all 134 unit tests pass.
- No follow-up ADRs required.
