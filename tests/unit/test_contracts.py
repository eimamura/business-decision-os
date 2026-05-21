from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
import pytest
from httpx import ASGITransport

from apps.api.main import app
from apps.api.state import sessions, sse_queues
from packages.agent.llm import create_llm_client
from packages.persistence.approvals import ApprovalTransition


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
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    await queue.put({"type": "done", "reply": "ok", "session_id": sid})
    sessions[sid] = {"session_id": sid, "status": "active", "goal": "", "messages": []}
    sse_queues[sid] = queue

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
        sse_queues.pop(sid, None)

    assert len(events) > 0
    assert events[-1]["type"] == "done"


def test_contract_missing_anthropic_key_raises_runtime_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        create_llm_client()
