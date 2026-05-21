# ADR: LLM Pricing Seed Values

**Date:** 2026-05-17
**Status:** Accepted
**Deciders:** Erielcio Imamura

## Context

The `llm_pricing` table stores per-1k-token USD rates for each model used by the system. These rates are recorded on every `llm_usage` row so historical cost data remains accurate even after price changes. Migration 0001 seeds initial pricing rows; `scripts/seed_llm_pricing.py` handles idempotent upserts. Local bootstrap: `make seed-all` (includes this script with `DATABASE_URL` from the Makefile).

## Decision

Seed three model rows on `effective_date = 2026-05-17`:

| Model | Input ($/1k) | Output ($/1k) | Cache Read ($/1k) | Cache Write ($/1k) | Source |
|---|---|---|---|---|---|
| claude-sonnet-4-6 | 0.003 | 0.015 | 0.0003 | 0.00375 | Anthropic pricing page |
| claude-opus-4-7 | 0.015 | 0.075 | 0.0015 | 0.01875 | Anthropic pricing page |
| text-embedding-3-small | 0.00002 | 0.0 | 0.0 | 0.0 | OpenAI pricing page |

**Sources:**
- Anthropic: https://www.anthropic.com/pricing
- OpenAI: https://openai.com/api/pricing/

Cache pricing for Anthropic models follows the prompt caching discount structure:
- Cache read: 10% of input token price
- Cache write: 125% of input token price

## Update Policy

1. When Anthropic or OpenAI announces pricing changes, add a new row with the updated `effective_date` rather than mutating existing rows (future schema enhancement).
2. For the current single-row-per-model schema, re-run `scripts/seed_llm_pricing.py` which performs `ON CONFLICT DO UPDATE`. Historical `llm_usage` rows retain the cost already computed at write time and are not retroactively modified.
3. The engineer responsible for the price update must commit the change to `scripts/seed_llm_pricing.py` with a `chore(deps): update llm_pricing seed` commit and run the script against all environments.
4. Budget thresholds in `settings` should be reviewed after each price change.

## Consequences

- All cost computations are performed at `LLMClient` write time using rates queried from `llm_pricing` at that moment.
- A pricing change mid-session does not affect in-flight `llm_usage` rows because cost is computed and stored atomically with each call.
- The `source_url` column provides an audit trail to the authoritative price reference for each model.
- `text-embedding-3-small` has zero output and cache costs because embeddings are input-only operations with no caching discount structure at the time of seeding.
