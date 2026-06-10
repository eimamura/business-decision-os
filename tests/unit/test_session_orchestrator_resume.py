from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from langgraph.types import Interrupt, StateSnapshot
from langchain_core.runnables import RunnableConfig

from packages.agent.llm import LLMMessage, LLMResponse, LLMUsage
from packages.agent.orchestrator import SessionOrchestrator, SessionUserQuery
from packages.agent.orchestrator.models import SessionResponse, AgentRoute, SessionIntent
from packages.memory import StubMemoryStore
from packages.tools import create_tool_registry


# ---------------------------------------------------------------------------
# Helpers / fakes
# ---------------------------------------------------------------------------


def _make_usage() -> LLMUsage:
    return LLMUsage(
        input_tokens=0,
        output_tokens=0,
        total_cost_usd=Decimal("0"),
    )


def _llm_response(text: str) -> LLMResponse:
    return LLMResponse(
        text=text,
        tool_calls=[],
        finish_reason="stop",
        usage=_make_usage(),
        model="stub",
        request_id=str(uuid4()),
        latency_ms=0,
    )


def _make_snapshot_with_interrupt() -> StateSnapshot:
    """Return a StateSnapshot that looks like a thread paused at an interrupt."""
    fake_interrupt = Interrupt(value={"ask_user_id": "abc", "question": "?"})
    return StateSnapshot(
        values={"session_id": "fake-session"},
        next=("wait_for_answer",),
        config=RunnableConfig(configurable={"thread_id": "fake-thread"}),
        metadata={"source": "loop", "step": 0, "parents": {}},
        created_at="2026-01-01T00:00:00+00:00",
        parent_config=None,
        tasks=(),
        interrupts=(fake_interrupt,),
    )


def _make_orchestrator() -> SessionOrchestrator:
    class _StubLLMClient:
        _model = "stub"

        async def complete(self, *args: Any, **kwargs: Any) -> LLMResponse:
            return _llm_response("stub response")

    return SessionOrchestrator(
        llm_client=_StubLLMClient(),
        tool_registry=create_tool_registry(),
        memory_store=StubMemoryStore(),
    )


def _make_session_response() -> SessionResponse:
    return SessionResponse(
        mode="direct_chat",
        reply="Job completed successfully.",
        intent=SessionIntent(
            category="job_resume",
            confidence=1.0,
            rationale="resume",
            goal_text=None,
        ),
        route=AgentRoute(
            mode="direct_chat",
            agents=[],
            requires_planning=False,
            requires_dag=False,
            rationale="resume",
        ),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_resume_uses_graph_astream_with_none_input() -> None:
    """resume() must call graph.astream_events(None, ...) — not ainvoke(initial_state, ...)."""
    orchestrator = _make_orchestrator()
    session_id = uuid4()
    approval_id = uuid4()
    expected = _make_session_response()

    astream_calls: list[tuple[Any, ...]] = []

    async def _fake_astream_events(
        input: Any, *, config: dict[str, Any], version: str
    ) -> Any:
        astream_calls.append((input, config, version))
        # Emit root on_chain_end event with result in output
        yield {
            "event": "on_chain_end",
            "name": "LangGraph",
            "run_id": "test-run",
            "parent_ids": [],
            "data": {"output": {"result": expected}},
        }

    mock_graph = MagicMock()
    mock_graph.astream_events = _fake_astream_events
    mock_graph.aget_state = AsyncMock(return_value=_make_snapshot_with_interrupt())
    orchestrator._graph = mock_graph

    result = await orchestrator.resume(session_id, approval_id)

    assert len(astream_calls) == 1, "astream_events must be called exactly once"
    called_input, called_config, called_version = astream_calls[0]
    assert called_input is None, "resume() must pass None as input to graph.astream_events"
    assert called_config["configurable"]["thread_id"] == str(session_id)
    assert called_version == "v2"
    assert result is expected


async def test_resume_returns_result_from_graph_state() -> None:
    """resume() must extract SessionResponse from the 'result' key of the root chain output."""
    orchestrator = _make_orchestrator()
    session_id = uuid4()
    approval_id = uuid4()
    expected = _make_session_response()

    async def _fake_astream_events(
        input: Any, *, config: dict[str, Any], version: str
    ) -> Any:
        # Emit a non-root node event (should be ignored for final_state extraction)
        yield {
            "event": "on_chain_end",
            "name": "classify_intent",
            "run_id": "node-run",
            "parent_ids": ["root-run"],
            "data": {"output": {"intent": None}},
        }
        # Emit root on_chain_end with result
        yield {
            "event": "on_chain_end",
            "name": "LangGraph",
            "run_id": "root-run",
            "parent_ids": [],
            "data": {"output": {"result": expected}},
        }

    mock_graph = MagicMock()
    mock_graph.astream_events = _fake_astream_events
    mock_graph.aget_state = AsyncMock(return_value=_make_snapshot_with_interrupt())
    orchestrator._graph = mock_graph

    result = await orchestrator.resume(session_id, approval_id)

    assert result is expected


async def test_resume_raises_on_no_result() -> None:
    """resume() must raise RuntimeError when no result is produced by the graph."""
    orchestrator = _make_orchestrator()
    session_id = uuid4()
    approval_id = uuid4()

    async def _fake_astream(
        input: Any, config: dict[str, Any], stream_mode: str
    ) -> Any:
        yield {"some_node": {"foo": "bar"}}

    mock_graph = MagicMock()
    mock_graph.astream = _fake_astream
    mock_graph.aget_state = AsyncMock(return_value=_make_snapshot_with_interrupt())
    orchestrator._graph = mock_graph

    mock_repo = MagicMock()
    mock_repo.update_status = AsyncMock()

    with patch(
        "packages.agent.orchestrator.session_orchestrator.DecisionSessionRepository",
        return_value=mock_repo,
    ):
        with pytest.raises(RuntimeError, match="Graph resume produced no result"):
            await orchestrator.resume(session_id, approval_id)


async def test_resume_schedules_failed_status_on_graph_exception() -> None:
    """When graph.astream_events raises, resume() must schedule a 'failed' status update."""
    orchestrator = _make_orchestrator()
    session_id = uuid4()
    approval_id = uuid4()

    async def _fake_astream_events(
        input: Any, *, config: dict[str, Any], version: str
    ) -> Any:
        raise RuntimeError("graph exploded")
        yield  # make it an async generator

    mock_graph = MagicMock()
    mock_graph.astream_events = _fake_astream_events
    mock_graph.aget_state = AsyncMock(return_value=_make_snapshot_with_interrupt())
    orchestrator._graph = mock_graph

    mock_repo = MagicMock()
    mock_repo.update_status = AsyncMock()

    with patch(
        "packages.agent.orchestrator.session_orchestrator.DecisionSessionRepository",
        return_value=mock_repo,
    ):
        with pytest.raises(RuntimeError, match="graph exploded"):
            await orchestrator.resume(session_id, approval_id)
        await asyncio.sleep(0)

    calls = [call.args for call in mock_repo.update_status.call_args_list]
    statuses = [c[1] for c in calls]
    assert "failed" in statuses, f"Expected 'failed' status update on exception, got: {statuses}"


async def test_resume_does_not_call_jobs_repository() -> None:
    """resume() must NOT look up jobs or call JobsRepository — the graph drives the response."""
    orchestrator = _make_orchestrator()
    session_id = uuid4()
    approval_id = uuid4()
    expected = _make_session_response()

    async def _fake_astream_events(
        input: Any, *, config: dict[str, Any], version: str
    ) -> Any:
        yield {
            "event": "on_chain_end",
            "name": "LangGraph",
            "run_id": "root-run",
            "parent_ids": [],
            "data": {"output": {"result": expected}},
        }

    mock_graph = MagicMock()
    mock_graph.astream_events = _fake_astream_events
    mock_graph.aget_state = AsyncMock(return_value=_make_snapshot_with_interrupt())
    orchestrator._graph = mock_graph

    with patch("packages.persistence.jobs_repo.JobsRepository") as mock_jobs_cls:
        await orchestrator.resume(session_id, approval_id)

    mock_jobs_cls.assert_not_called()


async def test_resume_signature_unchanged() -> None:
    """resume() must accept session_id: UUID and approval_id: UUID and return SessionResponse."""
    import inspect
    from packages.agent.orchestrator.session_orchestrator import SessionOrchestrator

    sig = inspect.signature(SessionOrchestrator.resume)
    params = list(sig.parameters.keys())
    assert "session_id" in params
    assert "approval_id" in params
    # Return annotation
    hints = sig.return_annotation
    # Should be SessionResponse (possibly as a string annotation)
    assert "SessionResponse" in str(hints)


async def test_resume_get_graph_uses_memory_saver_without_database_url() -> None:
    """_get_graph() must fall back to MemorySaver when DATABASE_URL is not set."""
    orchestrator = _make_orchestrator()

    with patch.dict("os.environ", {}, clear=True):
        # Clear DATABASE_URL so MemorySaver is used
        import os
        os.environ.pop("DATABASE_URL", None)

        graph = await orchestrator._get_graph()
        # Graph must be built and cached
        assert graph is not None
        assert orchestrator._graph is graph

        # Second call must return the same cached graph
        graph2 = await orchestrator._get_graph()
        assert graph2 is graph
