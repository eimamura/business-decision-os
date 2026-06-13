from __future__ import annotations

"""Unit tests for T-631: chart-fence SSE emission in _run_and_signal().

Verifies that when extract_chart_specs() returns one or more ChartSpec dicts,
_run_and_signal() emits a text_delta SSE event for each chart fence whose
'delta' field contains the chart fence string (` ```chart\n...\n``` `).

Strategy: invoke POST /messages with a stub orchestrator that returns a
SessionResponse whose agent_results contain chartable tool outputs.  Patch
extract_chart_specs at its source module (packages.agent.chart_extractor) so
the patch is active when the background task's local import resolves it.
Subscribe to the Broadcaster before POST so no events are missed via the
replay buffer, then assert events inside the same patch context so the mock
remains active for the full duration of the background task.
"""

import asyncio
import json
from typing import Any, AsyncGenerator
from unittest.mock import patch
from uuid import UUID, uuid4 as _uuid4

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
from packages.agent.orchestrator import (
    AgentRoute,
    SessionIntent,
    SessionResponse,
    SessionUserQuery,
    SpecialistResult,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def client() -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


# ---------------------------------------------------------------------------
# Stub orchestrator that returns a SessionResponse with agent_results
# ---------------------------------------------------------------------------


class _ChartStubOrchestrator:
    """Stub orchestrator that returns a fixed SessionResponse immediately.

    Sets up a minimal agent_results payload so that extract_chart_specs
    (patched in the test) can receive it.  Waits for at least one SSE
    subscriber before returning to avoid event loss.
    """

    def __init__(self, sse_queue: Broadcaster) -> None:
        self._sse_queue = sse_queue
        self._event_persister: Any = None

    async def run(self, session_id: UUID, query: SessionUserQuery) -> SessionResponse:
        # Wait until at least one SSE subscriber is watching to avoid event loss.
        while not self._sse_queue._subs:
            await asyncio.sleep(0.005)

        intent = SessionIntent(
            category="domain_analysis",
            confidence=1.0,
            rationale="stub",
        )
        route = AgentRoute(
            mode="single_agent",
            agents=["data_engineer"],
            rationale="stub",
        )
        return SessionResponse(
            mode="single_agent",
            reply="Here is the analysis.",
            intent=intent,
            route=route,
            agent_results={
                "data_engineer": SpecialistResult(
                    task_id=_uuid4(),
                    output={
                        "text": "Analysis complete.",
                        "specialist": "data_engineer",
                        "tool_results": {
                            "list_stockout_risk": {
                                "items": [{"sku_code": "SKU-001", "days_of_cover": 2.1}],
                                "count": 1,
                                "missing_data": [],
                            },
                        },
                    },
                    tool_calls_made=[],
                    status="completed",
                ),
            },
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _allow_rate_limit(uid: str) -> None:
    """Stub that bypasses the rate limiter."""
    return None


async def _create_session(client: httpx.AsyncClient, goal: str = "chart test") -> str:
    resp = await client.post("/api/v1/sessions", json={"goal": goal})
    assert resp.status_code == 200
    return resp.json()["session_id"]


def _cleanup(sid: str) -> None:
    sessions.pop(sid, None)
    broadcasters.pop(sid, None)
    broadcaster_ready.pop(sid, None)
    session_run_ids.pop(sid, None)


async def _collect_until_done(
    bc: Broadcaster, timeout: float = 5.0
) -> list[dict[str, Any]]:
    """Subscribe to *bc* and drain events until a terminal event arrives."""
    sub = bc.subscribe()
    events: list[dict[str, Any]] = []
    deadline = asyncio.get_event_loop().time() + timeout
    try:
        while True:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                pytest.fail("Timed out waiting for 'done' event from broadcaster")
            try:
                event = await asyncio.wait_for(sub.get(), timeout=remaining)
            except asyncio.TimeoutError:
                pytest.fail("Timed out waiting for 'done' event from broadcaster")
            events.append(event)
            if event.get("type") in {"done", "awaiting_input", "error"}:
                break
    finally:
        bc.unsubscribe(sub)
    return events


# ---------------------------------------------------------------------------
# Tests
#
# IMPORTANT: The patch must stay active while awaiting broadcaster events
# because _run_and_signal() runs as an asyncio background task that does
# a local import of extract_chart_specs.  Exiting the 'with patch(...)' block
# before the task runs would restore the real function.
# Therefore the pattern in every test is:
#   1. Pre-subscribe to the broadcaster so replay buffer captures all events.
#   2. POST /messages while the patch is active.
#   3. Await events (still inside 'with patch(...)') until 'done'.
# ---------------------------------------------------------------------------


async def test_chart_fence_emits_text_delta_event_with_single_spec(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When extract_chart_specs returns one spec, queue receives a text_delta event."""
    stub_spec = {
        "type": "bar",
        "title": "Stockout Risk — Days of Cover by SKU",
        "xKey": "sku_code",
        "series": [{"dataKey": "days_of_cover", "name": "Days of Cover", "color": "#ef4444"}],
        "data": [{"sku_code": "SKU-001", "days_of_cover": 2.1}],
    }

    monkeypatch.setattr(session_router, "get_orchestrator", lambda q: _ChartStubOrchestrator(q))
    monkeypatch.setattr(session_router, "check_rate_limit", _allow_rate_limit)

    sid = await _create_session(client)

    # Pre-create the Broadcaster so we can subscribe before the POST fires the task.
    bc = Broadcaster()
    broadcasters[sid] = bc
    sub = bc.subscribe()

    with patch("packages.agent.chart_extractor.extract_chart_specs", return_value=[stub_spec]):
        resp = await client.post(
            f"/api/v1/sessions/{sid}/messages",
            json={"content": "Show me stockout risk"},
        )
        assert resp.status_code == 200

        # Drain events while patch is still active (background task may still run).
        events: list[dict[str, Any]] = []
        deadline = asyncio.get_event_loop().time() + 5.0
        while True:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                pytest.fail("Timed out waiting for 'done' event from broadcaster")
            try:
                event = await asyncio.wait_for(sub.get(), timeout=remaining)
            except asyncio.TimeoutError:
                pytest.fail("Timed out waiting for 'done' event from broadcaster")
            events.append(event)
            if event.get("type") in {"done", "awaiting_input", "error"}:
                break

    bc.unsubscribe(sub)
    _cleanup(sid)

    text_delta_events = [e for e in events if e.get("type") == "text_delta"]
    assert len(text_delta_events) >= 1, (
        f"Expected at least one text_delta event; got event types: "
        f"{[e.get('type') for e in events]}"
    )


async def test_chart_fence_text_delta_delta_field_contains_chart_fence(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The delta field of the text_delta event must contain the chart fence string."""
    stub_spec = {
        "type": "bar",
        "title": "Stockout Risk",
        "xKey": "sku_code",
        "series": [],
        "data": [{"sku_code": "SKU-001", "days_of_cover": 2.1}],
    }
    expected_json = json.dumps(stub_spec, ensure_ascii=False)
    expected_fence = "\n\n```chart\n" + expected_json + "\n```\n"

    monkeypatch.setattr(session_router, "get_orchestrator", lambda q: _ChartStubOrchestrator(q))
    monkeypatch.setattr(session_router, "check_rate_limit", _allow_rate_limit)

    sid = await _create_session(client)

    bc = Broadcaster()
    broadcasters[sid] = bc
    sub = bc.subscribe()

    with patch("packages.agent.chart_extractor.extract_chart_specs", return_value=[stub_spec]):
        resp = await client.post(
            f"/api/v1/sessions/{sid}/messages",
            json={"content": "Show me stockout risk"},
        )
        assert resp.status_code == 200

        events: list[dict[str, Any]] = []
        deadline = asyncio.get_event_loop().time() + 5.0
        while True:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                pytest.fail("Timed out waiting for 'done' event from broadcaster")
            try:
                event = await asyncio.wait_for(sub.get(), timeout=remaining)
            except asyncio.TimeoutError:
                pytest.fail("Timed out waiting for 'done' event from broadcaster")
            events.append(event)
            if event.get("type") in {"done", "awaiting_input", "error"}:
                break

    bc.unsubscribe(sub)
    _cleanup(sid)

    text_delta_events = [e for e in events if e.get("type") == "text_delta"]
    assert len(text_delta_events) >= 1

    delta_values = [e["delta"] for e in text_delta_events]
    assert expected_fence in delta_values, (
        f"Expected chart fence not found in delta values.\n"
        f"Expected: {expected_fence!r}\n"
        f"Got deltas: {delta_values!r}"
    )


async def test_chart_fence_emits_one_text_delta_per_spec(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When extract_chart_specs returns N specs, exactly N text_delta events are emitted."""
    stub_specs = [
        {
            "type": "bar",
            "title": "Stockout Risk",
            "xKey": "sku_code",
            "series": [],
            "data": [{"sku_code": "SKU-001", "days_of_cover": 2.1}],
        },
        {
            "type": "line",
            "title": "Demand Trend",
            "xKey": "period",
            "series": [],
            "data": [
                {"period": "2026-05", "quantity": 100.0},
                {"period": "2026-06", "quantity": 110.0},
            ],
        },
    ]

    monkeypatch.setattr(session_router, "get_orchestrator", lambda q: _ChartStubOrchestrator(q))
    monkeypatch.setattr(session_router, "check_rate_limit", _allow_rate_limit)

    sid = await _create_session(client)

    bc = Broadcaster()
    broadcasters[sid] = bc
    sub = bc.subscribe()

    with patch("packages.agent.chart_extractor.extract_chart_specs", return_value=stub_specs):
        resp = await client.post(
            f"/api/v1/sessions/{sid}/messages",
            json={"content": "Show me charts"},
        )
        assert resp.status_code == 200

        events: list[dict[str, Any]] = []
        deadline = asyncio.get_event_loop().time() + 5.0
        while True:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                pytest.fail("Timed out waiting for 'done' event from broadcaster")
            try:
                event = await asyncio.wait_for(sub.get(), timeout=remaining)
            except asyncio.TimeoutError:
                pytest.fail("Timed out waiting for 'done' event from broadcaster")
            events.append(event)
            if event.get("type") in {"done", "awaiting_input", "error"}:
                break

    bc.unsubscribe(sub)
    _cleanup(sid)

    text_delta_events = [e for e in events if e.get("type") == "text_delta"]
    assert len(text_delta_events) == len(stub_specs), (
        f"Expected {len(stub_specs)} text_delta events (one per spec), "
        f"got {len(text_delta_events)}. Event types: {[e.get('type') for e in events]}"
    )


async def test_chart_fence_no_text_delta_when_extract_returns_empty(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When extract_chart_specs returns [], no text_delta events are emitted."""
    monkeypatch.setattr(session_router, "get_orchestrator", lambda q: _ChartStubOrchestrator(q))
    monkeypatch.setattr(session_router, "check_rate_limit", _allow_rate_limit)

    sid = await _create_session(client)

    bc = Broadcaster()
    broadcasters[sid] = bc
    sub = bc.subscribe()

    with patch("packages.agent.chart_extractor.extract_chart_specs", return_value=[]):
        resp = await client.post(
            f"/api/v1/sessions/{sid}/messages",
            json={"content": "No charts please"},
        )
        assert resp.status_code == 200

        events: list[dict[str, Any]] = []
        deadline = asyncio.get_event_loop().time() + 5.0
        while True:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                pytest.fail("Timed out waiting for 'done' event from broadcaster")
            try:
                event = await asyncio.wait_for(sub.get(), timeout=remaining)
            except asyncio.TimeoutError:
                pytest.fail("Timed out waiting for 'done' event from broadcaster")
            events.append(event)
            if event.get("type") in {"done", "awaiting_input", "error"}:
                break

    bc.unsubscribe(sub)
    _cleanup(sid)

    text_delta_events = [e for e in events if e.get("type") == "text_delta"]
    assert text_delta_events == [], (
        f"Expected no text_delta events when extract_chart_specs returns []; "
        f"got {len(text_delta_events)}"
    )


async def test_chart_fence_text_delta_event_has_session_id_field(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The text_delta event emitted for a chart fence must include the session_id field."""
    stub_spec = {"type": "bar", "title": "T", "xKey": "x", "series": [], "data": [{"x": 1}]}

    monkeypatch.setattr(session_router, "get_orchestrator", lambda q: _ChartStubOrchestrator(q))
    monkeypatch.setattr(session_router, "check_rate_limit", _allow_rate_limit)

    sid = await _create_session(client)

    bc = Broadcaster()
    broadcasters[sid] = bc
    sub = bc.subscribe()

    with patch("packages.agent.chart_extractor.extract_chart_specs", return_value=[stub_spec]):
        resp = await client.post(
            f"/api/v1/sessions/{sid}/messages",
            json={"content": "Check session_id field"},
        )
        assert resp.status_code == 200

        events: list[dict[str, Any]] = []
        deadline = asyncio.get_event_loop().time() + 5.0
        while True:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                pytest.fail("Timed out waiting for 'done' event")
            try:
                event = await asyncio.wait_for(sub.get(), timeout=remaining)
            except asyncio.TimeoutError:
                pytest.fail("Timed out waiting for 'done' event")
            events.append(event)
            if event.get("type") in {"done", "awaiting_input", "error"}:
                break

    bc.unsubscribe(sub)
    _cleanup(sid)

    text_delta_events = [e for e in events if e.get("type") == "text_delta"]
    assert len(text_delta_events) >= 1
    assert text_delta_events[0]["session_id"] == sid
