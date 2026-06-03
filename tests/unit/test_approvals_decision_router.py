"""Unit tests for T-071: POST /approvals/{id}/decision triggers LangGraph resume."""
from __future__ import annotations

import asyncio
import inspect
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_approval_record(session_id: str | None = None) -> dict[str, Any]:
    return {
        "id": str(uuid4()),
        "status": "pending",
        "session_id": session_id or str(uuid4()),
        "recommendation_id": None,
        "reason": None,
        "actor": None,
    }


def _make_updated_record(session_id: str, decision: str = "approved") -> dict[str, Any]:
    return {
        "id": str(uuid4()),
        "status": decision,
        "session_id": session_id,
        "recommendation_id": None,
        "reason": None,
        "actor": "test-user",
    }


# ---------------------------------------------------------------------------
# T-071: execute_job must NOT be imported in approvals.py
# ---------------------------------------------------------------------------


def test_approvals_router_does_not_import_execute_job() -> None:
    """The approvals router must not import execute_job after T-071."""
    import apps.api.routers.approvals as approvals_module

    source = inspect.getsource(approvals_module)
    assert "execute_job" not in source, (
        "execute_job must not be imported or referenced in approvals.py after T-071 — "
        "job execution now happens exclusively inside the LangGraph graph"
    )


# ---------------------------------------------------------------------------
# T-071: approved path calls orchestrator.resume(), not execute_job
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_approved_decision_triggers_orchestrator_resume() -> None:
    """POST /approvals/{id}/decision with 'approved' must fire orchestrator.resume()."""
    from httpx import ASGITransport, AsyncClient

    session_id = str(uuid4())
    approval_id = uuid4()
    record = _make_approval_record(session_id)
    updated = _make_updated_record(session_id, decision="approved")

    mock_approvals_repo = MagicMock()
    mock_approvals_repo.get = AsyncMock(return_value=record)
    mock_approvals_repo.update = AsyncMock(return_value=updated)

    resume_calls: list[tuple[Any, Any]] = []

    async def _fake_resume(sid: Any, aid: Any) -> None:
        resume_calls.append((sid, aid))

    mock_orchestrator = MagicMock()
    mock_orchestrator.resume = _fake_resume

    from apps.api.main import app
    import apps.api.routers.approvals as approvals_module

    # Override FastAPI dependency and module-level state
    app.dependency_overrides[approvals_module.get_orchestrator_dep] = (
        lambda: mock_orchestrator
    )
    try:
        with (
            patch.object(approvals_module, "_approvals_repo", mock_approvals_repo),
            patch.object(approvals_module, "can_execute", AsyncMock(return_value=True)),
            patch(
                "packages.persistence.sessions_repo.DecisionSessionRepository.update_status",
                AsyncMock(),
            ),
        ):
            transport = ASGITransport(app=app)  # type: ignore[arg-type]
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    f"/api/v1/approvals/{approval_id}/decision",
                    json={"decision": "approved"},
                    headers={"x-dev-user": "test-user"},
                )
    finally:
        app.dependency_overrides.pop(approvals_module.get_orchestrator_dep, None)

    assert resp.status_code == 200
    # Give create_task a chance to run
    await asyncio.sleep(0)
    assert len(resume_calls) == 1, (
        f"orchestrator.resume() must be called exactly once on approval; got {len(resume_calls)}"
    )


@pytest.mark.asyncio
async def test_rejected_decision_does_not_call_orchestrator_resume() -> None:
    """POST /approvals/{id}/decision with 'rejected' must NOT call orchestrator.resume()."""
    from httpx import ASGITransport, AsyncClient

    session_id = str(uuid4())
    approval_id = uuid4()
    record = _make_approval_record(session_id)
    updated = _make_updated_record(session_id, decision="rejected")

    mock_approvals_repo = MagicMock()
    mock_approvals_repo.get = AsyncMock(return_value=record)
    mock_approvals_repo.update = AsyncMock(return_value=updated)

    resume_calls: list[Any] = []

    async def _fake_resume(sid: Any, aid: Any) -> None:
        resume_calls.append((sid, aid))

    mock_orchestrator = MagicMock()
    mock_orchestrator.resume = _fake_resume

    mock_jobs_repo = MagicMock()
    mock_jobs_repo.get_by_approval_id = AsyncMock(return_value=None)

    from apps.api.main import app
    import apps.api.routers.approvals as approvals_module

    app.dependency_overrides[approvals_module.get_orchestrator_dep] = (
        lambda: mock_orchestrator
    )
    try:
        with (
            patch.object(approvals_module, "_approvals_repo", mock_approvals_repo),
            patch.object(approvals_module, "can_execute", AsyncMock(return_value=True)),
            patch(
                "packages.persistence.sessions_repo.DecisionSessionRepository.update_status",
                AsyncMock(),
            ),
            patch(
                "packages.persistence.jobs_repo.JobsRepository",
                return_value=mock_jobs_repo,
            ),
        ):
            transport = ASGITransport(app=app)  # type: ignore[arg-type]
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    f"/api/v1/approvals/{approval_id}/decision",
                    json={"decision": "rejected"},
                    headers={"x-dev-user": "test-user"},
                )
    finally:
        app.dependency_overrides.pop(approvals_module.get_orchestrator_dep, None)

    assert resp.status_code == 200
    await asyncio.sleep(0)
    assert resume_calls == [], (
        "orchestrator.resume() must NOT be called when decision is 'rejected'"
    )


def test_get_orchestrator_dep_returns_session_orchestrator() -> None:
    """get_orchestrator_dep() must return a SessionOrchestrator instance."""
    from packages.agent.orchestrator import SessionOrchestrator

    import os

    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key-abc123"}):
        from apps.api.routers.approvals import get_orchestrator_dep

        result = get_orchestrator_dep()
        assert isinstance(result, SessionOrchestrator), (
            f"Expected SessionOrchestrator, got {type(result)}"
        )


def test_get_orchestrator_dep_no_sse_queue() -> None:
    """get_orchestrator_dep() must create an orchestrator with no SSE queue (sse_queue=None)."""
    import os

    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key-abc123"}):
        from apps.api.routers.approvals import get_orchestrator_dep

        result = get_orchestrator_dep()
        assert result._sse_queue is None, (
            "get_orchestrator_dep() must pass sse_queue=None to the orchestrator"
        )
