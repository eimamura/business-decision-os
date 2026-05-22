from __future__ import annotations

import asyncio
import logging
import os
from asyncio import Queue
from typing import Any
from uuid import UUID

from collections.abc import Callable

from packages.agent.llm import ClaudeClient, LLMUsage
from packages.agent.orchestrator import SessionOrchestrator
from packages.agent.runner import AcaJobsRunner, CeleryJobRunner, InProcessJobRunner
from packages.memory import PgVectorMemoryStore, StubMemoryStore
from packages.persistence.llm_usage_repo import LlmUsageRepository
from packages.persistence.session_events_repo import SessionEventRepository
from packages.tools import create_tool_registry

logger = logging.getLogger(__name__)

sessions: dict[str, dict[str, Any]] = {}


class Broadcaster:
    """Fan-out pub/sub so multiple /stream connections each get every event."""

    def __init__(self) -> None:
        self._subs: list[Queue[dict[str, Any]]] = []

    async def put(self, event: dict[str, Any]) -> None:
        for q in self._subs:
            await q.put(event)

    def subscribe(self) -> Queue[dict[str, Any]]:
        q: Queue[dict[str, Any]] = Queue()
        self._subs.append(q)
        return q

    def unsubscribe(self, q: Queue[dict[str, Any]]) -> None:
        try:
            self._subs.remove(q)
        except ValueError:
            pass


broadcasters: dict[str, Broadcaster] = {}


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


def make_event_persister(session_id: str) -> Callable[[dict[str, Any]], Any]:
    async def _persister(event: dict[str, Any]) -> None:
        repo = SessionEventRepository()

        async def _write() -> None:
            try:
                await repo.create(
                    session_id=session_id,
                    event_type=event.get("type", "unknown"),
                    payload=event,
                )
            except RuntimeError as exc:
                logger.warning("event persist skipped: %s", exc)
            except Exception as exc:
                logger.warning("event persist failed: %s", exc)

        asyncio.create_task(_write())

    return _persister


def get_orchestrator(sse_queue: Any | None = None) -> SessionOrchestrator:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set — add it to .env")
    llm_client = ClaudeClient(api_key=api_key, usage_writer=_real_usage_writer)
    runner = _build_runner()
    tool_registry = create_tool_registry(runner=runner, llm_client=llm_client)
    memory_store = _build_memory_store()
    return SessionOrchestrator(llm_client, tool_registry, memory_store, sse_queue)
