from __future__ import annotations

import os
from asyncio import Queue
from typing import Any

from packages.agent.llm import ClaudeClient, StubClaudeClient
from packages.agent.orchestrator import PhaseOrchestrator
from packages.memory import StubMemoryStore
from packages.tools import create_tool_registry

sessions: dict[str, dict[str, Any]] = {}
sse_queues: dict[str, Queue[dict[str, Any]]] = {}


def get_orchestrator(sse_queue: Queue[dict[str, Any]]) -> PhaseOrchestrator:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    llm_client: ClaudeClient | StubClaudeClient
    if api_key:
        llm_client = ClaudeClient(api_key=api_key)
    else:
        llm_client = StubClaudeClient()
    tool_registry = create_tool_registry()
    memory_store = StubMemoryStore()
    return PhaseOrchestrator(llm_client, tool_registry, memory_store, sse_queue)
