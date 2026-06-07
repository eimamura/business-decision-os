"""T-391: Unit tests for the duplicate-tool detection guard in AgentRuntime._should_continue().

The guard inspects state["tool_results"] for repeated tool names and forces
an early transition to "verify_findings" before _MAX_ITERATIONS is reached.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

from packages.agent.runtime import AgentRuntime, _LCResponse


class _FakeToolRegistry:
    def __init__(self, tools: list[Any] | None = None) -> None:
        self._tools = tools or []

    def list_for_role(self, role: str) -> list[Any]:
        return self._tools

    def filter_for_user_role(self, user_role: str, tools: list[Any]) -> list[Any]:
        return tools

    def get(self, name: str) -> Any | None:
        for t in self._tools:
            if getattr(t, "name", None) == name:
                return t
        return None


class _ReadOnlyTool:
    """Stub tool with safety_level='read_only', used for case (b)."""

    name = "x"
    description = "A read-only tool"
    input_schema: dict[str, Any] = {}
    safety_level = "read_only"


def _make_runtime(tool_registry: Any | None = None) -> AgentRuntime:
    """Build an AgentRuntime with minimal mocks (no real LLM backend needed)."""
    registry = MagicMock()
    registry.get.return_value = None  # default: no model
    return AgentRuntime(
        name="test_agent",
        role="control",
        llm_client=None,
        tool_registry=tool_registry or _FakeToolRegistry(),
        sse_queue=None,
        system_prompt="You are a test specialist.",
        model_registry=registry,
    )


def _make_state(
    tool_results: list[dict[str, Any]],
    response: Any | None = None,
    iteration: int = 0,
    pending_hitl_approval_id: str | None = None,
) -> Any:
    """Build a minimal AgentState dict for use in _should_continue() tests."""
    return {
        "messages": [],
        "response": response,
        "input_tokens": 0,
        "output_tokens": 0,
        "cost_usd": 0.0,
        "tool_results": tool_results,
        "iteration": iteration,
        "status": "running",
        "error": None,
        "pending_hitl_approval_id": pending_hitl_approval_id,
        "pending_hitl_job_id": None,
        "compressed_messages": None,
    }


# ---------------------------------------------------------------------------
# T-391 (a): duplicate tool in tool_results → "verify_findings"
# ---------------------------------------------------------------------------


def test_should_continue_duplicate_tool_returns_verify_findings() -> None:
    """When state["tool_results"] contains the same tool name twice,
    _should_continue() must return "verify_findings" (duplicate-tool guard fires)."""
    tool_results = [
        {"list_stockout_risk": {}},
        {"list_stockout_risk": {}},
    ]
    # Provide a non-None response with a tool_call and finish_reason="tool_use"
    # so the only reason to return "verify_findings" is the duplicate-tool guard.
    response = _LCResponse(
        text="",
        tool_calls=[{"name": "list_stockout_risk", "id": "call_001", "input": {}}],
        finish_reason="tool_use",
    )
    state = _make_state(tool_results=tool_results, response=response, iteration=1)
    runtime = _make_runtime()

    result = runtime._should_continue(state)  # type: ignore[arg-type]

    assert result == "verify_findings", (
        f"Expected 'verify_findings' for duplicate tool, got {result!r}"
    )


# ---------------------------------------------------------------------------
# T-391 (b): single tool call, finish_reason="tool_use" → "execute_tools"
# ---------------------------------------------------------------------------


def test_should_continue_single_tool_returns_execute_tools() -> None:
    """When state["tool_results"] has the tool only once and the response has
    tool_calls + finish_reason='tool_use', _should_continue() returns 'execute_tools'."""
    tool = _ReadOnlyTool()
    registry = _FakeToolRegistry([tool])

    tool_results = [{"list_stockout_risk": {}}]
    response = _LCResponse(
        text="",
        tool_calls=[{"name": "x", "id": "call_001", "input": {}}],
        finish_reason="tool_use",
    )
    state = _make_state(tool_results=tool_results, response=response, iteration=1)
    runtime = _make_runtime(tool_registry=registry)

    result = runtime._should_continue(state)  # type: ignore[arg-type]

    assert result == "execute_tools", (
        f"Expected 'execute_tools' for single tool call, got {result!r}"
    )
