from __future__ import annotations

from apps.api.state import get_orchestrator, sse_queues
from packages.agent.orchestrator import SessionOrchestrator


def get_orchestrator_dep(session_id: str) -> SessionOrchestrator | None:
    queue = sse_queues.get(session_id)
    if queue is None:
        return None
    return get_orchestrator(queue)
