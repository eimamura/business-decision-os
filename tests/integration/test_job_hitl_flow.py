"""Integration tests for the job-dispatch HITL flow.

These tests require a live server on localhost:8000.
They are marked @pytest.mark.e2e and auto-skipped when the server is not
reachable (see tests/e2e/conftest.py).

Flow under test:
  POST /api/v1/sessions
  POST /api/v1/sessions/{id}/messages  (message that triggers job_dispatch)
  GET  /api/v1/approvals?status=pending  → find pending approval
  GET  /api/v1/jobs?status=pending_approval  → verify job row was created
  POST /api/v1/approvals/{id}/decision  → approve
  GET  /api/v1/jobs/{job_id}  → verify job transitions to completed + has files
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

# Prompt that reliably triggers job_dispatch in the agent
_DISPATCH_MESSAGE = (
    "Please run an inventory optimization simulation for SKU-A42 "
    "with a 14-day planning horizon so we can evaluate reorder timing."
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
    res = await client.post(
        _url("/api/v1/sessions"),
        json={"goal": "Job HITL flow integration test"},
        headers=_DEV_HEADERS,
    )
    assert res.status_code == 200, f"create_session: {res.status_code} {res.text}"
    data = res.json()
    return data["session_id"]


async def _post_message(client: httpx.AsyncClient, session_id: str, content: str) -> None:
    res = await client.post(
        _url(f"/api/v1/sessions/{session_id}/messages"),
        json={"content": content},
        headers=_DEV_HEADERS,
    )
    assert res.status_code == 200, f"post_message: {res.status_code} {res.text}"


async def _find_pending_approval_for_session(
    client: httpx.AsyncClient,
    session_id: str,
    max_attempts: int = 30,
    delay: float = 1.0,
) -> dict[str, Any]:
    """Poll GET /api/v1/approvals?status=pending for an approval linked to session_id."""
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
        f"No pending approval for session {session_id} after {max_attempts} attempts"
    )


async def _find_job_for_approval(
    client: httpx.AsyncClient,
    approval_id: str,
    max_attempts: int = 20,
    delay: float = 0.5,
) -> dict[str, Any]:
    """Poll GET /api/v1/jobs?status=pending_approval for a job with matching approval_id."""
    for _ in range(max_attempts):
        res = await client.get(
            _url("/api/v1/jobs"),
            params={"status": "pending_approval"},
            headers=_DEV_HEADERS,
        )
        if res.status_code == 200:
            payload = res.json()
            items = payload.get("items", []) if isinstance(payload, dict) else payload
            if isinstance(items, list):
                for job in items:
                    if str(job.get("approval_id")) == approval_id:
                        return job
        await asyncio.sleep(delay)
    pytest.fail(
        f"No job with approval_id={approval_id} in pending_approval status "
        f"after {max_attempts} attempts"
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.e2e
async def test_job_dispatch_creates_pending_job() -> None:
    """Triggering the job_dispatch tool creates a job row with status pending_approval."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        session_id = await _create_session(client)

        # Send a message that should trigger job_dispatch
        await _post_message(client, session_id, _DISPATCH_MESSAGE)

        # Wait until the session transitions to awaiting_approval
        await _poll_until(
            client,
            _url(f"/api/v1/sessions/{session_id}"),
            condition_fn=lambda d: d.get("status") == "awaiting_approval",
            max_attempts=30,
            delay=1.0,
        )

        # Find the pending approval linked to this session
        approval = await _find_pending_approval_for_session(client, session_id)
        approval_id = str(approval["id"])

        # The jobs endpoint must return a job linked to this approval
        job = await _find_job_for_approval(client, approval_id)

        assert job["status"] == "pending_approval"
        assert str(job.get("approval_id")) == approval_id
        assert job.get("job_type") is not None
        assert job.get("id") is not None


@pytest.mark.e2e
async def test_job_approve_executes_and_completes() -> None:
    """Approving the pending job triggers execution; the job must reach 'completed' status
    and have at least one file row attached."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        session_id = await _create_session(client)

        # Trigger job_dispatch
        await _post_message(client, session_id, _DISPATCH_MESSAGE)

        # Wait for awaiting_approval
        await _poll_until(
            client,
            _url(f"/api/v1/sessions/{session_id}"),
            condition_fn=lambda d: d.get("status") == "awaiting_approval",
            max_attempts=30,
            delay=1.0,
        )

        # Get the pending approval for this session
        approval = await _find_pending_approval_for_session(client, session_id)
        approval_id = str(approval["id"])

        # Confirm there is a pending job
        job = await _find_job_for_approval(client, approval_id)
        job_id = str(job["id"])
        assert job["status"] == "pending_approval"

        # Submit the approve decision
        res = await client.post(
            _url(f"/api/v1/approvals/{approval_id}/decision"),
            json={"decision": "approved"},
            headers=_DEV_HEADERS,
        )
        assert res.status_code == 200, (
            f"POST decision failed: {res.status_code} {res.text}"
        )

        # Wait until the job transitions to completed (or failed as a fallback)
        job_data = await _poll_until(
            client,
            _url(f"/api/v1/jobs/{job_id}"),
            condition_fn=lambda d: d.get("status") in {"completed", "failed"},
            max_attempts=40,
            delay=1.5,
        )

        assert job_data["status"] == "completed", (
            f"Expected job status 'completed', got '{job_data.get('status')}'"
        )

        # The completed job must have at least one generated file
        generated_files = job_data.get("generated_files", [])
        assert isinstance(generated_files, list)
        assert len(generated_files) >= 1, (
            "Expected at least one job_files row after job completion"
        )
