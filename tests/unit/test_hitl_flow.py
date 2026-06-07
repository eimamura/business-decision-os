from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4


from packages.agent.llm import LLMMessage, LLMResponse, LLMUsage
from packages.agent.orchestrator.models import (
    SessionUserQuery,
    SpecialistTask,
)
from packages.agent.runtime import AgentRuntime
from tests.unit.helpers import (
    FakeLCModel,
    RecordingLLMClient,
    make_llm_usage,
    make_model_registry,
    make_stop_response,
)


def _tool_use_response(tool_name: str, tool_input: dict[str, Any]) -> LLMResponse:
    """LLM response that requests a single tool call."""
    call_id = str(uuid4())
    return LLMResponse(
        text="",
        tool_calls=[{"id": call_id, "name": tool_name, "input": tool_input}],
        finish_reason="tool_use",
        usage=make_llm_usage(),
        model="claude-sonnet-4-6-test",
        request_id=str(uuid4()),
        latency_ms=1,
    )


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
    safety_level = "hitl"

    async def handle(self, input: dict[str, Any], ctx: Any) -> Any:
        # Should never be called — the HITL intercept pauses before reaching handle()
        raise AssertionError("handle() must not be called for a hitl tool")


class _FakeReadOnlyTool:
    """A tool with safety_level == 'read_only'."""

    name = "sql_query"
    description = "Run SQL"
    input_schema: dict[str, Any] = {}
    output_schema: dict[str, Any] = {}
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
    model_registry: Any = None,
) -> AgentRuntime:
    return AgentRuntime(
        name="test_agent",
        role="data_engineer",
        llm_client=llm_client,
        tool_registry=tool_registry,
        sse_queue=None,
        system_prompt="You are a test specialist.",
        model_registry=model_registry,
    )


# ---------------------------------------------------------------------------
# T-066: HITL is now implemented via LangGraph interrupt() — not HITLPause.
# The graph suspends at wait_for_approval and the result contains
# "__interrupt__" in the final state dict.
#
# These tests verify that:
# 1. A HITL tool does NOT call tool.handle()
# 2. The graph produces an "__interrupt__" in its output state
# 3. ApprovalsRepository.create is called before the interrupt
# 4. The graph still handles non-HITL tools normally
# ---------------------------------------------------------------------------


async def test_agent_runtime_hitl_tool_suspends_with_interrupt() -> None:
    """When the LLM requests a hitl tool, AgentRuntime graph must suspend via
    interrupt() — the __interrupt__ key appears in the state output and
    tool.handle() is never called."""
    tool_input = {"action_summary": "Reorder 1000 units of SKU-A"}
    lc_model = FakeLCModel([_tool_use_response("request_approval", tool_input)])
    registry = _FakeToolRegistry([_FakeHITLTool()])
    runtime = _make_runtime(MagicMock(), registry, model_registry=make_model_registry(lc_model))
    task = _make_task()
    ctx = _FakeToolContext()

    # Mock ApprovalsRepository.create to avoid real DB
    mock_repo = MagicMock()
    expected_approval_id = str(uuid4())
    mock_repo.create = AsyncMock(return_value={"id": expected_approval_id})

    # Build and invoke graph directly so we can inspect raw state output
    from langgraph.checkpoint.memory import MemorySaver
    from packages.agent.llm import LLMMessage, LLMToolSpec
    from packages.tools.schema_context import get_schema_context

    schema = get_schema_context()
    system_blocks = [
        {"type": "text", "text": "You are a test specialist.", "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": f"Operational DB schema:\n{schema}" if schema else "", "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": f"Role: data_engineer\nAvailable tools: 1\nAlways respond in the same language the user writes in."},
    ]

    agent_role_tools = registry.list_for_role("data_engineer")
    tool_objects = [t for t in agent_role_tools if t.name in {"request_approval"}]
    llm_tools = [
        LLMToolSpec(name=t.name, description=t.description, input_schema=t.input_schema)
        for t in tool_objects
    ]
    initial_messages = [
        LLMMessage(role="system", content="", content_blocks=system_blocks),
        LLMMessage(role="user", content="Approve action X"),
    ]

    import uuid
    checkpointer = MemorySaver()
    graph = runtime._build_graph(checkpointer)
    thread_id = str(uuid.uuid4())
    run_config: dict[str, Any] = {
        "configurable": {
            "thread_id": thread_id,
            "task": task,
            "ctx": ctx,
            "llm_tools": llm_tools,
            "sse_queue": None,
        }
    }
    from packages.agent.runtime import AgentState
    initial_state: AgentState = {
        "messages": initial_messages,
        "response": None,
        "input_tokens": 0,
        "output_tokens": 0,
        "cost_usd": 0.0,
        "tool_results": [],
        "iteration": 0,
        "status": "running",
        "error": None,
        "pending_hitl_approval_id": None,
        "pending_hitl_job_id": None,
    }

    with patch(
        "packages.persistence.approvals_repo.ApprovalsRepository",
        return_value=mock_repo,
    ):
        result = await graph.ainvoke(initial_state, config=run_config)

    # Graph must have suspended at interrupt()
    assert "__interrupt__" in result, (
        "Expected graph to suspend with __interrupt__ key when HITL tool is encountered"
    )
    interrupt_values = result["__interrupt__"]
    assert len(interrupt_values) >= 1
    assert interrupt_values[0].value.get("tool_name") == "request_approval"


async def test_agent_runtime_hitl_handle_never_called() -> None:
    """tool.handle() must never be called when safety_level == 'hitl'."""
    called: list[bool] = []

    class _SentinelHITLTool(_FakeHITLTool):
        async def handle(self, input: dict[str, Any], ctx: Any) -> Any:
            called.append(True)
            raise AssertionError("should not be called")

    tool_input = {"action_summary": "Send order to supplier"}
    lc_model = FakeLCModel([_tool_use_response("request_approval", tool_input)])
    registry = _FakeToolRegistry([_SentinelHITLTool()])
    runtime = _make_runtime(MagicMock(), registry, model_registry=make_model_registry(lc_model))
    task = _make_task()
    ctx = _FakeToolContext()

    mock_repo = MagicMock()
    mock_repo.create = AsyncMock(return_value={"id": str(uuid4())})

    from langgraph.checkpoint.memory import MemorySaver
    from packages.agent.llm import LLMMessage, LLMToolSpec
    from packages.tools.schema_context import get_schema_context

    schema = get_schema_context()
    system_blocks = [
        {"type": "text", "text": "You are a test specialist.", "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": "", "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": "Role: data_engineer\nAvailable tools: 1\nAlways respond in the same language the user writes in."},
    ]
    llm_tools = [
        LLMToolSpec(name=t.name, description=t.description, input_schema=t.input_schema)
        for t in registry.list_for_role("data_engineer")
    ]
    initial_messages = [
        LLMMessage(role="system", content="", content_blocks=system_blocks),
        LLMMessage(role="user", content="Approve action X"),
    ]

    import uuid
    checkpointer = MemorySaver()
    graph = runtime._build_graph(checkpointer)
    run_config: dict[str, Any] = {
        "configurable": {
            "thread_id": str(uuid.uuid4()),
            "task": task,
            "ctx": ctx,
            "llm_tools": llm_tools,
            "sse_queue": None,
        }
    }
    from packages.agent.runtime import AgentState
    initial_state: AgentState = {
        "messages": initial_messages,
        "response": None,
        "input_tokens": 0,
        "output_tokens": 0,
        "cost_usd": 0.0,
        "tool_results": [],
        "iteration": 0,
        "status": "running",
        "error": None,
        "pending_hitl_approval_id": None,
        "pending_hitl_job_id": None,
    }

    with patch(
        "packages.persistence.approvals_repo.ApprovalsRepository",
        return_value=mock_repo,
    ):
        result = await graph.ainvoke(initial_state, config=run_config)

    # handle() must not have been called
    assert called == [], "handle() must not have been called for a HITL tool"
    # Graph must have suspended
    assert "__interrupt__" in result


async def test_agent_runtime_read_only_tool_does_not_interrupt() -> None:
    """read_only tools must proceed normally without interrupting."""
    lc_model = FakeLCModel([
        _tool_use_response("sql_query", {}),
        make_stop_response("Query complete"),
        make_stop_response("pass"),
    ])
    registry = _FakeToolRegistry([_FakeReadOnlyTool()])
    runtime = _make_runtime(MagicMock(), registry, model_registry=make_model_registry(lc_model))
    task = _make_task(allowed_tools=["sql_query"])
    ctx = _FakeToolContext()

    # Non-HITL tool should complete normally (no interrupt)
    result = await runtime.run(task, ctx)
    assert result is not None
    assert result.status == "completed"


async def test_agent_runtime_hitl_approval_id_from_repo() -> None:
    """ApprovalsRepository.create must be called during prepare_hitl and
    the approval_id stored in graph state must match the repo return value."""
    expected_id = "approval-from-db-001"
    tool_input = {"action_summary": "Critical action"}

    lc_model = FakeLCModel([_tool_use_response("request_approval", tool_input)])
    registry = _FakeToolRegistry([_FakeHITLTool()])
    runtime = _make_runtime(MagicMock(), registry, model_registry=make_model_registry(lc_model))
    task = _make_task()
    ctx = _FakeToolContext()

    mock_repo = MagicMock()
    mock_repo.create = AsyncMock(return_value={"id": expected_id})

    from langgraph.checkpoint.memory import MemorySaver
    from packages.agent.llm import LLMMessage, LLMToolSpec

    system_blocks = [
        {"type": "text", "text": "You are a test specialist.", "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": "", "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": "Role: data_engineer\nAvailable tools: 1\nAlways respond in the same language the user writes in."},
    ]
    llm_tools = [
        LLMToolSpec(name=t.name, description=t.description, input_schema=t.input_schema)
        for t in registry.list_for_role("data_engineer")
    ]
    import uuid
    checkpointer = MemorySaver()
    graph = runtime._build_graph(checkpointer)
    run_config: dict[str, Any] = {
        "configurable": {
            "thread_id": str(uuid.uuid4()),
            "task": task,
            "ctx": ctx,
            "llm_tools": llm_tools,
            "sse_queue": None,
        }
    }
    from packages.agent.runtime import AgentState
    initial_state: AgentState = {
        "messages": [
            LLMMessage(role="system", content="", content_blocks=system_blocks),
            LLMMessage(role="user", content="Approve action X"),
        ],
        "response": None,
        "input_tokens": 0,
        "output_tokens": 0,
        "cost_usd": 0.0,
        "tool_results": [],
        "iteration": 0,
        "status": "running",
        "error": None,
        "pending_hitl_approval_id": None,
        "pending_hitl_job_id": None,
    }

    with patch(
        "packages.persistence.approvals_repo.ApprovalsRepository",
        return_value=mock_repo,
    ):
        result = await graph.ainvoke(initial_state, config=run_config)

    # Graph must have suspended with approval_id from repo in interrupt value
    assert "__interrupt__" in result
    interrupt_value = result["__interrupt__"][0].value
    assert interrupt_value.get("approval_id") == expected_id


async def test_agent_runtime_hitl_fallback_uuid_on_repo_error() -> None:
    """If ApprovalsRepository.create fails, graph must still suspend with a
    non-empty UUID fallback as the approval_id."""
    tool_input = {"action_summary": "Action with DB error"}

    lc_model = FakeLCModel([_tool_use_response("request_approval", tool_input)])
    registry = _FakeToolRegistry([_FakeHITLTool()])
    runtime = _make_runtime(MagicMock(), registry, model_registry=make_model_registry(lc_model))
    task = _make_task()
    ctx = _FakeToolContext()

    mock_repo = MagicMock()
    mock_repo.create = AsyncMock(side_effect=RuntimeError("DB unavailable"))

    from langgraph.checkpoint.memory import MemorySaver
    from packages.agent.llm import LLMMessage, LLMToolSpec

    system_blocks = [
        {"type": "text", "text": "You are a test specialist.", "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": "", "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": "Role: data_engineer\nAvailable tools: 1\nAlways respond in the same language the user writes in."},
    ]
    llm_tools = [
        LLMToolSpec(name=t.name, description=t.description, input_schema=t.input_schema)
        for t in registry.list_for_role("data_engineer")
    ]
    import uuid
    checkpointer = MemorySaver()
    graph = runtime._build_graph(checkpointer)
    run_config: dict[str, Any] = {
        "configurable": {
            "thread_id": str(uuid.uuid4()),
            "task": task,
            "ctx": ctx,
            "llm_tools": llm_tools,
            "sse_queue": None,
        }
    }
    from packages.agent.runtime import AgentState
    initial_state: AgentState = {
        "messages": [
            LLMMessage(role="system", content="", content_blocks=system_blocks),
            LLMMessage(role="user", content="Approve action X"),
        ],
        "response": None,
        "input_tokens": 0,
        "output_tokens": 0,
        "cost_usd": 0.0,
        "tool_results": [],
        "iteration": 0,
        "status": "running",
        "error": None,
        "pending_hitl_approval_id": None,
        "pending_hitl_job_id": None,
    }

    with patch(
        "packages.persistence.approvals_repo.ApprovalsRepository",
        return_value=mock_repo,
    ):
        result = await graph.ainvoke(initial_state, config=run_config)

    # Graph must still suspend even when repo errors out
    assert "__interrupt__" in result
    interrupt_value = result["__interrupt__"][0].value
    # approval_id must be a non-empty string (UUID fallback)
    approval_id = interrupt_value.get("approval_id")
    assert isinstance(approval_id, str)
    assert len(approval_id) > 0


# ---------------------------------------------------------------------------
# T-066: SessionOrchestrator no longer catches HITLPause.
# The HITL interrupt is emitted from inside the graph via SSE events.
# These tests verify the orchestrator handles the normal (non-HITL) path
# and that the HITLPause-based except block is gone.
# ---------------------------------------------------------------------------


async def test_session_orchestrator_has_no_hitl_pause_catch_block() -> None:
    """SessionOrchestrator.run() must not reference HITLPause anywhere.
    Verify by confirming that raising HITLPause-like errors from inside
    the run() call propagates as a general Exception (not specially handled)."""
    import inspect
    from packages.agent.orchestrator.session_orchestrator import SessionOrchestrator

    source = inspect.getsource(SessionOrchestrator.run)
    assert "HITLPause" not in source, (
        "SessionOrchestrator.run() must not catch HITLPause — "
        "HITL is now handled via LangGraph interrupt() inside AgentRuntime"
    )


async def test_session_orchestrator_awaiting_approval_status_via_sse() -> None:
    """When a HITL tool is triggered, the graph emits 'awaiting_approval' and
    'session_paused' SSE events without the orchestrator needing to catch HITLPause."""
    import asyncio as _asyncio
    from packages.agent.runtime import AgentRuntime

    sse_events: list[dict[str, Any]] = []

    async def _collect_sse() -> None:
        pass  # SSE events are recorded by the queue

    sse_queue: asyncio.Queue[Any] = asyncio.Queue()

    tool_input = {"action_summary": "Approve something"}
    lc_model = FakeLCModel([_tool_use_response("request_approval", tool_input)])
    registry = _FakeToolRegistry([_FakeHITLTool()])

    runtime = AgentRuntime(
        name="test_agent",
        role="data_engineer",
        llm_client=MagicMock(),
        tool_registry=registry,
        sse_queue=sse_queue,
        system_prompt="You are a test specialist.",
        model_registry=make_model_registry(lc_model),
    )
    task = _make_task()
    ctx = _FakeToolContext()

    mock_repo = MagicMock()
    approval_id = str(uuid4())
    mock_repo.create = AsyncMock(return_value={"id": approval_id})

    from langgraph.checkpoint.memory import MemorySaver
    from packages.agent.llm import LLMMessage, LLMToolSpec

    system_blocks = [
        {"type": "text", "text": "You are a test specialist.", "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": "", "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": "Role: data_engineer\nAvailable tools: 1\nAlways respond in the same language the user writes in."},
    ]
    llm_tools = [
        LLMToolSpec(name=t.name, description=t.description, input_schema=t.input_schema)
        for t in registry.list_for_role("data_engineer")
    ]
    import uuid
    checkpointer = MemorySaver()
    graph = runtime._build_graph(checkpointer)
    run_config: dict[str, Any] = {
        "configurable": {
            "thread_id": str(uuid.uuid4()),
            "task": task,
            "ctx": ctx,
            "llm_tools": llm_tools,
            "sse_queue": sse_queue,
        }
    }
    from packages.agent.runtime import AgentState
    initial_state: AgentState = {
        "messages": [
            LLMMessage(role="system", content="", content_blocks=system_blocks),
            LLMMessage(role="user", content="Approve action X"),
        ],
        "response": None,
        "input_tokens": 0,
        "output_tokens": 0,
        "cost_usd": 0.0,
        "tool_results": [],
        "iteration": 0,
        "status": "running",
        "error": None,
        "pending_hitl_approval_id": None,
        "pending_hitl_job_id": None,
    }

    with patch(
        "packages.persistence.approvals_repo.ApprovalsRepository",
        return_value=mock_repo,
    ):
        await graph.ainvoke(initial_state, config=run_config)

    # Collect all SSE events from the queue
    while not sse_queue.empty():
        sse_events.append(await sse_queue.get())

    event_types = [e.get("type") for e in sse_events]
    assert "awaiting_approval" in event_types, (
        f"Expected 'awaiting_approval' SSE event, got: {event_types}"
    )
    assert "session_paused" in event_types, (
        f"Expected 'session_paused' SSE event, got: {event_types}"
    )
