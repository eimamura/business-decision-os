"""Integration tests for the job-dispatch HITL flow.

These tests run against the live API at API_BASE_URL (API_PORT env, Makefile
default 8002) and are marked @pytest.mark.e2e. A dedicated e2e session fails
loudly when the API is unreachable (see tests/e2e/conftest.py).

Determinism (D-026): the served API must run LLM_DRIVER=scripted — enforced by
the session-scoped guard fixture in tests/e2e/conftest.py. Under the scripted
driver the control agent always emits one deterministic job_dispatch tool call,
so these flows assert scripted-driven outcomes: awaiting_input → approve →
completed with a generated file; reject → failed.

Status vocabulary (DECISIONS.md 2026-08-24): the approval pause reuses the
existing decision_sessions.status value 'awaiting_input' — 'awaiting_approval'
is forbidden by migration 0014's CHECK constraint. After approve + successful
job execution the session reaches 'completed'; reject/failed-job lands 'failed'.

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

from tests.e2e.conftest import API_BASE_URL

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_BASE = API_BASE_URL
_DEV_HEADERS = {"X-Dev-User": "dev-user", "Content-Type": "application/json"}

# Message that triggers job_dispatch. Under LLM_DRIVER=scripted the control
# agent always emits the deterministic job_dispatch tool call on its first
# control turn, independent of wording.
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

        # Wait until the session transitions to awaiting_input (the approval
        # pause status — 'awaiting_approval' is forbidden by migration 0014).
        await _poll_session_status(client, session_id, {"awaiting_input"})

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

        # Wait for the approval-pause status awaiting_input (DECISIONS.md
        # 2026-08-24; migration 0014 CHECK constraint)
        await _poll_session_status(client, session_id, {"awaiting_input"})

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

        # The session must land on its contract-correct terminal state after
        # approve + successful job execution (D-026): 'completed'.
        session_data = await _poll_session_status(
            client, session_id, {"completed", "failed"}
        )
        assert session_data["status"] == "completed", (
            f"Expected session status 'completed' after job completion, "
            f"got '{session_data.get('status')}'"
        )
