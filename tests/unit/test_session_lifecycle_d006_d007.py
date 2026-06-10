"""Unit tests for P79-B-03 — D-006 and D-007 acceptance criteria.

T-498: D-006 — No-pending-interrupt guard on POST /answer
  - 409 when no pending interrupt (orchestrator graph NOT invoked)
  - answer_ask_user raises NoPendingInterruptError on empty thread (metadata=None)
  - answer_ask_user raises NoPendingInterruptError on checkpoint with no interrupts
  - Happy-path ask_user resume is unaffected (existing behaviour confirmed via contract test)

T-499: D-007 — Delete cancels in-flight run + DB recovery
  - Deleting a session cancels its registered in-flight task
  - No done event broadcast after task cancellation
  - make_event_persister skips write for tombstoned session (no DB task created)
  - DB recovery: dict cleared + DB row present → endpoint succeeds (not 404)
  - DB recovery: both absent → 404
  - Event persister FK downgrade: FK-like failure logs at debug, not warning
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from langgraph.types import Interrupt, StateSnapshot
from langchain_core.runnables import RunnableConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_snapshot_no_checkpoint() -> StateSnapshot:
    """StateSnapshot representing a thread that has never been checkpointed."""
    return StateSnapshot(
        values={},
        next=(),
        config=RunnableConfig(configurable={"thread_id": "no-thread"}),
        metadata=None,           # metadata=None → no checkpoint
        created_at=None,
        parent_config=None,
        tasks=(),
        interrupts=(),
    )


def _make_snapshot_no_interrupt() -> StateSnapshot:
    """StateSnapshot with a checkpoint but no pending interrupt."""
    return StateSnapshot(
        values={"session_id": "some-session"},
        next=(),
        config=RunnableConfig(configurable={"thread_id": "some-thread"}),
        metadata={"source": "loop", "step": 1, "parents": {}},   # checkpoint exists
        created_at="2026-01-01T00:00:00+00:00",
        parent_config=None,
        tasks=(),
        interrupts=(),           # empty → no pending interrupt
    )


def _make_snapshot_with_interrupt() -> StateSnapshot:
    """StateSnapshot with a pending interrupt — has_pending_interrupt should be True."""
    fake_interrupt = Interrupt(value={"ask_user_id": "abc", "question": "?"})
    return StateSnapshot(
        values={"session_id": "some-session"},
        next=("wait_for_answer",),
        config=RunnableConfig(configurable={"thread_id": "some-thread"}),
        metadata={"source": "loop", "step": 1, "parents": {}},
        created_at="2026-01-01T00:00:00+00:00",
        parent_config=None,
        tasks=(),
        interrupts=(fake_interrupt,),
    )


def _make_bare_orchestrator() -> Any:
    """Build a SessionOrchestrator without a live DB (MemorySaver)."""
    from packages.agent.orchestrator import SessionOrchestrator
    from packages.memory import StubMemoryStore
    from packages.tools import create_tool_registry

    class _StubLLM:
        _model = "stub"

        async def complete(self, *args: Any, **kwargs: Any) -> Any:
            raise AssertionError("LLM must not be called in these tests")

    return SessionOrchestrator(
        llm_client=_StubLLM(),
        tool_registry=create_tool_registry(),
        memory_store=StubMemoryStore(),
    )


# ---------------------------------------------------------------------------
# T-498 — D-006: NoPendingInterruptError from has_pending_interrupt()
# ---------------------------------------------------------------------------


async def test_answer_ask_user_no_checkpoint_raises_no_pending_interrupt_error() -> None:
    """answer_ask_user raises NoPendingInterruptError when aget_state returns metadata=None."""
    from packages.agent.orchestrator.session_orchestrator import NoPendingInterruptError

    orchestrator = _make_bare_orchestrator()
    session_id = uuid4()

    mock_graph = MagicMock()
    mock_graph.aget_state = AsyncMock(return_value=_make_snapshot_no_checkpoint())
    orchestrator._graph = mock_graph

    with pytest.raises(NoPendingInterruptError):
        await orchestrator.answer_ask_user(session_id, "some answer")


async def test_answer_ask_user_checkpoint_no_interrupt_raises_no_pending_interrupt_error() -> None:
    """answer_ask_user raises NoPendingInterruptError when checkpoint exists but interrupts=()."""
    from packages.agent.orchestrator.session_orchestrator import NoPendingInterruptError

    orchestrator = _make_bare_orchestrator()
    session_id = uuid4()

    mock_graph = MagicMock()
    mock_graph.aget_state = AsyncMock(return_value=_make_snapshot_no_interrupt())
    orchestrator._graph = mock_graph

    with pytest.raises(NoPendingInterruptError):
        await orchestrator.answer_ask_user(session_id, "some answer")


async def test_no_pending_interrupt_error_is_typed_not_key_error() -> None:
    """NoPendingInterruptError must be a RuntimeError subclass, not KeyError."""
    from packages.agent.orchestrator.session_orchestrator import NoPendingInterruptError

    assert issubclass(NoPendingInterruptError, RuntimeError)


async def test_resume_no_checkpoint_raises_no_pending_interrupt_error() -> None:
    """resume() also raises NoPendingInterruptError when aget_state returns metadata=None."""
    from packages.agent.orchestrator.session_orchestrator import NoPendingInterruptError

    orchestrator = _make_bare_orchestrator()
    session_id = uuid4()
    approval_id = uuid4()

    mock_graph = MagicMock()
    mock_graph.aget_state = AsyncMock(return_value=_make_snapshot_no_checkpoint())
    orchestrator._graph = mock_graph

    with pytest.raises(NoPendingInterruptError):
        await orchestrator.resume(session_id, approval_id)


async def test_resume_checkpoint_no_interrupt_raises_no_pending_interrupt_error() -> None:
    """resume() raises NoPendingInterruptError when checkpoint exists but interrupts=()."""
    from packages.agent.orchestrator.session_orchestrator import NoPendingInterruptError

    orchestrator = _make_bare_orchestrator()
    session_id = uuid4()
    approval_id = uuid4()

    mock_graph = MagicMock()
    mock_graph.aget_state = AsyncMock(return_value=_make_snapshot_no_interrupt())
    orchestrator._graph = mock_graph

    with pytest.raises(NoPendingInterruptError):
        await orchestrator.resume(session_id, approval_id)


# ---------------------------------------------------------------------------
# T-498 — D-006: HTTP layer — POST /answer with no pending interrupt → 409
# ---------------------------------------------------------------------------


async def test_submit_ask_user_answer_no_pending_interrupt_returns_409() -> None:
    """POST /api/v1/sessions/{id}/answer with no pending interrupt → HTTP 409.

    Verifies: the pre-dispatch guard (has_pending_interrupt → False) returns 409
    without creating a background task or invoking orchestrator.answer_ask_user.
    """
    from httpx import ASGITransport, AsyncClient

    from apps.api.main import app
    import apps.api.routers.sessions as sessions_module

    session_id = uuid4()
    session_id_str = str(session_id)

    # Pre-populate in-memory session so we get past the 404 guard.
    sessions_module.sessions[session_id_str] = {
        "session_id": session_id_str,
        "status": "pending",
        "goal": "test",
        "messages": [],
    }

    mock_orchestrator = MagicMock()
    mock_orchestrator.has_pending_interrupt = AsyncMock(return_value=False)
    mock_orchestrator.answer_ask_user = AsyncMock(
        side_effect=AssertionError("answer_ask_user must not be called")
    )

    try:
        with patch.object(sessions_module, "get_orchestrator", return_value=mock_orchestrator):
            transport = ASGITransport(app=app)  # type: ignore[arg-type]
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    f"/api/v1/sessions/{session_id}/answer",
                    json={"answer": "some answer"},
                )
    finally:
        sessions_module.sessions.pop(session_id_str, None)

    assert resp.status_code == 409


async def test_submit_ask_user_answer_no_pending_interrupt_409_detail_mentions_no_pending_question() -> None:
    """409 detail must contain actionable guidance about the missing pending question."""
    from httpx import ASGITransport, AsyncClient

    from apps.api.main import app
    import apps.api.routers.sessions as sessions_module

    session_id = uuid4()
    session_id_str = str(session_id)

    sessions_module.sessions[session_id_str] = {
        "session_id": session_id_str,
        "status": "pending",
        "goal": "test",
        "messages": [],
    }

    mock_orchestrator = MagicMock()
    mock_orchestrator.has_pending_interrupt = AsyncMock(return_value=False)
    mock_orchestrator.answer_ask_user = AsyncMock()

    try:
        with patch.object(sessions_module, "get_orchestrator", return_value=mock_orchestrator):
            transport = ASGITransport(app=app)  # type: ignore[arg-type]
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    f"/api/v1/sessions/{session_id}/answer",
                    json={"answer": "anything"},
                )
    finally:
        sessions_module.sessions.pop(session_id_str, None)

    body = resp.json()
    detail = body.get("detail", "")
    assert "No pending question" in detail or "pending" in detail.lower()


async def test_submit_ask_user_answer_no_pending_interrupt_graph_not_invoked() -> None:
    """POST /answer with no pending interrupt must not create a background task (no graph run)."""
    from httpx import ASGITransport, AsyncClient

    from apps.api.main import app
    import apps.api.routers.sessions as sessions_module

    session_id = uuid4()
    session_id_str = str(session_id)

    sessions_module.sessions[session_id_str] = {
        "session_id": session_id_str,
        "status": "pending",
        "goal": "test",
        "messages": [],
    }

    mock_orchestrator = MagicMock()
    mock_orchestrator.has_pending_interrupt = AsyncMock(return_value=False)
    # answer_ask_user should never be called — if it is, the test fails
    mock_orchestrator.answer_ask_user = AsyncMock(
        side_effect=AssertionError("graph was invoked despite no pending interrupt")
    )

    try:
        with patch.object(sessions_module, "get_orchestrator", return_value=mock_orchestrator):
            transport = ASGITransport(app=app)  # type: ignore[arg-type]
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                await client.post(
                    f"/api/v1/sessions/{session_id}/answer",
                    json={"answer": "irrelevant"},
                )
    finally:
        sessions_module.sessions.pop(session_id_str, None)

    # If we reach here without AssertionError from the side_effect, the graph was not invoked.
    mock_orchestrator.answer_ask_user.assert_not_called()


# ---------------------------------------------------------------------------
# T-499 — D-007: delete cancels in-flight task
# ---------------------------------------------------------------------------


async def test_delete_session_cancels_registered_in_flight_task() -> None:
    """DELETE /sessions/{id} must cancel the task registered in session_tasks."""
    import apps.api.state as state_module
    import apps.api.routers.sessions as sessions_module

    session_id_str = str(uuid4())

    # Plant a blocking task in session_tasks (simulating an in-flight run).
    blocked = asyncio.Event()

    async def _blocking_run() -> None:
        await blocked.wait()  # never resolves without being cancelled

    task: asyncio.Task[None] = asyncio.create_task(_blocking_run())
    state_module.session_tasks[session_id_str] = task

    # Plant a session row in the in-memory dict so the 404 check passes.
    sessions_module.sessions[session_id_str] = {
        "session_id": session_id_str,
        "status": "running",
        "goal": "test",
        "messages": [],
    }

    mock_repo = MagicMock()
    mock_repo.delete_session = AsyncMock(return_value=True)

    try:
        with patch(
            "apps.api.routers.sessions.DecisionSessionRepository",
            return_value=mock_repo,
        ):
            from httpx import ASGITransport, AsyncClient
            from apps.api.main import app

            transport = ASGITransport(app=app)  # type: ignore[arg-type]
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.delete(f"/api/v1/sessions/{session_id_str}")
    finally:
        # Clean up in case the test fails mid-way.
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass
        state_module.session_tasks.pop(session_id_str, None)
        sessions_module.sessions.pop(session_id_str, None)
        state_module._deleted_session_ids.discard(session_id_str)

    assert resp.status_code == 204
    assert task.cancelled()


async def test_delete_session_no_done_event_broadcast_after_cancellation() -> None:
    """When a task is cancelled via delete, the done event must not be broadcast.

    This tests the tombstone + task-cancellation combination:
    1. Session is tombstoned (_deleted_session_ids).
    2. In-flight task is cancelled and awaited.
    3. Any event that the event_persister might receive is silently dropped.
    4. The broadcaster receives no "done" event.

    The test uses the real make_event_persister and a fake Broadcaster to confirm
    the tombstone guard suppresses writes before the broadcaster is touched.
    """
    import apps.api.state as state_module

    session_id_str = str(uuid4())
    broadcast_events: list[dict[str, Any]] = []

    class _CaptureBroadcaster:
        async def put(self, event: dict[str, Any]) -> None:
            broadcast_events.append(event)

    broadcaster = _CaptureBroadcaster()
    state_module.broadcasters[session_id_str] = broadcaster  # type: ignore[assignment]

    # Tombstone the session before creating the persister.
    state_module._deleted_session_ids.add(session_id_str)
    persister = state_module.make_event_persister(session_id_str)

    try:
        # Simulate what would happen if the cancellation guard failed and the
        # persister was still called — it must not schedule any write.
        with patch("apps.api.state.SessionEventRepository") as mock_repo_cls:
            await persister({"type": "done", "session_id": session_id_str})
            await asyncio.sleep(0)
            # SessionEventRepository must not be instantiated for tombstoned session
            mock_repo_cls.assert_not_called()
    finally:
        state_module._deleted_session_ids.discard(session_id_str)
        state_module.broadcasters.pop(session_id_str, None)

    # No done event was added to the broadcaster
    done_events = [e for e in broadcast_events if e.get("type") == "done"]
    assert done_events == []


# ---------------------------------------------------------------------------
# T-499 — D-007: make_event_persister — tombstone guard
# ---------------------------------------------------------------------------


async def test_make_event_persister_skips_write_for_tombstoned_session(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """make_event_persister returns without scheduling a DB write for a tombstoned session."""
    import apps.api.state as state_module

    session_id_str = str(uuid4())
    state_module._deleted_session_ids.add(session_id_str)

    persister = state_module.make_event_persister(session_id_str)

    with patch(
        "apps.api.state.SessionEventRepository",
    ) as mock_repo_cls:
        await persister({"type": "done", "session_id": session_id_str})
        # Give any spuriously-created tasks a chance to run
        await asyncio.sleep(0)

    try:
        # SessionEventRepository must not have been instantiated or called
        mock_repo_cls.assert_not_called()
    finally:
        state_module._deleted_session_ids.discard(session_id_str)


async def test_make_event_persister_fk_violation_logs_at_debug_not_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """FK-violation-like exception in event persister logs at DEBUG, not WARNING."""
    import apps.api.state as state_module

    session_id_str = str(uuid4())
    # Not tombstoned — persister will proceed to try the DB write
    state_module._deleted_session_ids.discard(session_id_str)

    persister = state_module.make_event_persister(session_id_str)

    class _FakeRepo:
        async def create(self, **kwargs: Any) -> None:
            raise Exception("foreign key constraint")

    with (
        patch("apps.api.state.SessionEventRepository", return_value=_FakeRepo()),
        caplog.at_level(logging.DEBUG, logger="apps.api.state"),
    ):
        await persister({"type": "graph_node", "session_id": session_id_str})
        # Let the create_task(_write) run
        await asyncio.sleep(0)

    warning_records = [
        r for r in caplog.records
        if r.levelno >= logging.WARNING and "persist" in r.getMessage().lower()
    ]
    assert warning_records == [], (
        f"Expected no WARNING-level persist records for FK violation, got: {warning_records}"
    )


async def test_make_event_persister_fk_violation_string_match_logs_at_debug(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """ForeignKeyViolation string pattern in exception message is downgraded to debug."""
    import apps.api.state as state_module

    session_id_str = str(uuid4())
    state_module._deleted_session_ids.discard(session_id_str)

    persister = state_module.make_event_persister(session_id_str)

    class _FakeRepo:
        async def create(self, **kwargs: Any) -> None:
            raise Exception("ForeignKeyViolation: insert into session_events")

    with (
        patch("apps.api.state.SessionEventRepository", return_value=_FakeRepo()),
        caplog.at_level(logging.DEBUG, logger="apps.api.state"),
    ):
        await persister({"type": "graph_node", "session_id": session_id_str})
        await asyncio.sleep(0)

    warning_records = [
        r for r in caplog.records
        if r.levelno >= logging.WARNING and "persist" in r.getMessage().lower()
    ]
    assert warning_records == [], (
        f"Expected no WARNING for ForeignKeyViolation string match, got: {warning_records}"
    )


# ---------------------------------------------------------------------------
# T-499 — D-007: DB recovery for update_session_title / get_messages /
#                submit_ask_user_answer (dict cleared, DB row present → success)
# ---------------------------------------------------------------------------


async def test_update_session_title_recovers_from_db_when_dict_empty() -> None:
    """PATCH /sessions/{id}/title succeeds after in-memory dict is cleared (DB row present)."""
    from httpx import ASGITransport, AsyncClient
    from apps.api.main import app
    import apps.api.routers.sessions as sessions_module

    session_id_str = str(uuid4())

    # Ensure dict is empty for this session
    sessions_module.sessions.pop(session_id_str, None)

    db_row = {
        "id": session_id_str,
        "status": "pending",
        "goal": "test goal",
        "title": None,
        "created_at": "2026-01-01T00:00:00+00:00",
    }

    mock_repo = MagicMock()
    mock_repo.get = AsyncMock(return_value=db_row)
    mock_repo.set_title = AsyncMock()

    try:
        with patch(
            "apps.api.routers.sessions.DecisionSessionRepository",
            return_value=mock_repo,
        ):
            transport = ASGITransport(app=app)  # type: ignore[arg-type]
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.patch(
                    f"/api/v1/sessions/{session_id_str}/title",
                    json={"title": "New Title"},
                )
    finally:
        sessions_module.sessions.pop(session_id_str, None)

    assert resp.status_code == 204


async def test_update_session_title_returns_404_when_both_dict_and_db_absent() -> None:
    """PATCH /sessions/{id}/title returns 404 when session is in neither dict nor DB."""
    from httpx import ASGITransport, AsyncClient
    from apps.api.main import app
    import apps.api.routers.sessions as sessions_module

    session_id_str = str(uuid4())
    sessions_module.sessions.pop(session_id_str, None)

    mock_repo = MagicMock()
    mock_repo.get = AsyncMock(return_value=None)   # DB also absent
    mock_repo.set_title = AsyncMock()

    with patch(
        "apps.api.routers.sessions.DecisionSessionRepository",
        return_value=mock_repo,
    ):
        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.patch(
                f"/api/v1/sessions/{session_id_str}/title",
                json={"title": "Unreachable"},
            )

    assert resp.status_code == 404


async def test_get_messages_recovers_from_db_when_dict_empty() -> None:
    """GET /sessions/{id}/messages returns in-memory messages after DB recovery."""
    from httpx import ASGITransport, AsyncClient
    from apps.api.main import app
    import apps.api.routers.sessions as sessions_module

    session_id_str = str(uuid4())
    sessions_module.sessions.pop(session_id_str, None)

    db_session_row = {
        "id": session_id_str,
        "status": "pending",
        "goal": "",
        "title": None,
        "created_at": "2026-01-01T00:00:00+00:00",
    }

    mock_repo = MagicMock()
    # get_messages raises RuntimeError (no DATABASE_URL) so fallback to in-memory path
    mock_repo.get_messages = AsyncMock(
        side_effect=RuntimeError("DATABASE_URL not configured")
    )
    mock_repo.get = AsyncMock(return_value=db_session_row)

    try:
        with patch(
            "apps.api.routers.sessions.DecisionSessionRepository",
            return_value=mock_repo,
        ):
            transport = ASGITransport(app=app)  # type: ignore[arg-type]
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get(f"/api/v1/sessions/{session_id_str}/messages")
    finally:
        sessions_module.sessions.pop(session_id_str, None)

    assert resp.status_code == 200


async def test_get_messages_returns_404_when_both_absent() -> None:
    """GET /sessions/{id}/messages returns 404 when session is in neither dict nor DB."""
    from httpx import ASGITransport, AsyncClient
    from apps.api.main import app
    import apps.api.routers.sessions as sessions_module

    session_id_str = str(uuid4())
    sessions_module.sessions.pop(session_id_str, None)

    mock_repo = MagicMock()
    mock_repo.get_messages = AsyncMock(
        side_effect=RuntimeError("DATABASE_URL not configured")
    )
    mock_repo.get = AsyncMock(return_value=None)

    with patch(
        "apps.api.routers.sessions.DecisionSessionRepository",
        return_value=mock_repo,
    ):
        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(f"/api/v1/sessions/{session_id_str}/messages")

    assert resp.status_code == 404


async def test_submit_ask_user_answer_recovers_from_db_when_dict_empty() -> None:
    """POST /sessions/{id}/answer succeeds (409 or 202) after in-memory dict cleared.

    The test mocks has_pending_interrupt → False so the endpoint reaches the 409
    path (which is the success signal: it got past the 404 guard to the 409 logic).
    """
    from httpx import ASGITransport, AsyncClient
    from apps.api.main import app
    import apps.api.routers.sessions as sessions_module

    session_id = uuid4()
    session_id_str = str(session_id)

    # Clear the in-memory dict
    sessions_module.sessions.pop(session_id_str, None)

    db_row = {
        "id": session_id_str,
        "status": "pending",
        "goal": "",
        "title": None,
        "created_at": "2026-01-01T00:00:00+00:00",
    }

    mock_repo = MagicMock()
    mock_repo.get = AsyncMock(return_value=db_row)

    mock_orchestrator = MagicMock()
    mock_orchestrator.has_pending_interrupt = AsyncMock(return_value=False)

    try:
        with (
            patch(
                "apps.api.routers.sessions.DecisionSessionRepository",
                return_value=mock_repo,
            ),
            patch.object(sessions_module, "get_orchestrator", return_value=mock_orchestrator),
        ):
            transport = ASGITransport(app=app)  # type: ignore[arg-type]
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    f"/api/v1/sessions/{session_id}/answer",
                    json={"answer": "hello"},
                )
    finally:
        sessions_module.sessions.pop(session_id_str, None)

    # 409 (not 404) confirms: recovered from DB, reached the interrupt-guard logic
    assert resp.status_code == 409


async def test_submit_ask_user_answer_returns_404_when_both_absent() -> None:
    """POST /sessions/{id}/answer returns 404 when session is in neither dict nor DB."""
    from httpx import ASGITransport, AsyncClient
    from apps.api.main import app
    import apps.api.routers.sessions as sessions_module

    session_id = uuid4()
    session_id_str = str(session_id)
    sessions_module.sessions.pop(session_id_str, None)

    mock_repo = MagicMock()
    mock_repo.get = AsyncMock(return_value=None)

    with patch(
        "apps.api.routers.sessions.DecisionSessionRepository",
        return_value=mock_repo,
    ):
        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                f"/api/v1/sessions/{session_id}/answer",
                json={"answer": "hello"},
            )

    assert resp.status_code == 404
