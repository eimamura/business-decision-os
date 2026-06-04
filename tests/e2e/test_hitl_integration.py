"""Integration tests for the HITL end-to-end flow.

These tests require a live server and are marked @pytest.mark.e2e.
They are skipped in unit/CI runs when localhost:8000 is not reachable
(see tests/e2e/conftest.py for the auto-skip logic).
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable

import httpx
import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_BASE = "http://localhost:8000"
_DEV_HEADERS = {"X-Dev-User": "dev-user", "Content-Type": "application/json"}

# Message designed to trigger the job_dispatch (HITL) tool via the agent.
# The agent must call job_dispatch when asked to run a simulation.
_HITL_MESSAGE = (
    "Run a demand simulation for SKU-001 with a 30-day horizon "
    "and report the projected stockout risk."
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _url(path: str) -> str:
    return f"{_BASE}{path}"


async def _poll_until(
    client: httpx.AsyncClient,
    url: str,
    condition_fn: Callable[[Any], bool],
    max_attempts: int = 20,
    delay: float = 0.5,
) -> Any:
    """Poll *url* every *delay* seconds until *condition_fn* returns True.

    Returns the response JSON on success; calls pytest.fail() on timeout.
    """
    for _ in range(max_attempts):
        res = await client.get(url, headers=_DEV_HEADERS)
        if res.status_code == 200 and condition_fn(res.json()):
            return res.json()
        await asyncio.sleep(delay)
    pytest.fail(f"Condition never met at {url} after {max_attempts} attempts")


async def _create_session(client: httpx.AsyncClient) -> str:
    """POST /api/v1/sessions and return the new session_id."""
    res = await client.post(
        _url("/api/v1/sessions"),
        json={"goal": "HITL integration test"},
        headers=_DEV_HEADERS,
    )
    assert res.status_code == 200, f"create_session failed: {res.status_code} {res.text}"
    data = res.json()
    assert "session_id" in data
    return data["session_id"]


async def _post_message(client: httpx.AsyncClient, session_id: str, content: str) -> None:
    """POST a message to the session and wait for the agent to start processing."""
    res = await client.post(
        _url(f"/api/v1/sessions/{session_id}/messages"),
        json={"content": content},
        headers=_DEV_HEADERS,
    )
    assert res.status_code == 200, f"post_message failed: {res.status_code} {res.text}"


async def _find_pending_approval(
    client: httpx.AsyncClient,
    session_id: str,
    max_attempts: int = 20,
    delay: float = 0.5,
) -> dict[str, Any]:
    """Poll GET /api/v1/approvals?status=pending until an approval for *session_id* appears."""
    for _ in range(max_attempts):
        res = await client.get(
            _url("/api/v1/approvals"),
            params={"status": "pending"},
            headers=_DEV_HEADERS,
        )
        if res.status_code == 200:
            approvals = res.json()
            if isinstance(approvals, list):
                for a in approvals:
                    if str(a.get("session_id")) == session_id:
                        return a
        await asyncio.sleep(delay)
    pytest.fail(
        f"No pending approval found for session {session_id} after {max_attempts} attempts"
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.e2e
async def test_hitl_session_transitions_to_awaiting_approval() -> None:
    """Create a session that triggers a hitl tool; assert status becomes awaiting_approval."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        session_id = await _create_session(client)

        # Send a message that should trigger the job_dispatch HITL tool
        await _post_message(client, session_id, _HITL_MESSAGE)

        # Poll until the session status is awaiting_approval (or timeout)
        data = await _poll_until(
            client,
            _url(f"/api/v1/sessions/{session_id}"),
            condition_fn=lambda d: d.get("status") == "awaiting_approval",
            max_attempts=30,
            delay=1.0,
        )

        assert data["status"] == "awaiting_approval"
        assert data["session_id"] == session_id


@pytest.mark.e2e
async def test_hitl_approve_transitions_to_completed() -> None:
    """Approve a pending HITL approval; assert session transitions to completed."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        session_id = await _create_session(client)

        # Trigger the HITL tool
        await _post_message(client, session_id, _HITL_MESSAGE)

        # Wait for awaiting_approval status
        await _poll_until(
            client,
            _url(f"/api/v1/sessions/{session_id}"),
            condition_fn=lambda d: d.get("status") == "awaiting_approval",
            max_attempts=30,
            delay=1.0,
        )

        # Find the pending approval
        approval = await _find_pending_approval(client, session_id)
        approval_id = str(approval["id"])

        # Submit the approve decision
        res = await client.post(
            _url(f"/api/v1/approvals/{approval_id}/decision"),
            json={"decision": "approved"},
            headers=_DEV_HEADERS,
        )
        assert res.status_code == 200, (
            f"POST decision failed: {res.status_code} {res.text}"
        )

        # The approval record must reflect the approved status
        decision_data = res.json()
        assert decision_data.get("status") == "approved"

        # The session should eventually transition to completed
        session_data = await _poll_until(
            client,
            _url(f"/api/v1/sessions/{session_id}"),
            condition_fn=lambda d: d.get("status") in {"completed", "failed"},
            max_attempts=30,
            delay=1.0,
        )

        assert session_data["status"] == "completed"


@pytest.mark.e2e
async def test_hitl_reject_transitions_to_failed() -> None:
    """Reject a pending HITL approval; assert session transitions to failed."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        session_id = await _create_session(client)

        # Trigger the HITL tool
        await _post_message(client, session_id, _HITL_MESSAGE)

        # Wait for awaiting_approval status
        await _poll_until(
            client,
            _url(f"/api/v1/sessions/{session_id}"),
            condition_fn=lambda d: d.get("status") == "awaiting_approval",
            max_attempts=30,
            delay=1.0,
        )

        # Find the pending approval
        approval = await _find_pending_approval(client, session_id)
        approval_id = str(approval["id"])

        # Submit the reject decision
        res = await client.post(
            _url(f"/api/v1/approvals/{approval_id}/decision"),
            json={"decision": "rejected", "reason": "Integration test reject"},
            headers=_DEV_HEADERS,
        )
        assert res.status_code == 200, (
            f"POST decision failed: {res.status_code} {res.text}"
        )

        decision_data = res.json()
        assert decision_data.get("status") == "rejected"

        # The session should transition to failed after rejection
        session_data = await _poll_until(
            client,
            _url(f"/api/v1/sessions/{session_id}"),
            condition_fn=lambda d: d.get("status") in {"failed", "completed"},
            max_attempts=20,
            delay=1.0,
        )

        assert session_data["status"] == "failed"
