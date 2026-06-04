from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from typing import AsyncIterator

from packages.agent.llm import LLMMessage, LLMResponse, LLMStreamEvent, LLMToolSpec, LLMUsage
from packages.agent.orchestrator import SessionOrchestrator, SessionUserQuery
from packages.memory import StubMemoryStore
from packages.tools import create_tool_registry
from tests.unit.helpers import make_llm_usage

# ---------------------------------------------------------------------------
# Helpers / fakes
# ---------------------------------------------------------------------------


def _llm_response(text: str) -> LLMResponse:
    return LLMResponse(
        text=text,
        tool_calls=[],
        finish_reason="stop",
        usage=make_llm_usage(input_tokens=0, output_tokens=0),
        model="stub",
        request_id=str(uuid4()),
        latency_ms=0,
    )


class DirectChatLLMClient:
    """LLM client that always routes to direct_chat mode and returns a simple reply."""

    def __init__(self) -> None:
        self._model = "stub"

    async def complete(
        self,
        messages: list[LLMMessage],
        tools: Any = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        prompt_cache: bool = True,
        agent_step_id: Any = None,
        specialist_role: Any = None,
    ) -> LLMResponse:
        # Detect which call we are in by inspecting the system message
        system = messages[0].content if messages else ""

        if "intent classifier" in system:
            return _llm_response(
                '{"category":"direct_chat","confidence":0.95,'
                '"rationale":"Greeting only","goal_text":"hello"}'
            )
        if "router inside SessionOrchestrator" in system:
            return _llm_response(
                '{"mode":"direct_chat","agents":[],'
                '"requires_planning":false,"requires_dag":false,"rationale":"chat"}'
            )
        # direct_chat response
        return _llm_response("Hello! How can I help you today?")

    async def stream(
        self,
        messages: list[LLMMessage],
        tools: list[LLMToolSpec] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[LLMStreamEvent]:
        llm_response = await self.complete(messages, tools=tools, **kwargs)

        async def _gen() -> AsyncIterator[LLMStreamEvent]:
            yield LLMStreamEvent(event="text_delta", data=llm_response.text)

        return _gen()


class FailingLLMClient:
    """LLM client whose intent classifier always raises, triggering failed status."""

    def __init__(self) -> None:
        self._model = "stub"

    async def complete(
        self,
        messages: list[LLMMessage],
        tools: Any = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        prompt_cache: bool = True,
        agent_step_id: Any = None,
        specialist_role: Any = None,
    ) -> LLMResponse:
        raise RuntimeError("LLM unavailable")


def _make_orchestrator(llm_client: Any) -> SessionOrchestrator:
    return SessionOrchestrator(
        llm_client=llm_client,
        tool_registry=create_tool_registry(),
        memory_store=StubMemoryStore(),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_run_success_calls_running_then_completed() -> None:
    """On a successful run, update_status must be called with 'running' then 'completed'."""
    orchestrator = _make_orchestrator(DirectChatLLMClient())
    session_id = uuid4()
    query = SessionUserQuery(text="hello")

    mock_repo = MagicMock()
    mock_repo.update_status = AsyncMock()

    with patch(
        "packages.agent.orchestrator.session_orchestrator.DecisionSessionRepository",
        return_value=mock_repo,
    ):
        await orchestrator.run(session_id, query)
        # Allow fire-and-forget tasks to complete
        await asyncio.sleep(0)

    calls = [call.args for call in mock_repo.update_status.call_args_list]
    statuses = [c[1] for c in calls]  # second positional arg is the status string
    assert "running" in statuses, f"Expected 'running' in status calls, got: {statuses}"
    assert "completed" in statuses, f"Expected 'completed' in status calls, got: {statuses}"
    assert statuses.index("running") < statuses.index("completed"), (
        "'running' must precede 'completed'"
    )


async def test_run_failure_calls_running_then_failed() -> None:
    """When run() raises, update_status must be called with 'running' then 'failed'."""
    orchestrator = _make_orchestrator(FailingLLMClient())
    session_id = uuid4()
    query = SessionUserQuery(text="hello")

    mock_repo = MagicMock()
    mock_repo.update_status = AsyncMock()

    with patch(
        "packages.agent.orchestrator.session_orchestrator.DecisionSessionRepository",
        return_value=mock_repo,
    ):
        with pytest.raises(RuntimeError, match="LLM unavailable"):
            await orchestrator.run(session_id, query)
        await asyncio.sleep(0)

    calls = [call.args for call in mock_repo.update_status.call_args_list]
    statuses = [c[1] for c in calls]
    assert "running" in statuses, f"Expected 'running' in status calls, got: {statuses}"
    assert "failed" in statuses, f"Expected 'failed' in status calls, got: {statuses}"
    assert "completed" not in statuses, (
        "'completed' must NOT be called when run() raises"
    )


async def test_run_status_update_uses_correct_session_id() -> None:
    """The session_id passed to update_status must match the one given to run()."""
    orchestrator = _make_orchestrator(DirectChatLLMClient())
    session_id = uuid4()
    query = SessionUserQuery(text="hello")

    mock_repo = MagicMock()
    mock_repo.update_status = AsyncMock()

    with patch(
        "packages.agent.orchestrator.session_orchestrator.DecisionSessionRepository",
        return_value=mock_repo,
    ):
        await orchestrator.run(session_id, query)
        await asyncio.sleep(0)

    for call in mock_repo.update_status.call_args_list:
        called_session_id = call.args[0]
        assert called_session_id == str(session_id), (
            f"update_status called with wrong session_id: {called_session_id!r}"
        )


async def test_db_error_does_not_propagate() -> None:
    """If update_status raises (e.g. DB not configured), run() must still succeed."""
    orchestrator = _make_orchestrator(DirectChatLLMClient())
    session_id = uuid4()
    query = SessionUserQuery(text="hello")

    mock_repo = MagicMock()
    mock_repo.update_status = AsyncMock(side_effect=RuntimeError("no DATABASE_URL"))

    with patch(
        "packages.agent.orchestrator.session_orchestrator.DecisionSessionRepository",
        return_value=mock_repo,
    ):
        # Must not raise even though update_status always fails
        response = await orchestrator.run(session_id, query)
        await asyncio.sleep(0)

    assert response is not None
