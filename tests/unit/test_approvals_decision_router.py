"""Unit tests for POST /approvals/{id}/decision — direct job dispatch on approve."""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4


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
# Approved + linked job → execute_job dispatched directly (no LangGraph resume)
# ---------------------------------------------------------------------------


async def test_approved_decision_with_linked_job_dispatches_execute_job() -> None:
    """POST decision='approved' with a linked job must call execute_job, not resume()."""
    from httpx import ASGITransport, AsyncClient

    session_id = str(uuid4())
    approval_id = uuid4()
    job_id = uuid4()

    record = _make_approval_record(session_id)
    updated = _make_updated_record(session_id, decision="approved")

    mock_approvals_repo = MagicMock()
    mock_approvals_repo.get = AsyncMock(return_value=record)
    mock_approvals_repo.update = AsyncMock(return_value=updated)

    mock_jobs_repo = MagicMock()
    mock_jobs_repo.get_by_approval_id = AsyncMock(return_value={"id": str(job_id)})
    mock_jobs_repo.update_status = AsyncMock()  # called to transition to "queued"

    execute_job_calls: list[UUID] = []

    async def _fake_execute_job(jid: UUID, sse_queue: Any = None) -> dict[str, Any]:
        execute_job_calls.append(jid)
        return {}

    mock_orchestrator = MagicMock()
    mock_orchestrator.resume = AsyncMock()

    from apps.api.main import app
    import apps.api.routers.approvals as approvals_module

    app.dependency_overrides[approvals_module.get_orchestrator_dep] = (
        lambda: mock_orchestrator
    )
    try:
        with (
            patch.object(approvals_module, "_approvals_repo", mock_approvals_repo),
            patch(
                "packages.persistence.sessions_repo.DecisionSessionRepository.update_status",
                AsyncMock(),
            ),
            patch(
                "packages.persistence.jobs_repo.JobsRepository",
                return_value=mock_jobs_repo,
            ),
            patch(
                "packages.agent.job_executor.execute_job",
                side_effect=_fake_execute_job,
            ),
            patch("apps.api.state.broadcasters", {}),
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
    await asyncio.sleep(0)
    assert len(execute_job_calls) == 1, (
        f"execute_job must be called exactly once when a linked job exists; got {len(execute_job_calls)}"
    )
    assert execute_job_calls[0] == job_id
    # LangGraph resume must NOT be called when a linked job handles execution
    assert mock_orchestrator.resume.call_count == 0, (
        "orchestrator.resume() must not be called when a linked job exists"
    )


# ---------------------------------------------------------------------------
# Approved + no linked job → falls back to LangGraph resume
# ---------------------------------------------------------------------------


async def test_approved_decision_without_linked_job_falls_back_to_resume() -> None:
    """POST decision='approved' with no linked job falls back to orchestrator.resume()."""
    from httpx import ASGITransport, AsyncClient

    session_id = str(uuid4())
    approval_id = uuid4()
    record = _make_approval_record(session_id)
    updated = _make_updated_record(session_id, decision="approved")

    mock_approvals_repo = MagicMock()
    mock_approvals_repo.get = AsyncMock(return_value=record)
    mock_approvals_repo.update = AsyncMock(return_value=updated)

    mock_jobs_repo = MagicMock()
    mock_jobs_repo.get_by_approval_id = AsyncMock(return_value=None)

    resume_calls: list[tuple[Any, Any]] = []

    async def _fake_resume(sid: Any, aid: Any) -> None:
        resume_calls.append((sid, aid))

    mock_orchestrator = MagicMock()
    mock_orchestrator.resume = _fake_resume

    from apps.api.main import app
    import apps.api.routers.approvals as approvals_module

    app.dependency_overrides[approvals_module.get_orchestrator_dep] = (
        lambda: mock_orchestrator
    )
    try:
        with (
            patch.object(approvals_module, "_approvals_repo", mock_approvals_repo),
            patch(
                "packages.persistence.sessions_repo.DecisionSessionRepository.update_status",
                AsyncMock(),
            ),
            patch(
                "packages.persistence.jobs_repo.JobsRepository",
                return_value=mock_jobs_repo,
            ),
            patch("apps.api.state.broadcasters", {}),
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
    await asyncio.sleep(0)
    assert len(resume_calls) == 1, (
        f"orchestrator.resume() must be called as fallback when no linked job; got {len(resume_calls)}"
    )


# ---------------------------------------------------------------------------
# Rejected → job cancelled, no execute_job or resume
# ---------------------------------------------------------------------------


async def test_rejected_decision_does_not_call_orchestrator_resume() -> None:
    """POST decision='rejected' must NOT call orchestrator.resume()."""
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


# ---------------------------------------------------------------------------
# needs_revision → linked job cancelled, session failed
# ---------------------------------------------------------------------------


async def test_needs_revision_cancels_linked_job() -> None:
    """POST decision='needs_revision' must cancel the linked job."""
    from httpx import ASGITransport, AsyncClient

    session_id = str(uuid4())
    approval_id = uuid4()
    job_id = uuid4()

    record = _make_approval_record(session_id)
    updated = _make_updated_record(session_id, decision="needs_revision")

    mock_approvals_repo = MagicMock()
    mock_approvals_repo.get = AsyncMock(return_value=record)
    mock_approvals_repo.update = AsyncMock(return_value=updated)

    update_status_calls: list[tuple[Any, str]] = []

    async def _fake_update_status(jid: Any, status: str) -> None:
        update_status_calls.append((jid, status))

    mock_jobs_repo = MagicMock()
    mock_jobs_repo.get_by_approval_id = AsyncMock(return_value={"id": str(job_id)})
    mock_jobs_repo.update_status = _fake_update_status

    mock_orchestrator = MagicMock()
    mock_orchestrator.resume = AsyncMock()

    from apps.api.main import app
    import apps.api.routers.approvals as approvals_module

    app.dependency_overrides[approvals_module.get_orchestrator_dep] = (
        lambda: mock_orchestrator
    )
    try:
        with (
            patch.object(approvals_module, "_approvals_repo", mock_approvals_repo),
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
                    json={"decision": "needs_revision", "reason": "please fix X"},
                    headers={"x-dev-user": "test-user"},
                )
    finally:
        app.dependency_overrides.pop(approvals_module.get_orchestrator_dep, None)

    assert resp.status_code == 200
    assert any(status == "cancelled" for _, status in update_status_calls), (
        "linked job must be cancelled on needs_revision"
    )
    assert mock_orchestrator.resume.call_count == 0, (
        "orchestrator.resume() must NOT be called on needs_revision"
    )


async def test_needs_revision_updates_session_to_failed() -> None:
    """POST decision='needs_revision' must mark the session as failed."""
    from httpx import ASGITransport, AsyncClient

    session_id = str(uuid4())
    approval_id = uuid4()

    record = _make_approval_record(session_id)
    updated = _make_updated_record(session_id, decision="needs_revision")

    mock_approvals_repo = MagicMock()
    mock_approvals_repo.get = AsyncMock(return_value=record)
    mock_approvals_repo.update = AsyncMock(return_value=updated)

    mock_jobs_repo = MagicMock()
    mock_jobs_repo.get_by_approval_id = AsyncMock(return_value=None)
    mock_jobs_repo.update_status = AsyncMock()

    session_status_calls: list[tuple[str, str]] = []

    async def _fake_session_update(sid: str, status: str) -> None:
        session_status_calls.append((sid, status))

    mock_orchestrator = MagicMock()
    mock_orchestrator.resume = AsyncMock()

    from apps.api.main import app
    import apps.api.routers.approvals as approvals_module

    app.dependency_overrides[approvals_module.get_orchestrator_dep] = (
        lambda: mock_orchestrator
    )
    try:
        with (
            patch.object(approvals_module, "_approvals_repo", mock_approvals_repo),
            patch(
                "packages.persistence.sessions_repo.DecisionSessionRepository.update_status",
                side_effect=_fake_session_update,
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
                    json={"decision": "needs_revision", "reason": "please fix X"},
                    headers={"x-dev-user": "test-user"},
                )
    finally:
        app.dependency_overrides.pop(approvals_module.get_orchestrator_dep, None)

    assert resp.status_code == 200
    assert any(status == "failed" for _, status in session_status_calls), (
        "session must be marked failed on needs_revision"
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
