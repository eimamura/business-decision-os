from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, status

from apps.api.state import sessions as _sessions_cache
from packages.persistence.db import get_pool

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.get("/steps", response_model=list[dict[str, Any]], status_code=status.HTTP_200_OK)
async def list_agent_steps(limit: int = 200) -> list[dict[str, Any]]:
    """All agent steps with per-step LLM usage totals, newest first."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    ast.id                                          AS step_id,
                    ast.session_id,
                    ds.title                                        AS session_title,
                    ds.goal                                         AS session_goal,
                    ast.specialist_role,
                    ast.step_type,
                    ast.started_at,
                    ast.ended_at,
                    EXTRACT(EPOCH FROM (ast.ended_at - ast.started_at))::int * 1000 AS duration_ms,
                    COALESCE(SUM(lu.input_tokens), 0)::int          AS input_tokens,
                    COALESCE(SUM(lu.output_tokens), 0)::int         AS output_tokens,
                    COALESCE(SUM(lu.total_cost_usd), 0.0)           AS total_cost_usd
                FROM agent_steps ast
                JOIN decision_sessions ds ON ds.id = ast.session_id
                LEFT JOIN llm_usage lu ON lu.agent_step_id = ast.id
                GROUP BY ast.id, ds.title, ds.goal
                ORDER BY ast.started_at DESC NULLS LAST
                LIMIT $1
                """,
                limit,
            )
        return [
            {
                "step_id": str(r["step_id"]),
                "session_id": str(r["session_id"]),
                "session_title": r["session_title"] or r["session_goal"] or "Untitled",
                "specialist_role": r["specialist_role"],
                "step_type": r["step_type"],
                "started_at": r["started_at"].isoformat() if r["started_at"] else None,
                "ended_at": r["ended_at"].isoformat() if r["ended_at"] else None,
                "duration_ms": r["duration_ms"],
                "input_tokens": r["input_tokens"],
                "output_tokens": r["output_tokens"],
                "total_cost_usd": float(r["total_cost_usd"]),
            }
            for r in rows
        ]
    except RuntimeError as e:
        if "DATABASE_URL" in str(e):
            return []
        raise HTTPException(status_code=500, detail="Internal error")
    except Exception:
        _log.exception("list_agent_steps failed")
        return []


@router.get("/llm-usage", response_model=list[dict[str, Any]], status_code=status.HTTP_200_OK)
async def list_llm_usage(limit: int = 500) -> list[dict[str, Any]]:
    """All LLM usage records with step and session context, newest first."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    lu.id,
                    lu.agent_step_id,
                    ast.specialist_role,
                    ast.session_id,
                    ds.title       AS session_title,
                    ds.goal        AS session_goal,
                    lu.model,
                    lu.input_tokens,
                    lu.output_tokens,
                    lu.cache_read_tokens,
                    lu.cache_write_tokens,
                    lu.total_cost_usd,
                    lu.latency_ms,
                    lu.created_at
                FROM llm_usage lu
                JOIN agent_steps ast ON ast.id = lu.agent_step_id
                JOIN decision_sessions ds ON ds.id = ast.session_id
                ORDER BY lu.created_at DESC
                LIMIT $1
                """,
                limit,
            )
        return [
            {
                "id": str(r["id"]),
                "agent_step_id": str(r["agent_step_id"]),
                "specialist_role": r["specialist_role"],
                "session_id": str(r["session_id"]),
                "session_title": r["session_title"] or r["session_goal"] or "Untitled",
                "model": r["model"],
                "input_tokens": r["input_tokens"],
                "output_tokens": r["output_tokens"],
                "cache_read_tokens": r["cache_read_tokens"],
                "cache_write_tokens": r["cache_write_tokens"],
                "total_cost_usd": float(r["total_cost_usd"]),
                "latency_ms": r["latency_ms"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ]
    except RuntimeError as e:
        if "DATABASE_URL" in str(e):
            return []
        raise HTTPException(status_code=500, detail="Internal error")
    except Exception:
        _log.exception("list_llm_usage failed")
        return []


@router.delete("/sessions", status_code=status.HTTP_200_OK)
async def delete_all_sessions() -> dict[str, int]:
    """Delete all sessions from DB and in-memory cache."""
    _sessions_cache.clear()
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("DELETE FROM decision_sessions RETURNING id")
        return {"deleted": len(rows)}
    except RuntimeError as e:
        if "DATABASE_URL" in str(e):
            return {"deleted": 0}
        raise HTTPException(status_code=500, detail="Internal error")
    except Exception:
        _log.exception("delete_all_sessions failed")
        raise HTTPException(status_code=500, detail="Internal error")
