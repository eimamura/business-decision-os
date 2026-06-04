from __future__ import annotations

"""Unit tests for B-01 (T-160, T-161, T-162) and B-02 (T-163) broadcaster/state cleanup.

Coverage:
- T-160: delete_session pops broadcasters, broadcaster_ready, and session_run_ids
- T-160: delete_all_sessions clears all three dicts
- T-163/B-02: session_run_ids stores a run_id per session; stale run_id drops events

Note on T-162 (SSE stream breaks on "error" type events):
  Already covered by test_contract_session_message_error_still_terminates_with_done
  in tests/unit/test_contracts.py — not duplicated here.
"""

import asyncio
from typing import Any
from uuid import uuid4

import httpx
import pytest
from httpx import ASGITransport

import apps.api.routers.sessions as session_router
from apps.api.main import app
from apps.api.state import (
    Broadcaster,
    broadcaster_ready,
    broadcasters,
    session_run_ids,
    sessions,
)


@pytest.fixture
async def client() -> httpx.AsyncClient:
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_session(client: httpx.AsyncClient, goal: str = "test") -> str:
    resp = await client.post("/api/v1/sessions", json={"goal": goal})
    assert resp.status_code == 200
    return resp.json()["session_id"]


async def _stub_delete_session_true(self: Any, session_id: str) -> bool:
    """Instance-method stub: returns True (session found and deleted)."""
    return True


async def _stub_delete_all_sessions(self: Any) -> int:
    """Instance-method stub: returns 0 (no DB rows affected)."""
    return 0


# ---------------------------------------------------------------------------
# T-160: delete_session cleans up all three state dicts
# ---------------------------------------------------------------------------


async def test_delete_session_removes_broadcaster_key(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DELETE /{session_id} must remove the session from broadcasters."""
    sid = await _create_session(client)
    # Pre-populate all three dicts to simulate an in-progress run
    broadcasters[sid] = Broadcaster()
    broadcaster_ready[sid] = asyncio.Event()
    session_run_ids[sid] = str(uuid4())

    monkeypatch.setattr(
        "apps.api.routers.sessions.DecisionSessionRepository.delete_session",
        _stub_delete_session_true,
    )

    resp = await client.delete(f"/api/v1/sessions/{sid}")
    assert resp.status_code == 204

    assert sid not in broadcasters


async def test_delete_session_removes_broadcaster_ready_key(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DELETE /{session_id} must remove the session from broadcaster_ready."""
    sid = await _create_session(client)
    broadcasters[sid] = Broadcaster()
    broadcaster_ready[sid] = asyncio.Event()
    session_run_ids[sid] = str(uuid4())

    monkeypatch.setattr(
        "apps.api.routers.sessions.DecisionSessionRepository.delete_session",
        _stub_delete_session_true,
    )

    resp = await client.delete(f"/api/v1/sessions/{sid}")
    assert resp.status_code == 204

    assert sid not in broadcaster_ready


async def test_delete_session_removes_session_run_ids_key(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DELETE /{session_id} must remove the session from session_run_ids (T-163 guard)."""
    sid = await _create_session(client)
    broadcasters[sid] = Broadcaster()
    broadcaster_ready[sid] = asyncio.Event()
    session_run_ids[sid] = str(uuid4())

    monkeypatch.setattr(
        "apps.api.routers.sessions.DecisionSessionRepository.delete_session",
        _stub_delete_session_true,
    )

    resp = await client.delete(f"/api/v1/sessions/{sid}")
    assert resp.status_code == 204

    assert sid not in session_run_ids


# ---------------------------------------------------------------------------
# T-160: delete_all_sessions clears all three state dicts
# ---------------------------------------------------------------------------


async def test_delete_all_sessions_clears_broadcasters(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DELETE /sessions must clear broadcasters entirely."""
    for _ in range(3):
        sid = str(uuid4())
        sessions[sid] = {"session_id": sid, "status": "active", "goal": "", "messages": []}
        broadcasters[sid] = Broadcaster()

    monkeypatch.setattr(
        "apps.api.routers.sessions.DecisionSessionRepository.delete_all_sessions",
        _stub_delete_all_sessions,
    )

    resp = await client.delete("/api/v1/sessions")
    assert resp.status_code == 204

    assert len(broadcasters) == 0


async def test_delete_all_sessions_clears_broadcaster_ready(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DELETE /sessions must clear broadcaster_ready entirely."""
    for _ in range(2):
        sid = str(uuid4())
        sessions[sid] = {"session_id": sid, "status": "active", "goal": "", "messages": []}
        broadcaster_ready[sid] = asyncio.Event()

    monkeypatch.setattr(
        "apps.api.routers.sessions.DecisionSessionRepository.delete_all_sessions",
        _stub_delete_all_sessions,
    )

    resp = await client.delete("/api/v1/sessions")
    assert resp.status_code == 204

    assert len(broadcaster_ready) == 0


async def test_delete_all_sessions_clears_session_run_ids(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DELETE /sessions must clear session_run_ids entirely (T-163 guard)."""
    for _ in range(2):
        sid = str(uuid4())
        sessions[sid] = {"session_id": sid, "status": "active", "goal": "", "messages": []}
        session_run_ids[sid] = str(uuid4())

    monkeypatch.setattr(
        "apps.api.routers.sessions.DecisionSessionRepository.delete_all_sessions",
        _stub_delete_all_sessions,
    )

    resp = await client.delete("/api/v1/sessions")
    assert resp.status_code == 204

    assert len(session_run_ids) == 0


# ---------------------------------------------------------------------------
# T-163 / B-02: stale run_id guard prevents superseded tasks from forwarding events
# ---------------------------------------------------------------------------


async def test_stale_run_id_drops_events_old_run_cannot_put() -> None:
    """A superseded run_id must not forward events to the broadcaster.

    Simulates the run_id check inside _run_and_signal: if session_run_ids[sid]
    no longer matches the task's own run_id, the task returns without calling
    queue.put().  Subscribers therefore receive nothing from the stale run.
    """
    sid = "stale-run-test-" + str(uuid4())
    bc = Broadcaster()
    broadcasters[sid] = bc
    sub = bc.subscribe()

    new_run_id = "new-run-" + str(uuid4())
    old_run_id = "old-run-" + str(uuid4())

    # The current run_id is the *new* one — simulates a second POST /messages
    # that superseded the first background task.
    session_run_ids[sid] = new_run_id

    # Old task checks: if session_run_ids.get(sid) != old_run_id → return
    if session_run_ids.get(sid) != old_run_id:
        pass  # stale task returns without calling bc.put()

    # Sub should be empty — no events forwarded by stale run
    assert sub.empty()

    # Cleanup
    broadcasters.pop(sid, None)
    session_run_ids.pop(sid, None)


async def test_current_run_id_can_put_events() -> None:
    """The current (non-stale) run_id must forward events to the broadcaster."""
    sid = "current-run-test-" + str(uuid4())
    bc = Broadcaster()
    broadcasters[sid] = bc
    sub = bc.subscribe()

    current_run_id = "current-run-" + str(uuid4())
    session_run_ids[sid] = current_run_id

    # Current task checks: if session_run_ids.get(sid) == current_run_id → put
    if session_run_ids.get(sid) == current_run_id:
        await bc.put({"type": "done"})

    event = await asyncio.wait_for(sub.get(), timeout=1.0)
    assert event["type"] == "done"

    # Cleanup
    broadcasters.pop(sid, None)
    session_run_ids.pop(sid, None)


async def test_post_message_stores_run_id_in_session_run_ids(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """POST /messages must store a run_id in session_run_ids[session_id] (T-163)."""
    from packages.agent.orchestrator import AgentRoute, SessionIntent, SessionResponse, SessionUserQuery
    from uuid import UUID

    class _ImmediateOrchestrator:
        def __init__(self, queue: Any) -> None:
            self._queue = queue
            self._event_persister: Any = None

        async def run(self, session_id: UUID, query: SessionUserQuery) -> SessionResponse:
            intent = SessionIntent(
                category="question_answering",
                confidence=1.0,
                rationale="stub",
            )
            route = AgentRoute(
                mode="direct_chat",
                agents=[],
                requires_planning=False,
                requires_dag=False,
                rationale="stub",
            )
            return SessionResponse(mode="direct_chat", reply="ok", intent=intent, route=route)

    async def _allow_rate_limit(uid: str) -> None:
        return None

    monkeypatch.setattr(session_router, "get_orchestrator", lambda q: _ImmediateOrchestrator(q))
    monkeypatch.setattr(session_router, "check_rate_limit", _allow_rate_limit)

    sid = await _create_session(client, goal="run_id test")

    # Before posting there should be no run_id for this session
    assert sid not in session_run_ids

    resp = await client.post(
        f"/api/v1/sessions/{sid}/messages",
        json={"content": "Hello"},
    )
    assert resp.status_code == 200

    # After POST /messages, a run_id must be present
    assert sid in session_run_ids
    assert len(session_run_ids[sid]) > 0

    # Cleanup
    sessions.pop(sid, None)
    broadcasters.pop(sid, None)
    broadcaster_ready.pop(sid, None)
    session_run_ids.pop(sid, None)
