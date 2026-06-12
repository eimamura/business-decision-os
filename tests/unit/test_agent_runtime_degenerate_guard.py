"""T-398/T-566/T-567: Unit tests for the degenerate LLM response guard in AgentRuntime.

When the final assistant text is non-empty but shorter than _DEGENERATE_RESPONSE_MIN_LEN
(10 chars), AgentRuntime.run() must (T-566 soft-fail):
  - emit a WARNING log containing 'Degenerate LLM response'
  - override output["text"] with _FALLBACK_DEGENERATE
  - return SpecialistResult.status == "completed" (soft-fail; mirrors P80 blocked-path)
  - set output["verification"]["blocked_reason"] == "degenerate_response"
  - return SpecialistResult.error is None (no agent_failed SSE)
  - push no type=error / code=agent_failed event onto the SSE queue (T-567a)

When text is >= _DEGENERATE_RESPONSE_MIN_LEN, run() completes normally.

T-567b: error-status run with final_state["error"] falsy → SpecialistResult.error is a
non-empty string (not None, not the string "None").

Note: packages.agent.runtime uses structlog (not stdlib logging). Use
structlog.testing.capture_logs() to assert on log output — caplog.records does not
capture structlog events.
"""
from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

import pytest
import structlog.testing

from packages.agent.orchestrator.models import SpecialistTask
from packages.agent.runtime import AgentRuntime, _FALLBACK_DEGENERATE
from tests.unit.helpers import FakeLCModel, make_model_registry, make_stop_response


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


class _FakeToolRegistry:
    def list_for_role(self, role: str) -> list:
        return []

    def filter_for_user_role(self, user_role: str, tools: list) -> list:
        return tools

    def get(self, name: str) -> None:
        return None


class _FakeToolContext:
    def __init__(self) -> None:
        self.agent_step_id = uuid4()
        self.session_id = uuid4()
        self.user_id = "test-user"
        self.user_role = "analyst"


def _make_task(instruction: str = "Summarize demand.") -> SpecialistTask:
    return SpecialistTask(
        task_id=uuid4(),
        instruction=instruction,
        context_payload={},
        allowed_tools=[],
    )


def _make_runtime(lc_model: FakeLCModel, sse_queue: Any = None) -> AgentRuntime:
    registry = make_model_registry(lc_model)
    return AgentRuntime(
        name="test_agent",
        role="data_engineer",
        llm_client=None,
        tool_registry=_FakeToolRegistry(),
        sse_queue=sse_queue,
        system_prompt="You are a test specialist.",
        model_registry=registry,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_degenerate_response_logs_warning_and_overrides_output() -> None:
    """When the final LLM response text is fewer than 10 characters, AgentRuntime.run()
    must emit a WARNING structlog event containing 'Degenerate', override output["text"]
    with the fallback message, return status == "completed" (soft-fail), set the
    degenerate_response blocked_reason, and return error == None (no agent_failed SSE)."""
    short_text = "Based"  # 5 chars — below the 10-char threshold
    # Rule-based verifier: no tool calls + no digit/no/none → passes through as "completed"
    # but degenerate guard in run() fires on the short text after graph exits
    main_response = make_stop_response(short_text)

    llm = FakeLCModel([main_response])
    runtime = _make_runtime(llm)
    task = _make_task()
    ctx = _FakeToolContext()

    with structlog.testing.capture_logs() as captured:
        result = await runtime.run(task, ctx)

    # T-566: degenerate is now a soft-fail — status completed, no agent_failed SSE
    assert result.status == "completed"
    assert result.error is None
    assert isinstance(result.output, dict)
    assert result.output["text"] == _FALLBACK_DEGENERATE
    assert result.output.get("verification", {}).get("blocked_reason") == "degenerate_response"
    # structlog warning must be present — capture_logs() collects structlog events
    warning_events = [
        r for r in captured
        if r.get("log_level") == "warning" and "Degenerate" in r.get("event", "")
    ]
    assert warning_events, (
        f"Expected a structlog WARNING containing 'Degenerate'; captured: {captured}"
    )


async def test_degenerate_response_no_error_sse_event_pushed() -> None:
    """T-567a: Degenerate run must not push any type=error or code=agent_failed SSE event.

    The sse_queue attached to AgentRuntime receives only tool-level graph_node events
    from _emit().  Degenerate text is caught after the graph exits in run(); no error
    event is pushed at any point — result.error is None confirms the caller
    (orchestrator/runtime._run_agent) would not trigger agent_failed either.
    """
    short_text = "Based"  # 5 chars — degenerate

    sse_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    llm = FakeLCModel([make_stop_response(short_text)])
    runtime = _make_runtime(llm, sse_queue=sse_queue)
    task = _make_task()
    ctx = _FakeToolContext()

    result = await runtime.run(task, ctx)

    # Drain all events pushed to the SSE queue by the runtime
    pushed_events: list[dict[str, Any]] = []
    while not sse_queue.empty():
        pushed_events.append(sse_queue.get_nowait())

    # Primary assertion: no type=error and no code=agent_failed in any pushed event
    error_events = [e for e in pushed_events if e.get("type") == "error"]
    agent_failed_events = [e for e in pushed_events if e.get("code") == "agent_failed"]
    assert error_events == [], (
        f"Expected no type=error SSE events for a degenerate run, got: {error_events}"
    )
    assert agent_failed_events == [], (
        f"Expected no agent_failed SSE events for a degenerate run, got: {agent_failed_events}"
    )

    # Confirm the result itself signals soft-fail (not hard-fail)
    assert result.status == "completed"
    assert result.error is None


async def test_degenerate_response_no_warning_when_text_10_chars_or_more() -> None:
    """When the final LLM response text is exactly 10 characters or more, AgentRuntime.run()
    must complete normally without emitting a degenerate structlog warning."""
    exact_10_text = "C" * 10  # exactly 10 chars — at the threshold, should pass
    main_response = make_stop_response(exact_10_text)

    llm = FakeLCModel([main_response])
    runtime = _make_runtime(llm)
    task = _make_task()
    ctx = _FakeToolContext()

    with structlog.testing.capture_logs() as captured:
        result = await runtime.run(task, ctx)

    assert result.status == "completed"
    degenerate_warnings = [
        r for r in captured
        if r.get("log_level") == "warning" and "Degenerate" in r.get("event", "")
    ]
    assert not degenerate_warnings, (
        f"Expected no degenerate WARNING for 10-char response; captured: {degenerate_warnings}"
    )


async def test_error_status_with_falsy_error_field_returns_non_empty_error_string() -> None:
    """T-567b: When the graph exits with status='error' and final_state['error'] is falsy
    (None or absent), SpecialistResult.error must be a non-empty string — not None and
    not the string 'None'.

    This tests the T-566 fix: `final_state.get("error") or "agent run failed (no error detail)"`.
    The patch simulates a graph that reports an error state without an error message
    (which was the pre-T-566 behaviour that surfaced as "Agent control failed: None").
    """
    from unittest.mock import AsyncMock, patch

    # Provide a valid FakeLCModel so __init__ succeeds
    llm = FakeLCModel([make_stop_response("fallback")])
    runtime = _make_runtime(llm)
    task = _make_task()
    ctx = _FakeToolContext()

    # Simulate the graph returning status="error" with error=None (the pre-fix scenario)
    fake_final_state: dict[str, Any] = {
        "status": "error",
        "error": None,  # falsy — the critical condition being tested
        "response": None,
        "input_tokens": 0,
        "output_tokens": 0,
        "cost_usd": 0.0,
        "tool_results": [],
        "iteration": 0,
        "blocked_reason": None,
        "groundedness": None,
        "revised": False,
    }

    mock_graph = AsyncMock()
    mock_graph.ainvoke = AsyncMock(return_value=fake_final_state)

    with patch.object(runtime, "_build_graph", return_value=mock_graph):
        result = await runtime.run(task, ctx)

    assert result.status == "failed"
    assert result.error is not None, "error must not be None when graph exits with status=error"
    assert result.error != "None", (
        "error must not be the string 'None' — that was the pre-T-566 bug"
    )
    assert len(result.error) > 0, "error must be a non-empty string"
