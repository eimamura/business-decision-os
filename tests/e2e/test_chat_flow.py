"""Phase 1 E2E smoke tests: chat → recommendation → approval → audit.

These tests run against the live API at API_BASE_URL (API_PORT env, Makefile
default 8002). Start the server before running:
    uv run uvicorn apps.api.main:app --port "$API_PORT"
"""

from __future__ import annotations

import json

import pytest

from tests.e2e.conftest import API_BASE_URL

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _api(path: str) -> str:
    return f"{API_BASE_URL}{path}"


# ---------------------------------------------------------------------------
# Chat flow
# ---------------------------------------------------------------------------


@pytest.mark.e2e
def test_healthz() -> None:
    """API health check returns 200."""
    import httpx

    resp = httpx.get(_api("/healthz"), timeout=5)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.e2e
def test_readyz() -> None:
    """API ready check returns 200."""
    import httpx

    resp = httpx.get(_api("/readyz"), timeout=5)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.e2e
def test_create_session(cleanup_test_sessions: list[str]) -> None:
    """POST /api/v1/sessions creates a session in the pending lifecycle state.

    Contract (apps/api/routers/sessions.py create_session + persistence insert):
    a fresh session is created with status 'pending'; it becomes running /
    awaiting_approval / completed only once a message run progresses it (D-025).
    """
    import httpx

    resp = httpx.post(_api("/api/v1/sessions"), json={"goal": "E2E test session"}, timeout=5)
    assert resp.status_code == 200
    data = resp.json()
    assert "session_id" in data
    assert data["status"] == "pending"
    cleanup_test_sessions.append(data["session_id"])


@pytest.mark.e2e
def test_decisions_sse_stream() -> None:
    """POST /api/v1/decisions honours the backend-dependent response contract (D-027).

    apps/api/routers/decisions.py create_decision branches on the served API's
    JOB_RUNNER_BACKEND (resolved from that process's environment, compose
    default 'celery'):

    - celery  → job-submission JSON {"job_id": ..., "status": "queued"};
      zero SSE events by design.
    - inline  → text/event-stream ending with a done event carrying reply,
      preceded by query_received / intent_classified /
      execution_mode_selected / response_ready.

    The expected branch is detected from the configuration this test runs
    under (the JOB_RUNNER_BACKEND environment variable — the same resolution
    the API itself performs). Observing the opposite shape is a loud config
    mismatch failure, never a vacuous pass.
    """
    import os

    import httpx

    backend = os.environ.get("JOB_RUNNER_BACKEND", "in_process").strip()

    if backend == "celery":
        # Job-submission contract: plain JSON, no SSE events at all.
        resp = httpx.post(
            _api("/api/v1/decisions"),
            json={"goal": "Optimize replenishment for SKU-E2E-001"},
            timeout=30,
        )
        assert resp.status_code == 200, f"{resp.status_code} {resp.text}"
        content_type = resp.headers.get("content-type", "")
        assert "application/json" in content_type, (
            f"JOB_RUNNER_BACKEND=celery must return job-submission JSON, got "
            f"content-type {content_type!r} — check the served API config"
        )
        body = resp.json()
        assert isinstance(body.get("job_id"), str) and body["job_id"], (
            f"Expected non-empty job_id in job-submission payload, got {body}"
        )
        assert body.get("status") == "queued", (
            f"Expected status='queued' in job-submission payload, got {body}"
        )
        return

    # Inline contract: a live SSE stream terminating with the done event.
    # The stable streaming contract (LangGraph-era runtime): every event
    # carries a type, graph_node progress events stream while the graph runs,
    # and the stream ends on a done event carrying the reply field. (The
    # P1-era query_received/intent_classified/… names no longer exist.)
    events: list[dict] = []
    with httpx.stream(
        "POST",
        _api("/api/v1/decisions"),
        json={"goal": "Optimize replenishment for SKU-E2E-001"},
        timeout=30,
        headers={"Accept": "text/event-stream"},
    ) as resp:
        content_type = resp.headers.get("content-type", "")
        if "text/event-stream" not in content_type:
            pytest.fail(
                f"Inline JOB_RUNNER_BACKEND expected an SSE stream but the API "
                f"returned content-type {content_type!r}. If the served API "
                f"runs with JOB_RUNNER_BACKEND=celery, run this tier with the "
                f"same value exported so the test can assert the matching "
                f"contract."
            )
        assert resp.status_code == 200
        for line in resp.iter_lines():
            if line.startswith("data:"):
                payload = json.loads(line[5:].strip())
                events.append(payload)
                if payload.get("type") == "done":
                    break

    assert len(events) >= 2, (
        f"Expected a streamed event sequence, got {len(events)} event(s)"
    )
    for event in events:
        assert isinstance(event.get("type"), str) and event["type"], (
            f"SSE event missing a type field: {event}"
        )
    progress_types = [e["type"] for e in events[:-1]]
    assert "done" not in progress_types, "done must appear exactly once, last"
    assert events[-1]["type"] == "done"
    assert "reply" in events[-1]


@pytest.mark.e2e
def test_list_sessions() -> None:
    """GET /api/v1/sessions returns a list."""
    import httpx

    resp = httpx.get(_api("/api/v1/sessions"), timeout=5)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
