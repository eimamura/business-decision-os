from __future__ import annotations

from apps.api.state import get_orchestrator, sse_queues
from packages.agent.orchestrator import PhaseOrchestrator


def get_orchestrator_dep(session_id: str) -> PhaseOrchestrator | None:
    queue = sse_queues.get(session_id)
    if queue is None:
        return None
    return get_orchestrator(queue)
