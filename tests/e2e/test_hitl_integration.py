"""Integration tests for the HITL end-to-end flow.

These tests require a live server at API_BASE_URL (API_PORT env, Makefile
default 8002) and are marked @pytest.mark.e2e. A dedicated e2e session fails
loudly when the API is unreachable (see tests/e2e/conftest.py).
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest

from tests.e2e.conftest import API_BASE_URL

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_BASE = API_BASE_URL
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


async def _poll_session_status(
    client: httpx.AsyncClient,
    session_id: str,
    states: set[str],
    max_attempts: int = 30,
    delay: float = 1.0,
) -> dict[str, Any]:
    """Poll GET /api/v1/sessions/{session_id} until its status is in *states*.

    Asserts the canonical detail resource (DECISIONS.md 2026-08-24 vocabulary:
    'awaiting_input' at pause; 'completed'/'failed' terminal after execution).
    Regression coverage for D-028: the endpoint must reflect DB-persisted
    status writes (HITL pause / job terminal sync / approval decisions), not
    only the process-local copy created at POST time.
    """
    last_status: Any = None
    for _ in range(max_attempts):
        res = await client.get(
            _url(f"/api/v1/sessions/{session_id}"), headers=_DEV_HEADERS
        )
        if res.status_code == 200:
            data = res.json()
            last_status = data.get("status")
            if last_status in states:
                return data
        await asyncio.sleep(delay)
    pytest.fail(
        f"Session {session_id} never reached status {sorted(states)} after "
        f"{max_attempts} attempts (last observed: {last_status!r})"
    )


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
async def test_hitl_session_transitions_to_awaiting_input() -> None:
    """Create a session that triggers a hitl tool; assert status becomes awaiting_input.

    The approval pause reuses the ask_user pause vocabulary 'awaiting_input'
    (DECISIONS.md 2026-08-24); 'awaiting_approval' is forbidden by migration
    0014's CHECK constraint on decision_sessions.status.
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        session_id = await _create_session(client)

        # Send a message that should trigger the job_dispatch HITL tool
        await _post_message(client, session_id, _HITL_MESSAGE)

        # Poll until the session status is awaiting_input (or timeout)
        data = await _poll_session_status(client, session_id, {"awaiting_input"})

        assert data["status"] == "awaiting_input"
        assert data["session_id"] == session_id


@pytest.mark.e2e
async def test_hitl_approve_transitions_to_completed() -> None:
    """Approve a pending HITL approval; assert session transitions to completed."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        session_id = await _create_session(client)

        # Trigger the HITL tool
        await _post_message(client, session_id, _HITL_MESSAGE)

        # Wait for the approval-pause status awaiting_input (DECISIONS.md
        # 2026-08-24; migration 0014 CHECK constraint)
        await _poll_session_status(client, session_id, {"awaiting_input"})

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

        # The session should eventually transition to completed (terminal
        # sync after the linked job executes — job_executor D-026 write)
        session_data = await _poll_session_status(
            client, session_id, {"completed", "failed"}
        )

        assert session_data["status"] == "completed"


@pytest.mark.e2e
async def test_hitl_reject_transitions_to_failed() -> None:
    """Reject a pending HITL approval; assert session transitions to failed."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        session_id = await _create_session(client)

        # Trigger the HITL tool
        await _post_message(client, session_id, _HITL_MESSAGE)

        # Wait for the approval-pause status awaiting_input (DECISIONS.md
        # 2026-08-24; migration 0014 CHECK constraint)
        await _poll_session_status(client, session_id, {"awaiting_input"})

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
        session_data = await _poll_session_status(
            client, session_id, {"failed", "completed"}
        )

        assert session_data["status"] == "failed"
