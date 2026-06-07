from __future__ import annotations

import asyncio
import json
from typing import Any
from uuid import UUID

import httpx
import pytest
from httpx import ASGITransport

import apps.api.routers.decisions as decision_router
import apps.api.routers.sessions as session_router
from apps.api.main import app
from apps.api.state import Broadcaster, broadcasters, sessions
from packages.agent.model_registry import create_model_registry
from packages.agent.orchestrator import (
    AgentRoute,
    SessionIntent,
    SessionResponse,
    SessionUserQuery,
)
from packages.persistence.approvals import ApprovalTransition

EXPECTED_SESSION_STREAM_EVENTS = [
    "graph_node",
    "response_ready",
    "done",
]


@pytest.fixture
async def client():
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


async def test_contract_healthz_returns_200_ok(client: httpx.AsyncClient) -> None:
    response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_contract_session_create_retrieve_roundtrip(client: httpx.AsyncClient) -> None:
    create_response = await client.post("/api/v1/sessions", json={"goal": "test goal"})
    assert create_response.status_code == 200
    session_id = create_response.json()["session_id"]

    get_response = await client.get(f"/api/v1/sessions/{session_id}")
    assert get_response.status_code == 200
    assert get_response.json()["session_id"] == session_id


@pytest.mark.parametrize("terminal", ["approved", "rejected", "needs_revision", "expired"])
def test_contract_approval_terminal_state_rejects_transition(terminal: str) -> None:
    with pytest.raises(ValueError, match="Illegal transition"):
        ApprovalTransition(from_status=terminal, to_status="pending")  # type: ignore[arg-type]


async def test_contract_audit_log_delete_not_allowed(client: httpx.AsyncClient) -> None:
    response = await client.delete("/api/v1/audit")
    assert response.status_code == 405


def test_contract_audit_log_repo_has_no_delete_method() -> None:
    from packages.persistence.audit_log_repo import AuditLogRepository

    assert not hasattr(AuditLogRepository, "delete")


async def test_contract_sse_stream_terminates_with_done_event(client: httpx.AsyncClient) -> None:
    sid = "contract-sse-test"
    broadcaster = Broadcaster()
    sessions[sid] = {"session_id": sid, "status": "active", "goal": "", "messages": []}
    broadcasters[sid] = broadcaster

    async def _inject() -> None:
        while not broadcaster._subs:  # wait for stream subscriber to attach
            await asyncio.sleep(0.005)
        await broadcaster.put({"type": "done", "reply": "ok", "session_id": sid})

    asyncio.create_task(_inject())

    events: list[dict[str, Any]] = []
    try:
        async with client.stream("GET", f"/api/v1/sessions/{sid}/stream") as response:
            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue
                event = json.loads(line[len("data:"):].strip())
                events.append(event)
                if event.get("type") == "done":
                    break
    finally:
        sessions.pop(sid, None)
        broadcasters.pop(sid, None)

    assert len(events) > 0
    assert events[-1]["type"] == "done"


async def _read_session_stream(
    client: httpx.AsyncClient, session_id: str
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    async with client.stream("GET", f"/api/v1/sessions/{session_id}/stream") as response:
        assert response.status_code == 200
        async for line in response.aiter_lines():
            if not line.startswith("data:"):
                continue
            event = json.loads(line[len("data:"):].strip())
            events.append(event)
            if event.get("type") == "done":
                break
    return events


async def test_contract_session_message_uses_user_query_and_streams_new_taxonomy(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}
    reply = "Inventory is stable for the requested SKU."

    class StubOrchestrator:
        def __init__(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
            self.queue = queue

        async def run(self, session_id: UUID, query: SessionUserQuery) -> SessionResponse:
            captured["session_id"] = session_id
            captured["query"] = query
            while not self.queue._subs:  # wait for stream subscriber to attach
                await asyncio.sleep(0.005)
            await self.queue.put({"type": "graph_node", "event": "start", "node_name": "run_direct_chat"})
            await self.queue.put({"type": "response_ready"})
            intent = SessionIntent(
                category="question_answering",
                confidence=0.99,
                rationale="stubbed contract test",
            )
            route = AgentRoute(
                mode="direct_chat",
                agents=[],
                requires_planning=False,
                requires_dag=False,
                rationale="stubbed contract test",
            )
            return SessionResponse(mode="direct_chat", reply=reply, intent=intent, route=route)

    def stub_get_orchestrator(
        queue: asyncio.Queue[dict[str, Any]],
    ) -> StubOrchestrator:
        return StubOrchestrator(queue)

    async def allow_request(user_id: str) -> None:
        return None

    monkeypatch.setattr(session_router, "get_orchestrator", stub_get_orchestrator)
    monkeypatch.setattr(session_router, "check_rate_limit", allow_request)

    create_response = await client.post("/api/v1/sessions", json={"goal": "contract"})
    assert create_response.status_code == 200
    session_id = create_response.json()["session_id"]

    send_response = await client.post(
        f"/api/v1/sessions/{session_id}/messages",
        json={"content": "How is inventory for SKU-1?"},
    )
    assert send_response.status_code == 200

    events = await _read_session_stream(client, session_id)
    event_types = [event["type"] for event in events]

    assert isinstance(captured["query"], SessionUserQuery)
    assert captured["query"].text == "How is inventory for SKU-1?"
    assert captured["session_id"] == UUID(session_id)
    assert event_types == EXPECTED_SESSION_STREAM_EVENTS
    assert events[-1]["reply"] == reply

    messages = sessions[session_id]["messages"]
    assert messages[-1]["role"] == "assistant"
    assert messages[-1]["content"] == reply


async def test_contract_session_message_error_still_terminates_with_done(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingOrchestrator:
        def __init__(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
            self.queue = queue

        async def run(self, session_id: UUID, query: SessionUserQuery) -> SessionResponse:
            while not self.queue._subs:  # wait for stream subscriber to attach
                await asyncio.sleep(0.005)
            raise RuntimeError("stub failure")

    def stub_get_orchestrator(
        queue: asyncio.Queue[dict[str, Any]],
    ) -> FailingOrchestrator:
        return FailingOrchestrator(queue)

    async def allow_request(user_id: str) -> None:
        return None

    monkeypatch.setattr(session_router, "get_orchestrator", stub_get_orchestrator)
    monkeypatch.setattr(session_router, "check_rate_limit", allow_request)

    create_response = await client.post("/api/v1/sessions", json={"goal": "contract"})
    assert create_response.status_code == 200
    session_id = create_response.json()["session_id"]

    send_response = await client.post(
        f"/api/v1/sessions/{session_id}/messages",
        json={"content": "Trigger a controlled failure"},
    )
    assert send_response.status_code == 200

    # With T-162, the SSE stream breaks on "error" so the stream terminates
    # as soon as the error event arrives.  "done" is still enqueued by the
    # finally block in _run_and_signal but the consumer has already closed.
    events: list[dict[str, Any]] = []
    async with client.stream("GET", f"/api/v1/sessions/{session_id}/stream") as response:
        assert response.status_code == 200
        async for line in response.aiter_lines():
            if not line.startswith("data:"):
                continue
            event = json.loads(line[len("data:"):].strip())
            events.append(event)
            # Stream closes on either "error" or "done" (T-162).
            if event.get("type") in ("error", "done"):
                break

    event_types = [event["type"] for event in events]

    assert "error" in event_types
    assert events[-1]["type"] == "error"
    assert events[-1]["code"] == "orchestration_failed"


async def test_contract_decisions_streams_new_taxonomy_and_done_reply(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}
    reply = "Run the replenishment plan with the lower stockout risk."

    class StubOrchestrator:
        def __init__(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
            self.queue = queue

        async def run(self, session_id: UUID, query: SessionUserQuery) -> SessionResponse:
            captured["session_id"] = session_id
            captured["query"] = query
            await asyncio.sleep(0.05)  # yield so stream subscriber can attach
            await self.queue.put({"type": "graph_node", "event": "start", "node_name": "synthesize"})
            await self.queue.put({"type": "response_ready"})
            intent = SessionIntent(
                category="decision_support",
                confidence=0.99,
                rationale="stubbed contract test",
                goal_text=query.text,
            )
            route = AgentRoute(
                mode="planned_execution",
                agents=["replenishment"],
                requires_planning=True,
                requires_dag=False,
                rationale="stubbed contract test",
            )
            return SessionResponse(
                mode="planned_execution",
                reply=reply,
                intent=intent,
                route=route,
                risk_level="low",
                requires_approval=False,
            )

    def stub_get_orchestrator(
        queue: asyncio.Queue[dict[str, Any]],
    ) -> StubOrchestrator:
        return StubOrchestrator(queue)

    monkeypatch.setenv("JOB_RUNNER_BACKEND", "in_process")
    monkeypatch.setattr(decision_router, "get_orchestrator", stub_get_orchestrator)

    events: list[dict[str, Any]] = []
    async with client.stream(
        "POST",
        "/api/v1/decisions",
        json={"goal": "Optimize replenishment for SKU-1"},
        headers={"Accept": "text/event-stream"},
    ) as response:
        assert response.status_code == 200
        async for line in response.aiter_lines():
            if not line.startswith("data:"):
                continue
            event = json.loads(line[len("data:"):].strip())
            events.append(event)
            if event.get("type") == "done":
                break

    event_types = [event["type"] for event in events]

    assert isinstance(captured["query"], SessionUserQuery)
    assert captured["query"].text == "Optimize replenishment for SKU-1"
    assert isinstance(captured["session_id"], UUID)
    assert event_types == EXPECTED_SESSION_STREAM_EVENTS
    assert events[-1]["reply"] == reply


def test_contract_missing_anthropic_key_raises_runtime_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        create_model_registry()
