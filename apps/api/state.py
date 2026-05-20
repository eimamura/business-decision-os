from __future__ import annotations

import os
from asyncio import Queue
from typing import Any

from packages.agent.job_runner import AcaJobsRunner, InProcessJobRunner
from packages.agent.llm import ClaudeClient
from packages.agent.orchestrator import PhaseOrchestrator
from packages.memory import StubMemoryStore
from packages.tools import create_tool_registry

sessions: dict[str, dict[str, Any]] = {}
sse_queues: dict[str, Queue[dict[str, Any]]] = {}


def _build_job_runner() -> AcaJobsRunner | InProcessJobRunner:
    backend = os.environ.get("JOB_RUNNER_BACKEND", "in_process").strip()
    if backend == "aca":
        return AcaJobsRunner()
    return InProcessJobRunner()


def get_orchestrator(sse_queue: Queue[dict[str, Any]]) -> PhaseOrchestrator:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set — add it to .env")
    llm_client = ClaudeClient(api_key=api_key)
    job_runner = _build_job_runner()
    tool_registry = create_tool_registry(job_runner=job_runner)
    memory_store = StubMemoryStore()
    return PhaseOrchestrator(llm_client, tool_registry, memory_store, sse_queue)
