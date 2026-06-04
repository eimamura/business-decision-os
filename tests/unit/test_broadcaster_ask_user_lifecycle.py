from __future__ import annotations

"""Regression tests for the two-phase AskUser SSE lifecycle.

Phase 1: POST /messages → SSE receives ask_user_required + awaiting_input
Phase 2: POST /answer  → SSE on the SAME broadcaster receives done

Bug 1 regression: submit_ask_user_answer() must reuse the existing Broadcaster,
not create a new one, otherwise the phase-2 SSE stream never receives events.
"""

import asyncio
import json
from typing import Any
from uuid import UUID

import httpx
import pytest
from httpx import ASGITransport
from langgraph.errors import GraphInterrupt
from langgraph.types import Interrupt

import apps.api.routers.sessions as session_router
from apps.api.main import app
from apps.api.state import Broadcaster, broadcasters, sessions
from packages.agent.orchestrator import AgentRoute, SessionIntent, SessionResponse, SessionUserQuery


@pytest.fixture
async def client() -> httpx.AsyncClient:
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


class _AskUserStubOrchestrator:
    """Stub that simulates the two-phase ask_user lifecycle.

    run()             → emits ask_user_required, then raises GraphInterrupt
    answer_ask_user() → returns SessionResponse (simulates resume after answer)
    """

    def __init__(self, sse_queue: Broadcaster) -> None:
        self._sse_queue = sse_queue
        self._event_persister: Any = None

    async def run(self, session_id: UUID, query: SessionUserQuery) -> SessionResponse:
        # Wait until at least one subscriber is watching — guarantees no events are lost.
        while not self._sse_queue._subs:
            await asyncio.sleep(0.005)

        ask_user_id = "ask-test-001"
        await self._sse_queue.put({
            "type": "ask_user_required",
            "session_id": str(session_id),
            "ask_user_id": ask_user_id,
            "question": "What date range?",
            "suggestions": ["Last 30 days", "Q1 2025"],
            "timestamp": "2026-01-01T00:00:00Z",
        })
        raise GraphInterrupt([Interrupt(value={"ask_user_id": ask_user_id})])

    async def answer_ask_user(
        self, session_id: UUID, answer: str
    ) -> SessionResponse:
        # Wait until phase-2 SSE subscriber is watching.
        while not self._sse_queue._subs:
            await asyncio.sleep(0.005)

        intent = SessionIntent(
            category="domain_analysis",
            confidence=0.9,
            rationale="stub",
        )
        route = AgentRoute(
            mode="single_agent",
            agents=["data_engineer"],
            rationale="stub",
        )
        return SessionResponse(
            mode="single_agent",
            reply=f"Analyzed: {answer}",
            intent=intent,
            route=route,
        )


async def _collect_sse_events(
    client: httpx.AsyncClient,
    session_id: str,
    terminal_types: frozenset[str] | None = None,
) -> list[dict[str, Any]]:
    """Read SSE events until a terminal event type is received."""
    if terminal_types is None:
        terminal_types = frozenset({"done", "awaiting_input", "error"})
    events: list[dict[str, Any]] = []
    async with client.stream("GET", f"/api/v1/sessions/{session_id}/stream") as response:
        assert response.status_code == 200
        async for line in response.aiter_lines():
            if not line.startswith("data:"):
                continue
            event = json.loads(line[len("data:"):].strip())
            events.append(event)
            if event.get("type") in terminal_types:
                break
    return events


async def _allow_rate_limit(user_id: str) -> None:
    return None


async def test_phase1_sse_receives_ask_user_required_and_awaiting_input(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Phase 1: after POST /messages the SSE stream receives ask_user_required then awaiting_input."""

    def stub_get_orchestrator(queue: Broadcaster) -> _AskUserStubOrchestrator:
        return _AskUserStubOrchestrator(queue)

    monkeypatch.setattr(session_router, "get_orchestrator", stub_get_orchestrator)
    monkeypatch.setattr(session_router, "check_rate_limit", _allow_rate_limit)

    create_resp = await client.post("/api/v1/sessions", json={"goal": "analyze inventory"})
    assert create_resp.status_code == 200
    session_id = create_resp.json()["session_id"]

    send_resp = await client.post(
        f"/api/v1/sessions/{session_id}/messages",
        json={"content": "Analyze inventory"},
    )
    assert send_resp.status_code == 200

    events = await _collect_sse_events(client, session_id)
    event_types = [e["type"] for e in events]

    assert "ask_user_required" in event_types
    assert "awaiting_input" in event_types
    # The stream must terminate with awaiting_input (not "done")
    assert events[-1]["type"] == "awaiting_input"


async def test_phase2_sse_receives_done_via_same_broadcaster(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Phase 2 (Bug 1 regression): POST /answer must reuse the existing Broadcaster.

    If submit_ask_user_answer() creates a NEW Broadcaster instead of reusing the existing
    one, the phase-2 SSE stream subscribes to B1 while the background task emits to B2 —
    and the 'done' event is never received.
    """

    def stub_get_orchestrator(queue: Broadcaster) -> _AskUserStubOrchestrator:
        return _AskUserStubOrchestrator(queue)

    monkeypatch.setattr(session_router, "get_orchestrator", stub_get_orchestrator)
    monkeypatch.setattr(session_router, "check_rate_limit", _allow_rate_limit)

    create_resp = await client.post("/api/v1/sessions", json={"goal": "analyze inventory"})
    assert create_resp.status_code == 200
    session_id = create_resp.json()["session_id"]

    # Phase 1: send initial message, consume phase-1 SSE to completion
    await client.post(
        f"/api/v1/sessions/{session_id}/messages",
        json={"content": "Analyze inventory"},
    )
    phase1_events = await _collect_sse_events(client, session_id)
    phase1_types = [e["type"] for e in phase1_events]
    assert "ask_user_required" in phase1_types, "phase 1 must produce ask_user_required"

    # Phase 2: submit answer; open a NEW SSE stream before posting so we can capture events
    broadcaster_before = broadcasters.get(session_id)

    answer_resp = await client.post(
        f"/api/v1/sessions/{session_id}/answer",
        json={"answer": "Last 30 days"},
    )
    assert answer_resp.status_code == 202

    # The broadcaster must be the SAME object — Bug 1 regression assertion
    broadcaster_after = broadcasters.get(session_id)
    assert broadcaster_before is broadcaster_after, (
        "submit_ask_user_answer() replaced the Broadcaster. "
        "Phase-2 SSE stream subscribed to the old instance and will never receive 'done'."
    )

    # Verify the phase-2 SSE stream actually receives 'done'
    phase2_events = await _collect_sse_events(client, session_id, terminal_types=frozenset({"done"}))
    phase2_types = [e["type"] for e in phase2_events]
    assert "done" in phase2_types
    assert phase2_events[-1]["type"] == "done"
    assert "Last 30 days" in phase2_events[-1]["reply"]
