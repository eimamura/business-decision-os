"""T-418: Assert parallel tool execution behaviour in AgentRuntime._execute_tools_node.

Gap 2 — P64 B-04 (T-412): Non-HITL tool calls must be executed via asyncio.gather();
HITL tool calls must remain sequential (not gathered).
"""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

from packages.agent.runtime import AgentRuntime, _LCResponse
from packages.tools.base import ToolContext, ToolResult


class _ReadOnlyTool:
    """Stub read-only tool."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.description = "A read-only tool"
        self.input_schema: dict[str, Any] = {}
        self.safety_level = "read_only"
        self.call_count = 0

    async def handle(self, input: dict[str, Any], ctx: Any) -> ToolResult:
        self.call_count += 1
        return ToolResult(output={"result": f"ok_{self.name}"}, audit_payload={})


class _HitlTool:
    """Stub HITL tool (safety_level='hitl')."""

    def __init__(self) -> None:
        self.name = "hitl_action"
        self.description = "A write/HITL tool"
        self.input_schema: dict[str, Any] = {}
        self.safety_level = "hitl"
        self.call_count = 0

    async def handle(self, input: dict[str, Any], ctx: Any) -> ToolResult:
        self.call_count += 1
        return ToolResult(output={"result": "hitl_ok"}, audit_payload={})


class _FakeToolRegistry:
    def __init__(self, tools: list[Any]) -> None:
        self._tools_map = {t.name: t for t in tools}

    def list_for_role(self, role: str) -> list[Any]:
        return list(self._tools_map.values())

    def filter_for_user_role(self, user_role: str, tools: list[Any]) -> list[Any]:
        return tools

    def get(self, name: str) -> Any | None:
        return self._tools_map.get(name)


def _make_state(response: Any, tool_plan: list[Any] | None = None) -> dict[str, Any]:
    from packages.agent.llm import LLMMessage
    return {
        "messages": [LLMMessage(role="user", content="analyze")],
        "response": response,
        "input_tokens": 0,
        "output_tokens": 0,
        "cost_usd": 0.0,
        "tool_results": [],
        "iteration": 0,
        "status": "running",
        "error": None,
        "pending_hitl_approval_id": None,
        "pending_hitl_job_id": None,
        "compressed_messages": None,
        "tool_plan": tool_plan or [],
    }


def _make_tool_response(tool_calls: list[dict[str, Any]]) -> _LCResponse:
    return _LCResponse(
        text="",
        tool_calls=tool_calls,
        finish_reason="tool_use",
        model="test-model",
        input_tokens=0,
        output_tokens=0,
    )


def _make_ctx() -> ToolContext:
    return ToolContext(
        session_id=uuid4(),
        agent_step_id=uuid4(),
        specialist_role="control",
        actor="test-user",
        correlation_id=uuid4(),
        user_role="analyst",
    )


def _make_runtime(tools: list[Any]) -> AgentRuntime:
    registry = MagicMock()
    registry.get.return_value = None
    return AgentRuntime(
        name="test_agent",
        role="control",
        llm_client=None,
        tool_registry=_FakeToolRegistry(tools),
        sse_queue=None,
        system_prompt="Test.",
        model_registry=registry,
    )


async def test_two_read_only_tools_are_both_called() -> None:
    """Two read-only tool calls in a single response must both be executed."""
    tool_a = _ReadOnlyTool("nl_query")
    tool_b = _ReadOnlyTool("list_stockout_risk")
    runtime = _make_runtime([tool_a, tool_b])

    response = _make_tool_response([
        {"id": "call_a", "name": "nl_query", "input": {}},
        {"id": "call_b", "name": "list_stockout_risk", "input": {}},
    ])
    state = _make_state(response)
    ctx = _make_ctx()
    config: dict[str, Any] = {"configurable": {"ctx": ctx, "agent_run_id": "run-1"}}

    await runtime._execute_tools_node(state, config)  # type: ignore[arg-type]

    assert tool_a.call_count == 1, "nl_query was not called"
    assert tool_b.call_count == 1, "list_stockout_risk was not called"


async def test_asyncio_gather_is_called_for_parallel_tools() -> None:
    """asyncio.gather must be invoked when there are parallel (non-HITL) tool calls."""
    tool_a = _ReadOnlyTool("nl_query")
    tool_b = _ReadOnlyTool("list_stockout_risk")
    runtime = _make_runtime([tool_a, tool_b])

    response = _make_tool_response([
        {"id": "call_a", "name": "nl_query", "input": {}},
        {"id": "call_b", "name": "list_stockout_risk", "input": {}},
    ])
    state = _make_state(response)
    ctx = _make_ctx()
    config: dict[str, Any] = {"configurable": {"ctx": ctx, "agent_run_id": "run-1"}}

    gather_called = False
    original_gather = asyncio.gather

    async def _spy_gather(*coros: Any, **kwargs: Any) -> Any:
        nonlocal gather_called
        gather_called = True
        return await original_gather(*coros, **kwargs)

    with patch("packages.agent.runtime.asyncio.gather", side_effect=_spy_gather):
        await runtime._execute_tools_node(state, config)  # type: ignore[arg-type]

    assert gather_called, "asyncio.gather was not called for parallel tool calls"


async def test_hitl_tool_is_not_gathered() -> None:
    """A HITL tool call must remain in hitl_calls and not be passed to asyncio.gather."""
    hitl = _HitlTool()
    runtime = _make_runtime([hitl])

    response = _make_tool_response([
        {"id": "call_h", "name": "hitl_action", "input": {}},
    ])
    state = _make_state(response)
    ctx = _make_ctx()
    config: dict[str, Any] = {"configurable": {"ctx": ctx, "agent_run_id": "run-1"}}

    gather_called = False
    original_gather = asyncio.gather

    async def _spy_gather(*coros: Any, **kwargs: Any) -> Any:
        nonlocal gather_called
        gather_called = True
        return await original_gather(*coros, **kwargs)

    with patch("packages.agent.runtime.asyncio.gather", side_effect=_spy_gather):
        # HITL tools with pending_hitl_approval_id=None go to sequential path
        # The node should NOT call asyncio.gather for this tool
        await runtime._execute_tools_node(state, config)  # type: ignore[arg-type]

    assert not gather_called, (
        "asyncio.gather was called for a HITL tool — HITL must remain sequential"
    )
