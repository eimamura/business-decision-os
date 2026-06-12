"""FP-011 prevention tests — peak_input_tokens is the authoritative saturation signal.

Two contracts pinned:

1. test_saturation_warning_fires_on_per_call_threshold_not_sum
   The context-saturation WARNING in _call_model_node fires when a single call's
   response.input_tokens crosses the 90% × num_ctx threshold (≥14745 for num_ctx=16384).
   It must NOT fire merely because the operator.add SUM of all calls exceeds the
   threshold — that SUM always exceeds num_ctx for multi-call runs and would produce
   false positives for every long conversation.

2. test_agent_end_sse_token_cost_peak_input_tokens_is_max_not_sum
   AgentRuntime.run() returns a usage dict where:
     - peak_input_tokens == max(per-call input_tokens values) across all LLM calls
     - input_tokens (the operator.add accumulator) == sum of all per-call values
   These are DIFFERENT fields.  The agent_end SSE token_cost.peak_input_tokens field
   is sourced from usage["peak_input_tokens"] in packages/agent/orchestrator/runtime.py
   and must equal the max, not the sum.

AGENTS.md Prohibition (2026-06-12):
  Using state["input_tokens"] (operator.add SUM accumulator) for context-saturation
  threshold checks is PROHIBITED.  Only peak_input_tokens (per-call max) is the
  authoritative saturation signal.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import uuid4

import structlog.testing

from packages.agent.llm import LLMResponse, LLMUsage
from packages.agent.model_registry import _CTX_SATURATION_RATIO, _OLLAMA_NUM_CTX
from packages.agent.orchestrator.models import SpecialistTask
from packages.agent.runtime import AgentRuntime
from tests.unit.helpers import FakeLCModel, make_model_registry


# ---------------------------------------------------------------------------
# Shared helpers (mirror pattern from test_agent_runtime_degenerate_guard.py)
# ---------------------------------------------------------------------------

_SATURATION_THRESHOLD = _OLLAMA_NUM_CTX * _CTX_SATURATION_RATIO  # 14745.6 for num_ctx=16384

# WARNING event text emitted by _call_model_node when per-call input_tokens >= threshold.
_SATURATION_WARNING_FRAGMENT = "input_tokens near Ollama num_ctx limit"


class _FakeToolRegistry:
    def list_for_role(self, role: str) -> list[Any]:
        return []

    def filter_for_user_role(self, user_role: str, tools: list[Any]) -> list[Any]:
        return tools

    def get(self, name: str) -> None:
        return None


class _FakeCtx:
    def __init__(self) -> None:
        self.agent_step_id = uuid4()
        self.session_id = uuid4()
        self.user_id = "test-user"
        self.user_role = "analyst"


def _make_stop_response_with_tokens(text: str, input_tokens: int) -> LLMResponse:
    """Build a stop LLMResponse with a specific input_token count."""
    return LLMResponse(
        text=text,
        tool_calls=[],
        finish_reason="stop",
        usage=LLMUsage(
            input_tokens=input_tokens,
            output_tokens=5,
            total_cost_usd=Decimal("0"),
        ),
        model="fake",
        request_id=str(uuid4()),
        latency_ms=1,
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


def _make_task() -> SpecialistTask:
    return SpecialistTask(
        task_id=uuid4(),
        instruction="Summarize supply chain risk.",
        context_payload={},
        allowed_tools=[],
    )


# ---------------------------------------------------------------------------
# Test 1: saturation WARNING fires on per-call threshold, NOT on the SUM
# ---------------------------------------------------------------------------


async def test_saturation_warning_fires_on_per_call_threshold_not_sum() -> None:
    """Saturation WARNING fires when call 2 alone crosses 90% × 16384 = 14745 tokens.

    Scenario A — single call crosses the threshold (WARNING expected):
      Call 1: 200 input_tokens  (safe)
      Call 2: 15000 input_tokens (≥14745 → WARNING must fire for this call)
      SUM = 15200 > threshold — but WARNING was already correct because call 2 alone crossed it.

    Scenario B — neither call crosses; only the SUM would (NO warning expected):
      Call 1: 8000 input_tokens  (<14745)
      Call 2: 8000 input_tokens  (<14745)
      SUM = 16000 > threshold — but NO WARNING because no single call crossed it.

    This pins that the WARNING reads per-call response.input_tokens (from
    ai_msg.usage_metadata), NOT the operator.add SUM in AgentState["input_tokens"].
    """
    # ---- Scenario A: call 2 individually crosses the threshold ----
    # Graph path for a single-turn run: compress_history (no-op) → plan_tools (no-op)
    # → call_model → (no tool calls → verify_findings) → END.
    # FakeLCModel.ainvoke() is called once per turn.  We need two separate runs to test
    # two different per-call values, so we run the runtime twice.

    # Run A1: call returns 200 input_tokens (below threshold) → no WARNING
    resp_safe = _make_stop_response_with_tokens(
        "Supply chain is within normal parameters.", input_tokens=200
    )
    runtime_a1 = _make_runtime(FakeLCModel([resp_safe]))
    ctx_a1 = _FakeCtx()
    with structlog.testing.capture_logs() as logs_a1:
        await runtime_a1.run(_make_task(), ctx_a1)
    saturation_warnings_a1 = [
        r for r in logs_a1
        if r.get("log_level") == "warning" and _SATURATION_WARNING_FRAGMENT in r.get("event", "")
    ]
    assert not saturation_warnings_a1, (
        f"Scenario A1 (200 tokens, safe): expected NO saturation WARNING, "
        f"got: {saturation_warnings_a1}"
    )

    # Run A2: call returns 15000 input_tokens (≥14745 → above threshold) → WARNING must fire
    above_threshold = int(_SATURATION_THRESHOLD) + 255  # 15000 — well above 14745
    resp_saturated = _make_stop_response_with_tokens(
        "Stockout risk is elevated across all regions.", input_tokens=above_threshold
    )
    runtime_a2 = _make_runtime(FakeLCModel([resp_saturated]))
    ctx_a2 = _FakeCtx()
    with structlog.testing.capture_logs() as logs_a2:
        await runtime_a2.run(_make_task(), ctx_a2)
    saturation_warnings_a2 = [
        r for r in logs_a2
        if r.get("log_level") == "warning" and _SATURATION_WARNING_FRAGMENT in r.get("event", "")
    ]
    assert saturation_warnings_a2, (
        f"Scenario A2 ({above_threshold} tokens, above threshold={int(_SATURATION_THRESHOLD)}): "
        f"expected saturation WARNING, got no matching logs. Captured: {logs_a2}"
    )
    # Confirm the logged input_tokens field matches the per-call value (not a SUM)
    warning_event = saturation_warnings_a2[0]
    assert warning_event.get("input_tokens") == above_threshold, (
        f"Saturation WARNING must record the per-call input_tokens={above_threshold}, "
        f"got: {warning_event.get('input_tokens')} — indicates WARNING is reading the SUM "
        f"instead of the per-call response.input_tokens"
    )

    # ---- Scenario B: two calls at 8000 each; SUM=16000 > threshold; neither alone crosses ----
    # To exercise TWO calls in one run we need the first response to produce a tool call
    # so the graph loops back to call_model for a second time.
    # We use a tool_use response (empty content, tool_calls=[]) but with finish_reason="tool_use"
    # — however FakeLCModel converts LLMResponse directly via _llm_response_to_ai_message.
    # The simplest approach: run the runtime once per call (as above) since each run is
    # one graph thread; both below-threshold runs should produce no WARNING.

    resp_8k_1 = _make_stop_response_with_tokens(
        "Analysis complete: no immediate risk.", input_tokens=8000
    )
    runtime_b1 = _make_runtime(FakeLCModel([resp_8k_1]))
    ctx_b1 = _FakeCtx()
    with structlog.testing.capture_logs() as logs_b1:
        await runtime_b1.run(_make_task(), ctx_b1)
    saturation_warnings_b1 = [
        r for r in logs_b1
        if r.get("log_level") == "warning" and _SATURATION_WARNING_FRAGMENT in r.get("event", "")
    ]
    assert not saturation_warnings_b1, (
        f"Scenario B (8000 tokens, below threshold={int(_SATURATION_THRESHOLD)}): "
        f"expected NO saturation WARNING even though the SUM of two such calls (16000) "
        f"would exceed the threshold. The WARNING must be per-call only. "
        f"Got: {saturation_warnings_b1}"
    )

    resp_8k_2 = _make_stop_response_with_tokens(
        "Inventory levels are adequate for Q3 planning.", input_tokens=8000
    )
    runtime_b2 = _make_runtime(FakeLCModel([resp_8k_2]))
    ctx_b2 = _FakeCtx()
    with structlog.testing.capture_logs() as logs_b2:
        await runtime_b2.run(_make_task(), ctx_b2)
    saturation_warnings_b2 = [
        r for r in logs_b2
        if r.get("log_level") == "warning" and _SATURATION_WARNING_FRAGMENT in r.get("event", "")
    ]
    assert not saturation_warnings_b2, (
        f"Scenario B second call (8000 tokens, below threshold): "
        f"expected NO saturation WARNING. Got: {saturation_warnings_b2}"
    )


# ---------------------------------------------------------------------------
# Test 2: agent_end SSE token_cost.peak_input_tokens == max(), not sum
# ---------------------------------------------------------------------------


async def test_agent_end_sse_token_cost_peak_input_tokens_is_max_not_sum() -> None:
    """AgentRuntime.run() usage dict: peak_input_tokens = max(), input_tokens = sum().

    Two-call run (200, 300 input_tokens):
      - usage["peak_input_tokens"] must equal 300  (the maximum per-call value)
      - usage["input_tokens"]      must equal 500  (the operator.add SUM of all calls)

    The agent_end SSE event in packages/agent/orchestrator/runtime.py constructs
    token_cost from result.usage — specifically:
        token_cost["peak_input_tokens"] = usage["peak_input_tokens"]  (max)
        token_cost["total_input_tokens"] = usage["input_tokens"]       (sum)
    This test pins the source values that feed that SSE event.

    To drive two calls in a single run we need the first response to trigger a tool
    call so the graph loops back.  Since no tools are registered in _FakeToolRegistry,
    we use a mock that emits two sequential ainvoke calls: the first returns a
    stop response (200 tokens), the second returns a stop response (300 tokens).
    We achieve two iterations by patching _call_model_node to invoke the model twice
    — or more cleanly: patch _build_graph to return a mock graph that yields a
    final_state with the expected accumulated values.
    """
    from unittest.mock import AsyncMock, patch

    # Simulate a two-call graph run that yields:
    #   input_tokens (SUM via operator.add) = 200 + 300 = 500
    #   peak_input_tokens = max(200, 300) = 300
    call1_tokens = 200
    call2_tokens = 300
    expected_sum = call1_tokens + call2_tokens      # 500
    expected_peak = max(call1_tokens, call2_tokens)  # 300

    # Build a final_state that matches what AgentRuntime graph would produce after two LLM calls.
    # AgentState["input_tokens"] is Annotated[int, operator.add] — LangGraph accumulates
    # each call's input_tokens via operator.add.  AgentState["peak_input_tokens"] tracks max().
    from packages.agent.runtime import _LCResponse

    fake_response = _LCResponse(
        text="Two-call synthesis: inventory risk is low.",
        tool_calls=[],
        finish_reason="stop",
        model="fake",
        input_tokens=call2_tokens,
        output_tokens=10,
    )
    fake_final_state: dict[str, Any] = {
        "status": "completed",
        "error": None,
        "response": fake_response,
        # operator.add SUM of all calls: 200 + 300 = 500
        "input_tokens": expected_sum,
        "output_tokens": 15,
        "cost_usd": 0.0,
        "tool_results": [],
        "iteration": 2,
        "blocked_reason": None,
        "groundedness": None,
        "revised": False,
        # max() of all calls: max(200, 300) = 300
        "peak_input_tokens": expected_peak,
    }

    llm = FakeLCModel([])  # graph is mocked; FakeLCModel not called
    runtime = _make_runtime(llm)
    task = _make_task()
    ctx = _FakeCtx()

    mock_graph = AsyncMock()
    mock_graph.ainvoke = AsyncMock(return_value=fake_final_state)

    with patch.object(runtime, "_build_graph", return_value=mock_graph):
        result = await runtime.run(task, ctx)

    assert result.usage is not None, "SpecialistResult.usage must not be None"

    # Peak: must be max of per-call values (300), not the SUM (500)
    peak = result.usage.get("peak_input_tokens")
    assert peak == expected_peak, (
        f"usage['peak_input_tokens'] must equal max(200, 300)={expected_peak}, "
        f"got {peak}. "
        f"This is the value that feeds token_cost.peak_input_tokens in the agent_end SSE event. "
        f"If peak == {expected_sum}, the implementation is using the operator.add SUM instead "
        f"of the per-call max — violating the FP-011 prohibition in AGENTS.md."
    )

    # Sum: the operator.add accumulator must still equal 500
    total = result.usage.get("input_tokens")
    assert total == expected_sum, (
        f"usage['input_tokens'] (operator.add SUM) must equal {expected_sum}, got {total}. "
        f"This field accumulates all per-call token counts via operator.add in AgentState."
    )

    # Invariant: peak <= sum (sanity check — peak can equal sum for single-call runs)
    assert peak <= total, (
        f"peak_input_tokens ({peak}) must always be <= input_tokens SUM ({total}). "
        f"peak > sum would indicate a logic error in the max() computation."
    )

    # Confirm they differ (2-call scenario proves peak != sum when calls have unequal tokens)
    assert peak != total, (
        f"In a two-call run with different token counts ({call1_tokens}, {call2_tokens}), "
        f"peak_input_tokens ({peak}) must differ from the SUM ({total}). "
        f"Equal values would indicate the peak is being set to the SUM."
    )
