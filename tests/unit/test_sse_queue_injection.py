from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from packages.agent.llm import LLMMessage, LLMResponse
from packages.agent.orchestrator.models import SpecialistTask
from packages.agent.runtime import AgentRuntime
from tests.unit.helpers import (
    FakeLCModel,
    RecordingLLMClient,
    make_llm_usage,
    make_model_registry,
    make_stop_response,
)


def _tool_use_response(tool_name: str, tool_input: dict[str, Any]) -> LLMResponse:
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


class _FakeReadOnlyTool:
    name = "nl_query"
    description = "Run SQL"
    input_schema: dict[str, Any] = {}
    output_schema: dict[str, Any] = {}
    safety_level = "read_only"

    async def handle(self, input: dict[str, Any], ctx: Any) -> Any:
        from packages.tools.base import ToolResult
        return ToolResult(output={"rows": [{"id": 1}]}, audit_payload={})


class _FakeHITLTool:
    name = "request_approval"
    description = "Requests approval"
    input_schema: dict[str, Any] = {}
    output_schema: dict[str, Any] = {}
    safety_level = "hitl"

    async def handle(self, input: dict[str, Any], ctx: Any) -> Any:
        raise AssertionError("handle() must not be called for hitl tool")


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
        self.user_role = "analyst"
        self.actor = "test-user"


def _make_task(allowed_tools: list[str]) -> SpecialistTask:
    return SpecialistTask(
        task_id=uuid4(),
        instruction="Test instruction",
        context_payload={},
        allowed_tools=allowed_tools,
    )


def _make_run_config(
    task: SpecialistTask,
    ctx: _FakeToolContext,
    llm_tools: list[Any],
    sse_queue: Any,
) -> dict[str, Any]:
    import uuid
    return {
        "configurable": {
            "thread_id": str(uuid.uuid4()),
            "task": task,
            "ctx": ctx,
            "llm_tools": llm_tools,
            "sse_queue": sse_queue,
        }
    }


def _make_initial_state() -> Any:
    from packages.agent.runtime import AgentState
    return AgentState(
        messages=[
            LLMMessage(role="system", content="Test system"),
            LLMMessage(role="user", content="Run SQL"),
        ],
        response=None,
        input_tokens=0,
        output_tokens=0,
        cost_usd=0.0,
        tool_results=[],
        iteration=0,
        status="running",
        error=None,
        pending_hitl_approval_id=None,
        pending_hitl_job_id=None,
        compressed_messages=None,
    )


# ---------------------------------------------------------------------------
# T-070: sse_queue from config["configurable"]["sse_queue"] is used in nodes
# ---------------------------------------------------------------------------


async def test_t070_tool_events_pushed_to_config_sse_queue() -> None:
    """When sse_queue is injected via config['configurable']['sse_queue'],
    the execute_tools node must push tool_started and tool_completed events
    to that queue — even if AgentRuntime was constructed with sse_queue=None."""
    from langgraph.checkpoint.memory import MemorySaver

    from packages.agent.llm import LLMToolSpec

    config_queue: asyncio.Queue[Any] = asyncio.Queue()
    constructor_queue: asyncio.Queue[Any] = asyncio.Queue()

    lc_model = FakeLCModel([
        _tool_use_response("nl_query", {}),
        make_stop_response("Query complete."),
        make_stop_response("pass"),
    ])
    registry = _FakeToolRegistry([_FakeReadOnlyTool()])

    # Runtime constructed with constructor_queue — nodes must NOT use it
    runtime = AgentRuntime(
        name="test_agent",
        role="data_engineer",
        llm_client=MagicMock(),
        tool_registry=registry,
        sse_queue=constructor_queue,
        system_prompt="You are a test specialist.",
        model_registry=make_model_registry(lc_model),
    )

    task = _make_task(allowed_tools=["nl_query"])
    ctx = _FakeToolContext()

    llm_tools = [
        LLMToolSpec(name=t.name, description=t.description, input_schema=t.input_schema)
        for t in registry.list_for_role("data_engineer")
        if t.name in {"nl_query"}
    ]
    checkpointer = MemorySaver()
    graph = runtime._build_graph(checkpointer)
    run_config = _make_run_config(task, ctx, llm_tools, sse_queue=config_queue)

    await graph.ainvoke(_make_initial_state(), config=run_config)

    # config_queue must have received SSE events
    config_events: list[dict[str, Any]] = []
    while not config_queue.empty():
        config_events.append(await config_queue.get())

    config_types = [e.get("type") for e in config_events]
    # P20: tool_started/tool_completed replaced by graph_node (kind="tool") events
    assert "graph_node" in config_types, (
        f"Expected 'graph_node' in config_queue events, got: {config_types}"
    )
    tool_events = [e for e in config_events if e.get("type") == "graph_node" and e.get("kind") == "tool"]
    assert len(tool_events) >= 2, (
        f"Expected at least 2 tool graph_node events (start+end), got: {tool_events}"
    )

    # constructor_queue must NOT have received any events (nodes bypass it)
    constructor_events: list[dict[str, Any]] = []
    while not constructor_queue.empty():
        constructor_events.append(await constructor_queue.get())

    assert constructor_events == [], (
        f"constructor_queue must NOT receive events from graph nodes, "
        f"got: {[e.get('type') for e in constructor_events]}"
    )


async def test_t070_hitl_events_pushed_to_config_sse_queue() -> None:
    """When a HITL tool is triggered, awaiting_approval and session_paused events
    must be pushed to config['configurable']['sse_queue']."""
    from langgraph.checkpoint.memory import MemorySaver

    from packages.agent.llm import LLMToolSpec

    config_queue: asyncio.Queue[Any] = asyncio.Queue()

    tool_input = {"action_summary": "Critical action"}
    lc_model_hitl = FakeLCModel([_tool_use_response("request_approval", tool_input)])
    registry = _FakeToolRegistry([_FakeHITLTool()])

    runtime = AgentRuntime(
        name="test_agent",
        role="data_engineer",
        llm_client=MagicMock(),
        tool_registry=registry,
        sse_queue=None,
        system_prompt="You are a test specialist.",
        model_registry=make_model_registry(lc_model_hitl),
    )

    task = _make_task(allowed_tools=["request_approval"])
    ctx = _FakeToolContext()

    mock_repo = MagicMock()
    mock_repo.create = AsyncMock(return_value={"id": str(uuid4())})

    llm_tools = [
        LLMToolSpec(name=t.name, description=t.description, input_schema=t.input_schema)
        for t in registry.list_for_role("data_engineer")
        if t.name in {"request_approval"}
    ]
    checkpointer = MemorySaver()
    graph = runtime._build_graph(checkpointer)
    run_config = _make_run_config(task, ctx, llm_tools, sse_queue=config_queue)

    initial_state = _make_initial_state()
    initial_state["messages"] = [
        LLMMessage(role="system", content="Test"),
        LLMMessage(role="user", content="Approve action"),
    ]

    with patch(
        "packages.persistence.approvals_repo.ApprovalsRepository",
        return_value=mock_repo,
    ):
        await graph.ainvoke(initial_state, config=run_config)

    events: list[dict[str, Any]] = []
    while not config_queue.empty():
        events.append(await config_queue.get())

    event_types = [e.get("type") for e in events]
    assert "awaiting_approval" in event_types, (
        f"Expected 'awaiting_approval' in config_queue, got: {event_types}"
    )
    assert "session_paused" in event_types, (
        f"Expected 'session_paused' in config_queue, got: {event_types}"
    )


async def test_t070_no_sse_queue_in_config_does_not_crash() -> None:
    """When sse_queue is None in config, graph nodes must not crash —
    they must silently skip SSE emission."""
    from langgraph.checkpoint.memory import MemorySaver

    from packages.agent.llm import LLMToolSpec

    lc_model_no_sse = FakeLCModel([
        _tool_use_response("nl_query", {}),
        make_stop_response("Query completed successfully with results."),
    ])
    registry = _FakeToolRegistry([_FakeReadOnlyTool()])

    runtime = AgentRuntime(
        name="test_agent",
        role="data_engineer",
        llm_client=MagicMock(),
        tool_registry=registry,
        sse_queue=None,
        system_prompt="You are a test specialist.",
        model_registry=make_model_registry(lc_model_no_sse),
    )

    task = _make_task(allowed_tools=["nl_query"])
    ctx = _FakeToolContext()

    llm_tools = [
        LLMToolSpec(name=t.name, description=t.description, input_schema=t.input_schema)
        for t in registry.list_for_role("data_engineer")
        if t.name in {"nl_query"}
    ]
    checkpointer = MemorySaver()
    graph = runtime._build_graph(checkpointer)
    run_config = _make_run_config(task, ctx, llm_tools, sse_queue=None)

    result = await graph.ainvoke(_make_initial_state(), config=run_config)
    assert result.get("status") == "completed"
