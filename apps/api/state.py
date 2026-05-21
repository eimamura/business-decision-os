from __future__ import annotations

import asyncio
import logging
import os
from asyncio import Queue
from typing import Any
from uuid import UUID

from packages.agent.runner import AcaJobsRunner, CeleryJobRunner, InProcessJobRunner
from packages.agent.llm import ClaudeClient, LLMUsage
from packages.agent.orchestrator import PhaseOrchestrator
from packages.memory import PgVectorMemoryStore, StubMemoryStore
from packages.persistence.llm_usage_repo import LlmUsageRepository
from packages.tools import create_tool_registry

logger = logging.getLogger(__name__)

sessions: dict[str, dict[str, Any]] = {}
sse_queues: dict[str, Queue[dict[str, Any]]] = {}


def _build_runner() -> AcaJobsRunner | InProcessJobRunner | CeleryJobRunner:
    backend = os.environ.get("JOB_RUNNER_BACKEND", "in_process").strip()
    if backend == "aca":
        return AcaJobsRunner()
    if backend == "celery":
        return CeleryJobRunner()
    return InProcessJobRunner()


def _build_memory_store() -> PgVectorMemoryStore | StubMemoryStore:
    url = os.environ.get("DATABASE_URL", "")
    if url:
        url = url.replace("postgresql+asyncpg://", "postgresql://")
        return PgVectorMemoryStore(url)
    return StubMemoryStore()


async def _real_usage_writer(
    session_id: UUID | None,
    agent_step_id: UUID | None,
    specialist_role: str | None,
    provider: str,
    model: str,
    usage: LLMUsage,
) -> None:
    if agent_step_id is None:
        return

    repo = LlmUsageRepository()

    async def _write() -> None:
        try:
            await repo.create(
                agent_step_id=str(agent_step_id),
                model=model,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                cache_read_tokens=usage.cache_read_tokens,
                cache_write_tokens=usage.cache_write_tokens,
                total_cost_usd=float(usage.total_cost_usd),
            )
        except RuntimeError as exc:
            logger.warning("LLM usage write skipped: %s", exc)
        except Exception as exc:
            logger.warning("LLM usage write failed: %s", exc)

    asyncio.create_task(_write())


def get_orchestrator(sse_queue: Queue[dict[str, Any]]) -> PhaseOrchestrator:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set — add it to .env")
    llm_client = ClaudeClient(api_key=api_key, usage_writer=_real_usage_writer)
    runner = _build_runner()
    tool_registry = create_tool_registry(runner=runner)
    memory_store = _build_memory_store()
    return PhaseOrchestrator(llm_client, tool_registry, memory_store, sse_queue)
