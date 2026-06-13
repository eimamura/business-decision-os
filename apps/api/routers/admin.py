from __future__ import annotations

import csv
import io
import logging
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
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


class AgentRegistryEntry(BaseModel):
    role: str
    display_name: str
    category: Literal["domain", "cross_domain", "orchestrator"]
    tools: list[str]
    execution_count: int
    last_executed_at: str | None


class ToolRegistryEntry(BaseModel):
    name: str
    display_name: str
    used_by_agents: list[str]
    execution_count: int
    last_executed_at: str | None


class RegistryResponse(BaseModel):
    agents: list[AgentRegistryEntry]
    tools: list[ToolRegistryEntry]


@router.get("/registry", response_model=RegistryResponse, status_code=status.HTTP_200_OK)
async def get_registry() -> RegistryResponse:
    """All agents and tools with execution counts and last-run timestamps."""
    from packages.tools.base import _ROLE_TOOL_ALLOWLIST

    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            agent_rows = await conn.fetch(
                """
                SELECT specialist_role,
                       COUNT(*)::int         AS execution_count,
                       MAX(started_at)       AS last_executed_at
                FROM agent_steps
                WHERE step_type = 'specialist_execution'
                GROUP BY specialist_role
                """
            )
            tool_rows = await conn.fetch(
                """
                SELECT payload->>'name'                AS tool_name,
                       COUNT(*)::int                   AS execution_count,
                       MAX(created_at)                 AS last_executed_at
                FROM session_events
                WHERE event_type = 'graph_node'
                  AND payload->>'kind' = 'tool'
                  AND payload->>'event' = 'end'
                  AND payload->>'name' IS NOT NULL
                GROUP BY payload->>'name'
                """
            )
    except RuntimeError as e:
        if "DATABASE_URL" in str(e):
            agent_rows = []
            tool_rows = []
        else:
            raise HTTPException(status_code=500, detail="Internal error")
    except Exception:
        _log.exception("get_registry failed")
        raise HTTPException(status_code=500, detail="Internal error")

    agent_stats: dict[str, dict[str, Any]] = {
        r["specialist_role"]: {
            "execution_count": r["execution_count"],
            "last_executed_at": (
                r["last_executed_at"].isoformat() if r["last_executed_at"] else None
            ),
        }
        for r in agent_rows
    }
    tool_stats: dict[str, dict[str, Any]] = {
        r["tool_name"]: {
            "execution_count": r["execution_count"],
            "last_executed_at": (
                r["last_executed_at"].isoformat() if r["last_executed_at"] else None
            ),
        }
        for r in tool_rows
    }

    def _category(role: str) -> Literal["domain", "cross_domain", "orchestrator"]:
        if role == "orchestrator":
            return "orchestrator"
        return "domain"

    agents: list[AgentRegistryEntry] = []
    for role, allowed_tools in _ROLE_TOOL_ALLOWLIST.items():
        stats = agent_stats.get(role, {"execution_count": 0, "last_executed_at": None})
        agents.append(AgentRegistryEntry(
            role=role,
            display_name=role.replace("_", " ").title(),
            category=_category(role),
            tools=list(allowed_tools),
            execution_count=stats["execution_count"],
            last_executed_at=stats["last_executed_at"],
        ))

    all_tool_names: set[str] = set()
    for _role_tools in _ROLE_TOOL_ALLOWLIST.values():
        all_tool_names.update(_role_tools)

    tool_to_agents: dict[str, list[str]] = {t: [] for t in all_tool_names}
    for role, allowed_tools in _ROLE_TOOL_ALLOWLIST.items():
        for t in allowed_tools:
            tool_to_agents[t].append(role)

    tools: list[ToolRegistryEntry] = []
    for tool_name in sorted(all_tool_names):
        stats = tool_stats.get(tool_name, {"execution_count": 0, "last_executed_at": None})
        tools.append(ToolRegistryEntry(
            name=tool_name,
            display_name=tool_name.replace("_", " ").title(),
            used_by_agents=sorted(tool_to_agents[tool_name]),
            execution_count=stats["execution_count"],
            last_executed_at=stats["last_executed_at"],
        ))

    return RegistryResponse(agents=agents, tools=tools)


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
                    lu.created_at,
                    ast.step_type,
                    lu.prompt_messages_json,
                    lu.response_text,
                    lu.tool_calls_json
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
                "step_type": r["step_type"],
                "prompt_messages_json": r["prompt_messages_json"],
                "response_text": r["response_text"],
                "tool_calls_json": r["tool_calls_json"],
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


@router.get(
    "/context-logs",
    response_model=list[Any],
    status_code=status.HTTP_200_OK,
)
async def list_context_logs(
    session_id: UUID | None = None,
    use_case_id: str | None = None,
    limit: int = Query(default=50, le=200),
) -> list[Any]:
    """Retrieve context_log entries, optionally filtered by session or use-case."""
    from packages.persistence.context_log import ContextLogRepository

    repo = ContextLogRepository()
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            if session_id is not None:
                rows = await repo.list_by_session(str(session_id), limit=limit, conn=conn)
            elif use_case_id is not None:
                rows = await repo.list_by_use_case(use_case_id, limit=limit, conn=conn)
            else:
                rows = await repo.list_recent(limit=limit, conn=conn)
        return [r.model_dump(mode="json") for r in rows]
    except RuntimeError as e:
        if "DATABASE_URL" in str(e):
            return []
        raise HTTPException(status_code=500, detail="Internal error") from e
    except Exception:
        _log.exception("list_context_logs failed")
        raise HTTPException(status_code=500, detail="Internal error")
