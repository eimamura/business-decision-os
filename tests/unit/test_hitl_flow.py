from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from packages.agent.llm import LLMMessage, LLMResponse, LLMUsage
from packages.agent.orchestrator.hitl import HITLPause
from packages.agent.orchestrator.models import (
    SessionUserQuery,
    SpecialistTask,
)
from packages.agent.runtime import AgentRuntime


# ---------------------------------------------------------------------------
# Helpers / fakes
# ---------------------------------------------------------------------------


def _make_usage() -> LLMUsage:
    return LLMUsage(
        input_tokens=10,
        output_tokens=5,
        total_cost_usd=Decimal("0"),
    )


def _stop_response(text: str = "Done.") -> LLMResponse:
    return LLMResponse(
        text=text,
        tool_calls=[],
        finish_reason="stop",
        usage=_make_usage(),
        model="claude-sonnet-4-6-test",
        request_id=str(uuid4()),
        latency_ms=1,
    )


def _tool_use_response(tool_name: str, tool_input: dict[str, Any]) -> LLMResponse:
    """LLM response that requests a single tool call."""
    call_id = str(uuid4())
    return LLMResponse(
        text="",
        tool_calls=[{"id": call_id, "name": tool_name, "input": tool_input}],
        finish_reason="tool_use",
        usage=_make_usage(),
        model="claude-sonnet-4-6-test",
        request_id=str(uuid4()),
        latency_ms=1,
    )


class _RecordingLLMClient:
    """Returns pre-configured responses in order."""

    def __init__(self, responses: list[LLMResponse]) -> None:
        self._responses = list(responses)
        self._model = "claude-sonnet-4-6-mock"

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
        if not self._responses:
            return _stop_response("fallback")
        return self._responses.pop(0)


class _FakeHITLTool:
    """A tool with safety_level == 'hitl'."""

    name = "request_approval"
    description = "Requests human approval"
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {"action_summary": {"type": "string"}},
        "required": ["action_summary"],
    }
    output_schema: dict[str, Any] = {}
    requires_approval = True
    safety_level = "hitl"

    async def handle(self, input: dict[str, Any], ctx: Any) -> Any:
        # Should never be called — the HITL intercept raises before reaching handle()
        raise AssertionError("handle() must not be called for a hitl tool")


class _FakeReadOnlyTool:
    """A tool with safety_level == 'read_only'."""

    name = "sql_query"
    description = "Run SQL"
    input_schema: dict[str, Any] = {}
    output_schema: dict[str, Any] = {}
    requires_approval = False
    safety_level = "read_only"

    async def handle(self, input: dict[str, Any], ctx: Any) -> Any:
        from packages.tools.base import ToolResult

        return ToolResult(output={"rows": []}, audit_payload={})


class _FakeToolRegistry:
    def __init__(self, tools: list[Any]) -> None:
        self._tools = tools

    def list_for_role(self, role: str) -> list[Any]:
        return self._tools

    def filter_for_user_role(self, user_role: str, tools: list[Any]) -> list[Any]:
        return tools

    def get(self, name: str) -> Any | None:
        for t in self._tools:
            if t.name == name:
                return t
        return None


class _FakeToolContext:
    def __init__(self) -> None:
        self.agent_step_id = uuid4()
        self.session_id = uuid4()
        self.user_id = "test-user"
        self.user_role = "manager"
        self.actor = "test-user"


def _make_task(
    instruction: str = "Approve action X",
    allowed_tools: list[str] | None = None,
) -> SpecialistTask:
    return SpecialistTask(
        task_id=uuid4(),
        instruction=instruction,
        context_payload={},
        allowed_tools=allowed_tools or ["request_approval"],
    )


def _make_runtime(
    llm_client: Any,
    tool_registry: Any,
) -> AgentRuntime:
    return AgentRuntime(
        name="test_agent",
        role="data_engineer",
        llm_client=llm_client,
        tool_registry=tool_registry,
        sse_queue=None,
        system_prompt="You are a test specialist.",
    )


# ---------------------------------------------------------------------------
# Test 1: HITLPause is an Exception with correct fields
# ---------------------------------------------------------------------------


def test_hitl_pause_is_exception() -> None:
    exc = HITLPause(approval_id="abc-123", tool_name="request_approval", tool_input={})
    assert isinstance(exc, Exception)
    assert exc.approval_id == "abc-123"
    assert exc.tool_name == "request_approval"
    assert exc.tool_input == {}


def test_hitl_pause_carries_tool_input() -> None:
    payload = {"action_summary": "Delete 500 units"}
    exc = HITLPause(approval_id="xyz", tool_name="request_approval", tool_input=payload)
    assert exc.tool_input == payload


# ---------------------------------------------------------------------------
# Test 2: AgentRuntime raises HITLPause when a hitl tool is called
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_agent_runtime_hitl_tool_raises_pause() -> None:
    """When the LLM requests a hitl tool, AgentRuntime must raise HITLPause."""
    tool_input = {"action_summary": "Reorder 1000 units of SKU-A"}
    llm = _RecordingLLMClient([
        _tool_use_response("request_approval", tool_input),
    ])
    registry = _FakeToolRegistry([_FakeHITLTool()])
    runtime = _make_runtime(llm, registry)
    task = _make_task()
    ctx = _FakeToolContext()

    # Mock ApprovalsRepository.create to avoid real DB
    mock_repo = MagicMock()
    mock_repo.create = AsyncMock(return_value={"id": str(uuid4())})

    with patch(
        "packages.persistence.approvals_repo.ApprovalsRepository",
        return_value=mock_repo,
    ):
        with pytest.raises(HITLPause) as exc_info:
            await runtime.run(task, ctx)

    pause = exc_info.value
    assert pause.tool_name == "request_approval"
    assert pause.tool_input == tool_input


@pytest.mark.asyncio
async def test_agent_runtime_hitl_raises_before_handle() -> None:
    """handle() must never be called when safety_level == 'hitl'."""
    called: list[bool] = []

    class _SentinelHITLTool(_FakeHITLTool):
        async def handle(self, input: dict[str, Any], ctx: Any) -> Any:
            called.append(True)
            raise AssertionError("should not be called")

    tool_input = {"action_summary": "Send order to supplier"}
    llm = _RecordingLLMClient([_tool_use_response("request_approval", tool_input)])
    registry = _FakeToolRegistry([_SentinelHITLTool()])
    runtime = _make_runtime(llm, registry)
    task = _make_task()
    ctx = _FakeToolContext()

    mock_repo = MagicMock()
    mock_repo.create = AsyncMock(return_value={"id": str(uuid4())})

    with patch(
        "packages.persistence.approvals_repo.ApprovalsRepository",
        return_value=mock_repo,
    ):
        with pytest.raises(HITLPause):
            await runtime.run(task, ctx)

    assert called == [], "handle() must not have been called"


@pytest.mark.asyncio
async def test_agent_runtime_read_only_tool_does_not_raise_pause() -> None:
    """read_only tools must proceed normally without raising HITLPause."""
    tool_input: dict[str, Any] = {}
    llm = _RecordingLLMClient([
        _tool_use_response("sql_query", tool_input),
        _stop_response("Query complete"),
    ])
    registry = _FakeToolRegistry([_FakeReadOnlyTool()])
    runtime = _make_runtime(llm, registry)
    task = _make_task(allowed_tools=["sql_query"])
    ctx = _FakeToolContext()

    # No HITLPause should be raised
    result = await runtime.run(task, ctx)
    assert result is not None


@pytest.mark.asyncio
async def test_agent_runtime_hitl_pause_carries_approval_id_from_repo() -> None:
    """The approval_id on HITLPause must come from ApprovalsRepository.create."""
    expected_id = "approval-from-db-001"
    tool_input = {"action_summary": "Critical action"}

    llm = _RecordingLLMClient([_tool_use_response("request_approval", tool_input)])
    registry = _FakeToolRegistry([_FakeHITLTool()])
    runtime = _make_runtime(llm, registry)
    task = _make_task()
    ctx = _FakeToolContext()

    mock_repo = MagicMock()
    mock_repo.create = AsyncMock(return_value={"id": expected_id})

    with patch(
        "packages.persistence.approvals_repo.ApprovalsRepository",
        return_value=mock_repo,
    ):
        with pytest.raises(HITLPause) as exc_info:
            await runtime.run(task, ctx)

    assert exc_info.value.approval_id == expected_id


@pytest.mark.asyncio
async def test_agent_runtime_hitl_fallback_uuid_on_repo_error() -> None:
    """If ApprovalsRepository.create fails, HITLPause must still be raised with a UUID."""
    tool_input = {"action_summary": "Action with DB error"}

    llm = _RecordingLLMClient([_tool_use_response("request_approval", tool_input)])
    registry = _FakeToolRegistry([_FakeHITLTool()])
    runtime = _make_runtime(llm, registry)
    task = _make_task()
    ctx = _FakeToolContext()

    mock_repo = MagicMock()
    mock_repo.create = AsyncMock(side_effect=RuntimeError("DB unavailable"))

    with patch(
        "packages.persistence.approvals_repo.ApprovalsRepository",
        return_value=mock_repo,
    ):
        with pytest.raises(HITLPause) as exc_info:
            await runtime.run(task, ctx)

    # approval_id must be a non-empty string (UUID fallback)
    assert isinstance(exc_info.value.approval_id, str)
    assert len(exc_info.value.approval_id) > 0


# ---------------------------------------------------------------------------
# Test 3: SessionOrchestrator catches HITLPause and returns correct response
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_session_orchestrator_catches_hitl_pause() -> None:
    """SessionOrchestrator.run() must catch HITLPause and return SessionResponse
    with requires_approval=True and mode='direct_chat'."""
    from packages.agent.orchestrator import SessionOrchestrator
    from packages.memory import StubMemoryStore
    from packages.tools import create_tool_registry

    approval_id = str(uuid4())

    class _HITLLLMClient:
        _model = "stub"

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
            system = messages[0].content if messages else ""
            if "intent classifier" in system:
                return LLMResponse(
                    text=(
                        '{"category":"direct_chat","confidence":0.9,'
                        '"rationale":"test","goal_text":"approve something"}'
                    ),
                    tool_calls=[],
                    finish_reason="stop",
                    usage=_make_usage(),
                    model="stub",
                    request_id=str(uuid4()),
                    latency_ms=0,
                )
            if "router inside SessionOrchestrator" in system:
                return LLMResponse(
                    text=(
                        '{"mode":"direct_chat","agents":[],'
                        '"requires_planning":false,"requires_dag":false,"rationale":"chat"}'
                    ),
                    tool_calls=[],
                    finish_reason="stop",
                    usage=_make_usage(),
                    model="stub",
                    request_id=str(uuid4()),
                    latency_ms=0,
                )
            # direct_chat response triggers HITLPause via injected side_effect
            raise HITLPause(
                approval_id=approval_id,
                tool_name="request_approval",
                tool_input={"action_summary": "Test"},
            )

    orchestrator = SessionOrchestrator(
        llm_client=_HITLLLMClient(),
        tool_registry=create_tool_registry(),
        memory_store=StubMemoryStore(),
    )
    session_id = uuid4()
    query = SessionUserQuery(text="approve action X")

    mock_repo = MagicMock()
    mock_repo.update_status = AsyncMock()

    with patch(
        "packages.agent.orchestrator.session_orchestrator.DecisionSessionRepository",
        return_value=mock_repo,
    ):
        response = await orchestrator.run(session_id, query)
        await asyncio.sleep(0)

    assert response.requires_approval is True
    assert response.mode == "direct_chat"
    assert approval_id in response.reply
    assert "request_approval" in response.reply


@pytest.mark.asyncio
async def test_session_orchestrator_hitl_pause_sets_awaiting_approval_status() -> None:
    """After catching HITLPause, the session status must transition to 'awaiting_approval'."""
    from packages.agent.orchestrator import SessionOrchestrator
    from packages.memory import StubMemoryStore
    from packages.tools import create_tool_registry

    approval_id = str(uuid4())

    class _HITLLLMClient2:
        _model = "stub"

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
            system = messages[0].content if messages else ""
            if "intent classifier" in system:
                return LLMResponse(
                    text=(
                        '{"category":"direct_chat","confidence":0.9,'
                        '"rationale":"test","goal_text":"approve something"}'
                    ),
                    tool_calls=[],
                    finish_reason="stop",
                    usage=_make_usage(),
                    model="stub",
                    request_id=str(uuid4()),
                    latency_ms=0,
                )
            if "router inside SessionOrchestrator" in system:
                return LLMResponse(
                    text=(
                        '{"mode":"direct_chat","agents":[],'
                        '"requires_planning":false,"requires_dag":false,"rationale":"chat"}'
                    ),
                    tool_calls=[],
                    finish_reason="stop",
                    usage=_make_usage(),
                    model="stub",
                    request_id=str(uuid4()),
                    latency_ms=0,
                )
            raise HITLPause(
                approval_id=approval_id,
                tool_name="request_approval",
                tool_input={},
            )

    orchestrator = SessionOrchestrator(
        llm_client=_HITLLLMClient2(),
        tool_registry=create_tool_registry(),
        memory_store=StubMemoryStore(),
    )
    session_id = uuid4()
    query = SessionUserQuery(text="run hitl action")

    mock_repo = MagicMock()
    mock_repo.update_status = AsyncMock()

    with patch(
        "packages.agent.orchestrator.session_orchestrator.DecisionSessionRepository",
        return_value=mock_repo,
    ):
        await orchestrator.run(session_id, query)
        await asyncio.sleep(0)

    statuses = [c.args[1] for c in mock_repo.update_status.call_args_list]
    assert "awaiting_approval" in statuses, (
        f"Expected 'awaiting_approval' status, got: {statuses}"
    )
    assert "failed" not in statuses, (
        "Session must NOT be marked 'failed' when HITLPause is caught"
    )
