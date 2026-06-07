"""T-398: Unit tests for the degenerate LLM response guard in AgentRuntime.

When the final assistant text is non-empty but shorter than _DEGENERATE_RESPONSE_MIN_LEN
(10 chars), AgentRuntime.run() must:
  - emit a WARNING log containing 'Degenerate LLM response'
  - override output["text"] with _FALLBACK_DEGENERATE
  - return SpecialistResult.status == "failed"

When text is >= _DEGENERATE_RESPONSE_MIN_LEN, run() completes normally.
"""
from __future__ import annotations

import logging
from uuid import uuid4

import pytest

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


def _make_runtime(lc_model: FakeLCModel) -> AgentRuntime:
    registry = make_model_registry(lc_model)
    return AgentRuntime(
        name="test_agent",
        role="data_engineer",
        llm_client=None,
        tool_registry=_FakeToolRegistry(),
        sse_queue=None,
        system_prompt="You are a test specialist.",
        model_registry=registry,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_degenerate_response_logs_warning_and_overrides_output(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """When the final LLM response text is fewer than 10 characters, AgentRuntime.run()
    must emit a WARNING log, override output["text"] with the fallback message, and
    return status == "failed"."""
    short_text = "Based"  # 5 chars — below the 10-char threshold
    # Rule-based verifier: no tool calls + no digit/no/none → passes through as "completed"
    # but degenerate guard in run() fires on the short text before output is built
    main_response = make_stop_response(short_text)

    llm = FakeLCModel([main_response])
    runtime = _make_runtime(llm)
    task = _make_task()
    ctx = _FakeToolContext()

    with caplog.at_level(logging.WARNING, logger="packages.agent.runtime"):
        result = await runtime.run(task, ctx)

    assert result.status == "failed"
    assert isinstance(result.output, dict)
    assert result.output["text"] == _FALLBACK_DEGENERATE
    assert any("Degenerate" in r.message for r in caplog.records)


async def test_degenerate_response_no_warning_when_text_10_chars_or_more(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """When the final LLM response text is exactly 10 characters or more, AgentRuntime.run()
    must complete normally without emitting a degenerate warning."""
    exact_10_text = "C" * 10  # exactly 10 chars — at the threshold, should pass
    main_response = make_stop_response(exact_10_text)

    llm = FakeLCModel([main_response])
    runtime = _make_runtime(llm)
    task = _make_task()
    ctx = _FakeToolContext()

    with caplog.at_level(logging.WARNING, logger="packages.agent.runtime"):
        result = await runtime.run(task, ctx)

    assert result.status == "completed"
    assert not any("Degenerate" in r.message for r in caplog.records)
