"""Seeds llm_pricing with verified model rates.

Usage: uv run python scripts/seed_llm_pricing.py

Rates verified 2026-05-17:
  Anthropic: https://www.anthropic.com/pricing
  OpenAI:    https://openai.com/api/pricing/
"""

from __future__ import annotations

import asyncio

PRICING = [
    {
        "model": "claude-sonnet-4-6",
        "input_cost_per_1k": 0.003,
        "output_cost_per_1k": 0.015,
        "cache_read_cost_per_1k": 0.0003,
        "cache_write_cost_per_1k": 0.00375,
    },
    {
        "model": "claude-opus-4-7",
        "input_cost_per_1k": 0.015,
        "output_cost_per_1k": 0.075,
        "cache_read_cost_per_1k": 0.0015,
        "cache_write_cost_per_1k": 0.01875,
    },
    {
        "model": "text-embedding-3-small",
        "input_cost_per_1k": 0.00002,
        "output_cost_per_1k": 0.0,
        "cache_read_cost_per_1k": 0.0,
        "cache_write_cost_per_1k": 0.0,
    },
]


async def seed() -> None:
    raise NotImplementedError("Phase 1 — DB required")


if __name__ == "__main__":
    asyncio.run(seed())
