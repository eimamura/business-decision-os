from __future__ import annotations

import csv
import io
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from apps.api.state import sessions as _sessions_cache
from packages.persistence.db import get_pool
from packages.persistence.sample_data import replace_operational_tables
from scripts.generate_sample_data import SampleDataConfig, generate

GROUND_TRUTH_DIR = Path("data/sample/ground_truth")

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


class GroundTruthDataset(BaseModel):
    columns: list[str]
    rows: list[list[str]]


class GroundTruthResponse(BaseModel):
    sku_parameters: GroundTruthDataset
    location_parameters: GroundTruthDataset
    supplier_parameters: GroundTruthDataset
    customer_parameters: GroundTruthDataset


def _read_ground_truth_csv(name: str) -> GroundTruthDataset:
    path = GROUND_TRUTH_DIR / f"{name}.csv"
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{name}.csv not found")
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)
    if not rows:
        return GroundTruthDataset(columns=[], rows=[])
    return GroundTruthDataset(columns=rows[0], rows=rows[1:])


def _write_ground_truth_csv(name: str, dataset: GroundTruthDataset) -> None:
    path = GROUND_TRUTH_DIR / f"{name}.csv"
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(dataset.columns)
    writer.writerows(dataset.rows)
    path.write_text(buf.getvalue(), encoding="utf-8")


class GenerateSampleDataRequest(BaseModel):
    seed: int = 42
    sku_count: int = Field(default=30, ge=1, le=30)
    horizon_days: int = Field(default=365, ge=1, le=1095)
    warehouse_count: int = Field(default=2, ge=1, le=10)
    missing_rate: float = Field(default=0.02, ge=0, le=0.25)


class SampleDataTableSummary(BaseModel):
    table_name: str
    row_count: int
    top_rows: list[dict[str, Any]]


class GenerateSampleDataResponse(BaseModel):
    tables: list[SampleDataTableSummary]


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


@router.post(
    "/sample-data/generate",
    response_model=GenerateSampleDataResponse,
    status_code=status.HTTP_200_OK,
)
async def generate_sample_data(
    body: GenerateSampleDataRequest,
) -> GenerateSampleDataResponse:
    try:
        generate(
            SampleDataConfig(
                seed=body.seed,
                sku_count=body.sku_count,
                horizon_days=body.horizon_days,
                warehouse_count=body.warehouse_count,
                missing_rate=body.missing_rate,
            )
        )
        pool = await get_pool()
        async with pool.acquire() as conn:
            tables = await replace_operational_tables(conn)
        return GenerateSampleDataResponse(
            tables=[SampleDataTableSummary.model_validate(table) for table in tables]
        )
    except RuntimeError as e:
        if "DATABASE_URL" in str(e):
            raise HTTPException(status_code=500, detail="DATABASE_URL not set") from e
        raise HTTPException(status_code=500, detail="Internal error") from e
    except Exception as e:
        _log.exception("generate_sample_data failed")
        raise HTTPException(status_code=500, detail="Internal error") from e


@router.get(
    "/ground-truth",
    response_model=GroundTruthResponse,
    status_code=status.HTTP_200_OK,
)
async def get_ground_truth() -> GroundTruthResponse:
    return GroundTruthResponse(
        sku_parameters=_read_ground_truth_csv("sku_parameters"),
        location_parameters=_read_ground_truth_csv("location_parameters"),
        supplier_parameters=_read_ground_truth_csv("supplier_parameters"),
        customer_parameters=_read_ground_truth_csv("customer_parameters"),
    )


@router.put(
    "/ground-truth",
    response_model=GroundTruthResponse,
    status_code=status.HTTP_200_OK,
)
async def save_ground_truth(body: GroundTruthResponse) -> GroundTruthResponse:
    try:
        _write_ground_truth_csv("sku_parameters", body.sku_parameters)
        _write_ground_truth_csv("location_parameters", body.location_parameters)
        _write_ground_truth_csv("supplier_parameters", body.supplier_parameters)
        _write_ground_truth_csv("customer_parameters", body.customer_parameters)
    except HTTPException:
        raise
    except Exception as e:
        _log.exception("save_ground_truth failed")
        raise HTTPException(status_code=500, detail="Internal error") from e
    return await get_ground_truth()
