from __future__ import annotations

import uuid
from typing import Any

from packages.persistence.db import get_pool


class LlmUsageRepository:
    async def create(
        self,
        agent_step_id: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cache_read_tokens: int = 0,
        cache_write_tokens: int = 0,
        total_cost_usd: float = 0.0,
        request_id: str | None = None,
        latency_ms: int | None = None,
    ) -> str:
        row_id = str(uuid.uuid4())
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO llm_usage
                    (id, agent_step_id, model, input_tokens, output_tokens,
                     cache_read_tokens, cache_write_tokens, total_cost_usd,
                     request_id, latency_ms)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                """,
                uuid.UUID(row_id),
                uuid.UUID(agent_step_id),
                model,
                input_tokens,
                output_tokens,
                cache_read_tokens,
                cache_write_tokens,
                total_cost_usd,
                request_id,
                latency_ms,
            )
        return row_id

    async def get_session_totals(self, session_id: str) -> dict[str, Any]:
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    COALESCE(SUM(lu.input_tokens), 0)::int   AS input_tokens,
                    COALESCE(SUM(lu.output_tokens), 0)::int  AS output_tokens,
                    COALESCE(SUM(lu.total_cost_usd), 0.0)    AS total_cost_usd
                FROM llm_usage lu
                JOIN agent_steps ast ON ast.id = lu.agent_step_id
                WHERE ast.session_id = $1
                """,
                uuid.UUID(session_id),
            )
        if row is None:
            return {"input_tokens": 0, "output_tokens": 0, "total_cost_usd": 0.0}
        return {
            "input_tokens": row["input_tokens"],
            "output_tokens": row["output_tokens"],
            "total_cost_usd": float(row["total_cost_usd"]),
        }
