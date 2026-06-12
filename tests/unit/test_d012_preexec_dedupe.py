"""D-012 — Pre-execution tool-call dedupe and loop message cap (unit tests).

Tests:
  T-D012-a  _tool_fingerprint returns stable name:args string
  T-D012-b  _execute_tools_node skips a duplicate call (same name+args already seen)
            and appends a cached-reference message instead of re-executing the tool
  T-D012-c  _execute_tools_node accumulates new fingerprints in seen_tool_fingerprints
  T-D012-d  Tool-result message content is capped at _LOOP_TOOL_RESULT_MESSAGE_MAX_CHARS
  T-D012-e  _should_continue still fires the post-execution guard when duplicates slip
            through (backward-compatibility: post-exec guard is NOT removed)
  T-D012-f  AgentRuntime.run() sets peak_input_tokens in usage to the max single-call
            input_tokens value (not the operator.add SUM); this is the authoritative
            saturation signal for the ≤90% context-overflow check (D-012 fix).
  T-D012-g  _should_continue routes to synthesize_from_tools when ALL pending tool calls
            are already in seen_tool_fingerprints (pre-execution routing guard — prevents
            infinite loop when model keeps requesting already-executed tools).
"""
from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from packages.agent.runtime import (
    AgentRuntime,
    _LOOP_TOOL_RESULT_MESSAGE_MAX_CHARS,
    _LCResponse,
)
from packages.tools.base import ToolResult


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


class _EchoTool:
    """Tool that returns whatever is passed in the 'value' input key."""

    def __init__(self, name: str, output: dict[str, Any] | None = None) -> None:
        self.name = name
        self.description = f"Echo tool {name}"
        self.input_schema: dict[str, Any] = {}
        self.safety_level = "read_only"
        self._output = output or {"count": 1, "items": ["SKU-001"]}
        self.call_count = 0

    async def handle(self, input: dict[str, Any], ctx: Any) -> ToolResult:
        self.call_count += 1
        return ToolResult(output=self._output, audit_payload={})


class _LargeOutputTool:
    """Tool that returns output larger than _LOOP_TOOL_RESULT_MESSAGE_MAX_CHARS."""

    name = "large_tool"
    description = "Returns large output"
    input_schema: dict[str, Any] = {}
    safety_level = "read_only"
    call_count = 0

    async def handle(self, input: dict[str, Any], ctx: Any) -> ToolResult:
        self.call_count += 1
        # Generate output larger than the cap
        big_value = "x" * (_LOOP_TOOL_RESULT_MESSAGE_MAX_CHARS + 1000)
        return ToolResult(output={"data": big_value}, audit_payload={})


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


class _FakeCtx:
    def __init__(self) -> None:
        self.agent_step_id = uuid4()
        self.session_id = uuid4()
        self.user_role = "analyst"


def _make_runtime(tools: list[Any]) -> AgentRuntime:
    registry = MagicMock()
    registry.get.return_value = None
    return AgentRuntime(
        name="test_agent",
        role="control",
        llm_client=None,
        tool_registry=_FakeToolRegistry(tools),
        sse_queue=None,
        system_prompt="You are a test specialist.",
        model_registry=registry,
    )


def _make_state(
    tool_calls: list[dict[str, Any]],
    seen_tool_fingerprints: list[str] | None = None,
) -> dict[str, Any]:
    from packages.agent.runtime import _LCResponse

    response = _LCResponse(
        text="",
        tool_calls=tool_calls,
        finish_reason="tool_use",
    )
    return {
        "messages": [],
        "response": response,
        "input_tokens": 0,
        "output_tokens": 0,
        "cost_usd": 0.0,
        "tool_results": [],
        "iteration": 1,
        "status": "running",
        "error": None,
        "blocked_reason": None,
        "pending_hitl_approval_id": None,
        "pending_hitl_job_id": None,
        "compressed_messages": None,
        "tool_plan": [],
        "groundedness": None,
        "revised": False,
        "loop_guard_triggered": False,
        "seen_tool_fingerprints": seen_tool_fingerprints or [],
    }


def _make_config(ctx: _FakeCtx) -> dict[str, Any]:
    return {
        "configurable": {
            "ctx": ctx,
            "sse_queue": None,
            "event_persister": None,
            "agent_run_id": "test-run",
        }
    }


# ---------------------------------------------------------------------------
# T-D012-a: _tool_fingerprint stability
# ---------------------------------------------------------------------------


def test_tool_fingerprint_stable_for_same_call() -> None:
    """_tool_fingerprint must return the same string for identical name+args."""
    runtime = _make_runtime([])
    call = {"name": "list_stockout_risk", "id": "call_001", "input": {"horizon_days": 7}}
    fp1 = runtime._tool_fingerprint(call)
    fp2 = runtime._tool_fingerprint(call)
    assert fp1 == fp2, "fingerprint is not stable for identical calls"


def test_tool_fingerprint_differs_for_different_args() -> None:
    """_tool_fingerprint must differ when args change."""
    runtime = _make_runtime([])
    call_7 = {"name": "list_stockout_risk", "id": "call_001", "input": {"horizon_days": 7}}
    call_14 = {"name": "list_stockout_risk", "id": "call_002", "input": {"horizon_days": 14}}
    assert runtime._tool_fingerprint(call_7) != runtime._tool_fingerprint(call_14)


def test_tool_fingerprint_differs_for_different_names() -> None:
    """_tool_fingerprint must differ when tool names differ even with same args."""
    runtime = _make_runtime([])
    call_a = {"name": "tool_a", "id": "call_001", "input": {}}
    call_b = {"name": "tool_b", "id": "call_002", "input": {}}
    assert runtime._tool_fingerprint(call_a) != runtime._tool_fingerprint(call_b)


def test_tool_fingerprint_arg_order_insensitive() -> None:
    """_tool_fingerprint must produce the same result regardless of dict key order."""
    runtime = _make_runtime([])
    call_ab = {"name": "tool", "id": "x", "input": {"a": 1, "b": 2}}
    call_ba = {"name": "tool", "id": "y", "input": {"b": 2, "a": 1}}
    assert runtime._tool_fingerprint(call_ab) == runtime._tool_fingerprint(call_ba)


# ---------------------------------------------------------------------------
# T-D012-b: duplicate call is skipped, cached-reference message appended
# ---------------------------------------------------------------------------


async def test_execute_tools_skips_duplicate_and_emits_cached_reference() -> None:
    """When a tool call fingerprint is already in seen_tool_fingerprints,
    _execute_tools_node must NOT execute the tool and must append a cached-reference
    LLMMessage with role='tool' and content containing '[cached]'.
    """
    tool = _EchoTool("list_stockout_risk")
    runtime = _make_runtime([tool])
    ctx = _FakeCtx()

    fp = runtime._tool_fingerprint(
        {"name": "list_stockout_risk", "id": "call_001", "input": {}}
    )
    state = _make_state(
        tool_calls=[{"name": "list_stockout_risk", "id": "call_001", "input": {}}],
        seen_tool_fingerprints=[fp],  # already seen
    )
    config = _make_config(ctx)

    result = await runtime._execute_tools_node(state, config)  # type: ignore[arg-type]

    # Tool must NOT have been called
    assert tool.call_count == 0, (
        f"Tool was re-executed despite its fingerprint already being in seen_tool_fingerprints: "
        f"call_count={tool.call_count}"
    )

    # A cached-reference message must have been appended
    messages = result.get("messages", [])
    assert messages, "No messages returned — expected a cached-reference message"
    cached_msg = messages[0]
    assert cached_msg.role == "tool", (
        f"Expected role='tool' on cached-reference message, got {cached_msg.role!r}"
    )
    assert "[cached]" in cached_msg.content, (
        f"Cached-reference message does not contain '[cached]': {cached_msg.content!r}"
    )


# ---------------------------------------------------------------------------
# T-D012-c: new fingerprints are accumulated in the state update
# ---------------------------------------------------------------------------


async def test_execute_tools_accumulates_new_fingerprints() -> None:
    """After executing a fresh (non-duplicate) tool call,
    _execute_tools_node must include its fingerprint in the returned
    seen_tool_fingerprints list.
    """
    tool = _EchoTool("list_stockout_risk")
    runtime = _make_runtime([tool])
    ctx = _FakeCtx()

    call = {"name": "list_stockout_risk", "id": "call_001", "input": {"horizon_days": 7}}
    state = _make_state(tool_calls=[call], seen_tool_fingerprints=[])
    config = _make_config(ctx)

    result = await runtime._execute_tools_node(state, config)  # type: ignore[arg-type]

    expected_fp = runtime._tool_fingerprint(call)
    new_fps = result.get("seen_tool_fingerprints", [])
    assert expected_fp in new_fps, (
        f"Expected fingerprint {expected_fp!r} in returned seen_tool_fingerprints, "
        f"got {new_fps}"
    )


# ---------------------------------------------------------------------------
# T-D012-d: tool-result message content is capped at _LOOP_TOOL_RESULT_MESSAGE_MAX_CHARS
# ---------------------------------------------------------------------------


async def test_execute_tools_caps_large_tool_result_message() -> None:
    """When a tool returns output larger than _LOOP_TOOL_RESULT_MESSAGE_MAX_CHARS,
    the LLMMessage appended to the loop messages must have content truncated to
    at most _LOOP_TOOL_RESULT_MESSAGE_MAX_CHARS + len(' ...[truncated]') characters.
    """
    tool = _LargeOutputTool()
    runtime = _make_runtime([tool])
    ctx = _FakeCtx()

    call = {"name": "large_tool", "id": "call_001", "input": {}}
    state = _make_state(tool_calls=[call], seen_tool_fingerprints=[])
    config = _make_config(ctx)

    result = await runtime._execute_tools_node(state, config)  # type: ignore[arg-type]

    messages = result.get("messages", [])
    assert messages, "No messages returned by _execute_tools_node"
    tool_msg = messages[0]
    assert tool_msg.role == "tool"

    # The raw output is larger than the cap; the content should be capped
    assert len(tool_msg.content) <= _LOOP_TOOL_RESULT_MESSAGE_MAX_CHARS + len(" ...[truncated]"), (
        f"Tool-result message not capped: len={len(tool_msg.content)}, "
        f"cap={_LOOP_TOOL_RESULT_MESSAGE_MAX_CHARS}"
    )
    assert "...[truncated]" in tool_msg.content, (
        "Expected '...[truncated]' marker in capped tool-result message"
    )


# ---------------------------------------------------------------------------
# T-D012-e: post-execution duplicate guard still returns synthesize_from_tools
# ---------------------------------------------------------------------------


def test_should_continue_post_exec_guard_still_fires() -> None:
    """_should_continue must still return 'synthesize_from_tools' when duplicates
    appear in tool_results (post-execution guard — backward-compatible with D-011 fix).

    The pre-execution guard (D-012) prevents duplicates from being appended in the
    first place; the post-execution guard is a second line of defence when the
    pre-execution guard is bypassed for any reason.
    """
    runtime = _make_runtime([])
    response = _LCResponse(
        text="",
        tool_calls=[{"name": "list_stockout_risk", "id": "call_001", "input": {}}],
        finish_reason="tool_use",
    )
    state: dict[str, Any] = {
        "messages": [],
        "response": response,
        "input_tokens": 0,
        "output_tokens": 0,
        "cost_usd": 0.0,
        "tool_results": [
            {"list_stockout_risk": {}},
            {"list_stockout_risk": {}},  # duplicate — post-exec guard fires
        ],
        "iteration": 2,
        "status": "running",
        "error": None,
        "pending_hitl_approval_id": None,
        "pending_hitl_job_id": None,
        "compressed_messages": None,
        "seen_tool_fingerprints": [],
    }

    result = runtime._should_continue(state)  # type: ignore[arg-type]

    assert result == "synthesize_from_tools", (
        f"Post-exec duplicate guard expected 'synthesize_from_tools', got {result!r}"
    )


# ---------------------------------------------------------------------------
# T-D012-f: peak_input_tokens tracks the max single-call value (not operator.add SUM)
# ---------------------------------------------------------------------------


async def test_agent_run_usage_contains_peak_input_tokens() -> None:
    """AgentRuntime.run() must set usage['peak_input_tokens'] to the maximum
    single-call input_tokens seen during the run.

    The operator.add accumulator (input_tokens) is the SUM of all LLM calls —
    for a 2-call run both calls at 10 tokens, input_tokens=20, peak_input_tokens=10.
    Only peak_input_tokens is valid for the ≤90% Ollama saturation check (D-012 fix).
    """
    from packages.agent.orchestrator.models import SpecialistTask
    from packages.agent.runtime import AgentRuntime
    from tests.unit.helpers import FakeLCModel, make_model_registry, make_stop_response

    class _FakeToolRegistry:
        def list_for_role(self, role: str) -> list:
            return []
        def filter_for_user_role(self, user_role: str, tools: list) -> list:
            return tools
        def get(self, name: str) -> None:
            return None

    class _FakeCtx:
        def __init__(self) -> None:
            self.agent_step_id = uuid4()
            self.session_id = uuid4()
            self.user_id = "test-user"
            self.user_role = "analyst"

    # Single LLM call with input_tokens=42 (non-zero to verify peak is captured)
    from packages.agent.llm import LLMResponse, LLMUsage
    from decimal import Decimal

    response = LLMResponse(
        text="SKU-001 is at critical stockout risk.",
        tool_calls=[],
        finish_reason="stop",
        usage=LLMUsage(
            input_tokens=42,
            output_tokens=10,
            total_cost_usd=Decimal("0"),
        ),
        model="fake",
        request_id=str(uuid4()),
        latency_ms=1,
    )

    llm = FakeLCModel([response])
    registry = make_model_registry(llm)
    runtime = AgentRuntime(
        name="test_agent",
        role="data_engineer",
        llm_client=None,
        tool_registry=_FakeToolRegistry(),
        sse_queue=None,
        system_prompt="You are a test specialist.",
        model_registry=registry,
    )
    task = SpecialistTask(
        task_id=uuid4(),
        instruction="Which products are at risk of stockout?",
        context_payload={},
        allowed_tools=[],
    )
    ctx = _FakeCtx()

    result = await runtime.run(task, ctx)

    assert result.usage is not None
    peak = result.usage.get("peak_input_tokens")
    assert peak is not None, "usage['peak_input_tokens'] must be set (D-012 fix)"
    assert peak == 42, (
        f"Expected peak_input_tokens=42 (single call), got {peak}. "
        "peak_input_tokens must be the max single-call value, not the operator.add SUM."
    )


# ---------------------------------------------------------------------------
# T-D012-g: _should_continue routes to synthesize_from_tools when all pending
# tool calls are already in seen_tool_fingerprints (pre-execution routing guard)
# ---------------------------------------------------------------------------


def test_should_continue_all_dupes_in_fingerprints_routes_to_synthesize() -> None:
    """When ALL pending tool calls from the model are already in seen_tool_fingerprints,
    _should_continue must route to 'synthesize_from_tools' (tool_results non-empty)
    to prevent the model from looping infinitely on already-cached tool calls.

    This is the D-012 pre-execution routing guard: the post-execution guard (D-011)
    fires when tool_results has duplicates, but with pre-execution dedupe the second
    result is never added to tool_results.  This guard covers that gap.
    """
    runtime = _make_runtime(tools=[])

    call = {"name": "x", "id": "call_001", "input": {}}
    fp = runtime._tool_fingerprint(call)

    response = _LCResponse(
        text="",
        tool_calls=[call],
        finish_reason="tool_use",
    )
    state = {
        "messages": [],
        "response": response,
        "input_tokens": 0,
        "output_tokens": 0,
        "cost_usd": 0.0,
        "tool_results": [{"x": {"count": 1}}],  # already has result for this tool
        "iteration": 2,
        "status": "running",
        "error": None,
        "pending_hitl_approval_id": None,
        "pending_hitl_job_id": None,
        "compressed_messages": None,
        "seen_tool_fingerprints": [fp],  # fingerprint already seen
    }

    result = runtime._should_continue(state)  # type: ignore[arg-type]

    assert result == "synthesize_from_tools", (
        f"Expected 'synthesize_from_tools' when all pending tool calls are pre-execution "
        f"duplicates (D-012 routing guard), got {result!r}"
    )


def test_should_continue_all_dupes_no_results_routes_to_verify() -> None:
    """When ALL pending tool calls are pre-execution duplicates but tool_results is empty,
    _should_continue must route to 'verify_findings' (nothing to synthesize from).
    """
    runtime = _make_runtime(tools=[])

    call = {"name": "x", "id": "call_001", "input": {}}
    fp = runtime._tool_fingerprint(call)

    response = _LCResponse(
        text="",
        tool_calls=[call],
        finish_reason="tool_use",
    )
    state = {
        "messages": [],
        "response": response,
        "input_tokens": 0,
        "output_tokens": 0,
        "cost_usd": 0.0,
        "tool_results": [],  # no results yet
        "iteration": 2,
        "status": "running",
        "error": None,
        "pending_hitl_approval_id": None,
        "pending_hitl_job_id": None,
        "compressed_messages": None,
        "seen_tool_fingerprints": [fp],  # fingerprint already seen
    }

    result = runtime._should_continue(state)  # type: ignore[arg-type]

    assert result == "verify_findings", (
        f"Expected 'verify_findings' when all pending calls are duplicates but no "
        f"tool_results exist (D-012 routing guard), got {result!r}"
    )
