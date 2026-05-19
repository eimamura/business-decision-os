"""Phase 1 E2E smoke tests: chat → recommendation → approval → audit.

These tests run against the live API (localhost:8000) using httpx.
Start the server before running: uv run uvicorn apps.api.main:app --port 8000
"""

from __future__ import annotations

import json
from uuid import uuid4

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _api(path: str) -> str:
    return f"http://localhost:8000{path}"


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
def test_create_session() -> None:
    """POST /api/v1/sessions creates a session."""
    import httpx

    resp = httpx.post(_api("/api/v1/sessions"), json={"goal": "E2E test session"}, timeout=5)
    assert resp.status_code == 200
    data = resp.json()
    assert "session_id" in data
    assert data["status"] == "active"


@pytest.mark.e2e
def test_decisions_sse_stream() -> None:
    """POST /api/v1/decisions streams SSE events ending with recommendation_ready."""
    import httpx

    events: list[dict] = []
    with httpx.stream(
        "POST",
        _api("/api/v1/decisions"),
        json={"goal": "Optimize replenishment for SKU-E2E-001"},
        timeout=30,
        headers={"Accept": "text/event-stream"},
    ) as resp:
        assert resp.status_code == 200
        for line in resp.iter_lines():
            if line.startswith("data:"):
                payload = json.loads(line[5:].strip())
                events.append(payload)
                if payload.get("type") == "done":
                    break

    event_types = [e.get("type") for e in events]
    assert "session_started" in event_types or "step_started" in event_types
    assert "recommendation_ready" in event_types
    assert "done" in event_types


@pytest.mark.e2e
def test_list_sessions() -> None:
    """GET /api/v1/sessions returns a list."""
    import httpx

    resp = httpx.get(_api("/api/v1/sessions"), timeout=5)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
