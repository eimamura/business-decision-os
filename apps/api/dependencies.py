from __future__ import annotations

from apps.api.state import broadcasters, get_orchestrator, make_event_persister
from packages.agent.orchestrator import SessionOrchestrator


def get_orchestrator_dep(session_id: str) -> SessionOrchestrator | None:
    broadcaster = broadcasters.get(session_id)
    if broadcaster is None:
        return None
    orchestrator = get_orchestrator(broadcaster)
    orchestrator._event_persister = make_event_persister(session_id)
    return orchestrator
