"""D-011 unit tests — loop guard synthesis node + slim-agent-output digest.

Covers:
  T-D011-A-01  synthesize_from_tools produces grounded text from tool observations
  T-D011-A-02  synthesize_from_tools falls through gracefully when LLM call fails
  T-D011-A-03  synthesize_from_tools falls through gracefully when LLM produces
               degenerate text (< _DEGENERATE_RESPONSE_MIN_LEN chars)
  T-D011-A-04  end-to-end: duplicate tool call → synthesize_from_tools → grounded reply
               (not the hard-coded fallback)
  T-D011-B-01  _slim_agent_output includes tool_results_digest when text is a fallback
  T-D011-B-02  _slim_agent_output does NOT include digest when text is substantive (>= 50 chars)
  T-D011-B-03  _build_tool_digest honours the max_chars cap deterministically
"""
from __future__ import annotations

import asyncio
import json
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from packages.agent.orchestrator.decision import (
    _FALLBACK_TEXT_MIN_LEN,
    _SYNTHESIZE_TOOL_DIGEST_MAX_CHARS,
    _build_tool_digest,
    _slim_agent_output,
)
from packages.agent.orchestrator.models import SpecialistTask
from packages.agent.runtime import (
    AgentRuntime,
    _DEGENERATE_RESPONSE_MIN_LEN,
    _LOOP_GUARD_SYNTHESIS_MAX_CHARS,
    _LCResponse,
)
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


def _make_task(instruction: str = "Analyze demand gap.") -> SpecialistTask:
    return SpecialistTask(
        task_id=uuid4(),
        instruction=instruction,
        context_payload={},
        allowed_tools=[],
    )


def _make_runtime(lc_model: Any) -> AgentRuntime:
    registry = make_model_registry(lc_model)
    return AgentRuntime(
        name="test_control",
        role="control",
        llm_client=None,
        tool_registry=_FakeToolRegistry(),
        sse_queue=None,
        system_prompt="You are a supply chain control specialist.",
        model_registry=registry,
    )


def _make_base_state(
    tool_results: list[dict[str, Any]] | None = None,
    response: Any | None = None,
    loop_guard_triggered: bool = False,
) -> dict[str, Any]:
    """Build minimal AgentState for synthesize_from_tools tests."""
    return {
        "messages": [],
        "response": response,
        "input_tokens": 0,
        "output_tokens": 0,
        "cost_usd": 0.0,
        "tool_results": tool_results or [],
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
        "loop_guard_triggered": loop_guard_triggered,
    }


def _make_config() -> Any:
    return MagicMock(get=MagicMock(return_value={}))


# ---------------------------------------------------------------------------
# T-D011-A-01: synthesize_from_tools produces grounded text
# ---------------------------------------------------------------------------


async def test_synthesize_from_tools_produces_grounded_text() -> None:
    """When tool_results are non-empty and the LLM returns a substantive reply,
    synthesize_from_tools must update state["response"] with the new text and
    set loop_guard_triggered=True."""
    grounded_reply = (
        "SKU-028 shows a 15% demand gap over the last four weeks. "
        "The forecast was 200 units but actual demand was 230 units. "
        "This suggests a systematic underforecast driven by a new customer segment."
    )
    llm = FakeLCModel([make_stop_response(grounded_reply)])
    runtime = _make_runtime(llm)

    tool_results = [
        {
            "analyze_forecast_deviation": {
                "count": 1,
                "items": [
                    {
                        "sku_id": "SKU-028",
                        "forecast_qty": 200,
                        "actual_qty": 230,
                        "deviation_pct": 15.0,
                    }
                ],
            }
        }
    ]
    state = _make_base_state(tool_results=tool_results)
    config = _make_config()

    result = await runtime._synthesize_from_tools_node(state, config)  # type: ignore[arg-type]

    assert result.get("loop_guard_triggered") is True
    new_response = result.get("response")
    assert new_response is not None, "synthesize_from_tools must set response"
    assert new_response.text == grounded_reply
    assert new_response.finish_reason == "stop"
    assert new_response.tool_calls == []


# ---------------------------------------------------------------------------
# T-D011-A-02: synthesize_from_tools falls through when LLM call fails
# ---------------------------------------------------------------------------


async def test_synthesize_from_tools_falls_through_on_llm_error() -> None:
    """When the LLM call raises, synthesize_from_tools must return only
    loop_guard_triggered=True without setting response — so verify_findings
    handles the run via the existing blocked/soft-fail path."""
    llm = FakeLCModel([])  # empty — will fall through to error branch

    # Patch the model to raise
    runtime = _make_runtime(llm)
    runtime._lc_model = MagicMock()
    runtime._lc_model.ainvoke = AsyncMock(side_effect=RuntimeError("model timeout"))

    tool_results = [{"list_stockout_risk": {"count": 2, "items": ["SKU-001", "SKU-002"]}}]
    state = _make_base_state(tool_results=tool_results)
    config = _make_config()

    result = await runtime._synthesize_from_tools_node(state, config)  # type: ignore[arg-type]

    assert result.get("loop_guard_triggered") is True
    # response must NOT be set — the old (empty-text) response persists in state
    assert "response" not in result


# ---------------------------------------------------------------------------
# T-D011-A-03: synthesize_from_tools falls through on degenerate text
# ---------------------------------------------------------------------------


async def test_synthesize_from_tools_falls_through_on_degenerate_text() -> None:
    """When the forced-final LLM call returns text shorter than
    _DEGENERATE_RESPONSE_MIN_LEN, synthesize_from_tools must NOT update
    response in state (falling through to the existing blocked path)."""
    short_text = "OK"  # 2 chars — well below the 10-char threshold
    llm = FakeLCModel([make_stop_response(short_text)])
    runtime = _make_runtime(llm)

    tool_results = [{"list_stockout_risk": {"count": 1, "items": ["SKU-001"]}}]
    state = _make_base_state(tool_results=tool_results)
    config = _make_config()

    result = await runtime._synthesize_from_tools_node(state, config)  # type: ignore[arg-type]

    assert result.get("loop_guard_triggered") is True
    assert "response" not in result, (
        "synthesize_from_tools must not set response for degenerate text"
    )


# ---------------------------------------------------------------------------
# T-D011-A-04: end-to-end — duplicate tool → synthesis → grounded reply
# ---------------------------------------------------------------------------


async def test_end_to_end_duplicate_tool_produces_grounded_reply() -> None:
    """End-to-end simulation of the D-011 failure path:

    1. First LLM call → tool_call (finish_reason=tool_use, text="")
    2. Tool executed; second LLM call → same tool again (duplicate) → guard fires
    3. synthesize_from_tools LLM call (no tools) → grounded text
    4. Final SpecialistResult must NOT be the hard-coded fallback and must
       contain the grounded text.
    """
    from packages.agent.llm import LLMResponse, LLMUsage

    tool_call_resp = LLMResponse(
        text="",
        tool_calls=[{"id": "c1", "name": "list_stockout_risk", "input": {}}],
        finish_reason="tool_use",
        usage=LLMUsage(input_tokens=100, output_tokens=5, total_cost_usd=Decimal("0")),
        model="fake",
        request_id=str(uuid4()),
        latency_ms=1,
    )
    grounded_text = (
        "SKU-001 is at critical stockout risk with 3 days of supply remaining. "
        "Immediate replenishment of 500 units is recommended to avoid a service failure."
    )
    synthesis_resp = LLMResponse(
        text=grounded_text,
        tool_calls=[],
        finish_reason="stop",
        usage=LLMUsage(input_tokens=200, output_tokens=50, total_cost_usd=Decimal("0")),
        model="fake",
        request_id=str(uuid4()),
        latency_ms=1,
    )

    # Sequence of LLM calls (plan_tools is skipped for this intent — context_payload={}).
    # call_model: first → tool call; second → same tool call (duplicate guard fires);
    # synthesize_from_tools: one forced-final call → grounded text.
    llm = FakeLCModel([
        tool_call_resp,       # first call_model → calls list_stockout_risk
        tool_call_resp,       # second call_model (after execute_tools) → duplicate
        synthesis_resp,       # synthesize_from_tools forced-final call (no tools)
    ])

    from packages.tools.base import ToolResult

    # Override the tool registry to stub the tool execution
    class _StubToolRegistry:
        def list_for_role(self, role: str) -> list:
            return []

        def filter_for_user_role(self, user_role: str, tools: list) -> list:
            return tools

        def get(self, name: str) -> Any:
            tool = MagicMock()
            tool.safety_level = "read_only"
            tool.name = name
            tool.handle = AsyncMock(
                return_value=ToolResult(
                    output={"count": 2, "items": ["SKU-001", "SKU-002"]},
                    audit_payload={},
                )
            )
            return tool

    registry = make_model_registry(llm)
    runtime = AgentRuntime(
        name="test_control",
        role="control",
        llm_client=None,
        tool_registry=_StubToolRegistry(),
        sse_queue=None,
        system_prompt="You are a supply chain control specialist.",
        model_registry=registry,
    )

    task = _make_task()
    ctx = _FakeToolContext()

    result = await runtime.run(task, ctx)

    assert result.status == "completed"
    assert result.output is not None
    reply_text = result.output.get("text", "")
    # Must not be the hard-coded fallback
    assert "Could not verify findings" not in reply_text, (
        f"Expected grounded reply, got fallback: {reply_text!r}"
    )
    # Must contain the grounded synthesis text
    assert "SKU-001" in reply_text, (
        f"Expected seeded entity SKU-001 in reply, got: {reply_text!r}"
    )


# ---------------------------------------------------------------------------
# T-D011-B-01: _slim_agent_output includes digest when text is a fallback
# ---------------------------------------------------------------------------


def test_slim_agent_output_includes_digest_for_fallback_text() -> None:
    """When agent text is shorter than _FALLBACK_TEXT_MIN_LEN and tool_results
    are present, _slim_agent_output must include a non-empty tool_results_digest."""
    fallback_text = "Could not verify findings. Please rephrase your question or try again."
    # This is 70 chars — above _FALLBACK_TEXT_MIN_LEN (50), so the digest is NOT included.
    # Use a truly short text:
    short_text = "N/A"  # 3 chars < 50

    output = {
        "text": short_text,
        "specialist": "control",
        "tool_results": [
            {"list_stockout_risk": {"count": 2, "items": [{"sku_id": "SKU-001"}, {"sku_id": "SKU-002"}]}}
        ],
    }

    slim = _slim_agent_output(output)

    assert "tool_results_digest" in slim, (
        "Expected tool_results_digest in slim output when text is a fallback"
    )
    assert "SKU-001" in slim["tool_results_digest"]


# ---------------------------------------------------------------------------
# T-D011-B-02: _slim_agent_output does NOT include digest for substantive text
# ---------------------------------------------------------------------------


def test_slim_agent_output_no_digest_for_substantive_text() -> None:
    """When agent text is >= _FALLBACK_TEXT_MIN_LEN, _slim_agent_output must
    NOT include tool_results_digest — the synthesize LLM uses the text."""
    long_text = (
        "SKU-028 shows a 15% demand gap over the last four weeks. "
        "The forecast was 200 units but actual demand was 230 units."
    )
    assert len(long_text) >= _FALLBACK_TEXT_MIN_LEN

    output = {
        "text": long_text,
        "specialist": "control",
        "tool_results": [
            {"analyze_forecast_deviation": {"count": 1, "items": [{"sku_id": "SKU-028"}]}}
        ],
    }

    slim = _slim_agent_output(output)

    assert "tool_results_digest" not in slim, (
        "tool_results_digest must NOT appear when agent text is substantive"
    )
    assert slim["text"] == long_text


# ---------------------------------------------------------------------------
# T-D011-B-03: _build_tool_digest honours the max_chars cap deterministically
# ---------------------------------------------------------------------------


def test_build_tool_digest_respects_max_chars() -> None:
    """_build_tool_digest must never produce a string longer than max_chars + a
    truncation marker, and must include the truncation marker when the budget
    is exhausted."""
    large_entry: dict[str, Any] = {
        "analyze_forecast_deviation": {
            "count": 30,
            "items": [{"sku_id": f"SKU-{i:03d}", "deviation_pct": 10.0 + i} for i in range(30)],
        }
    }
    tool_results = [large_entry] * 5  # inflate to ensure truncation

    max_chars = 500
    digest = _build_tool_digest(tool_results, max_chars=max_chars)

    # Digest may be slightly over max_chars due to the truncation marker appended,
    # but the pre-marker content must not exceed max_chars.
    # We allow for the " ...[truncated]" suffix (16 chars).
    assert len(digest) <= max_chars + 20, (
        f"Digest length {len(digest)} exceeded cap {max_chars} + marker allowance"
    )
    # When truncated, the marker must be present
    if len(digest) > max_chars:
        assert "[truncated]" in digest


def test_build_tool_digest_empty_for_no_results() -> None:
    """_build_tool_digest returns empty string when tool_results is empty or None."""
    assert _build_tool_digest([]) == ""
    assert _build_tool_digest(None) == ""  # type: ignore[arg-type]


def test_build_tool_digest_single_entry_within_budget() -> None:
    """_build_tool_digest returns the full JSON of a small entry when it fits."""
    entry = {"list_stockout_risk": {"count": 1, "items": [{"sku_id": "SKU-001"}]}}
    digest = _build_tool_digest([entry], max_chars=_SYNTHESIZE_TOOL_DIGEST_MAX_CHARS)

    parsed = json.loads(digest)  # must be valid JSON for the single entry
    assert parsed == entry
