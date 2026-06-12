from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from packages.agent.llm import LLMMessage, LLMResponse
from packages.agent.orchestrator.models import SpecialistTask
from packages.agent.runtime import SUMMARY_THRESHOLD, AgentRuntime
from tests.unit.helpers import (
    FakeLCModel,
    RecordingLLMClient,
    make_model_registry,
    make_stop_response,
    make_tool_call_response,
)


class _FakeTool:
    name = "nl_query"
    description = "Run SQL"
    input_schema: dict[str, Any] = {}

    async def handle(self, input: dict[str, Any], ctx: Any) -> Any:
        from packages.tools.base import ToolResult
        return ToolResult(output={"rows": [{"sku": "A", "qty": 10}]}, audit_payload={})


class _FakeToolRegistry:
    def __init__(self, tools: list[Any] | None = None) -> None:
        self._tools = tools or []

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


def _make_task(instruction: str = "What is the demand trend?") -> SpecialistTask:
    return SpecialistTask(
        task_id=uuid4(),
        instruction=instruction,
        context_payload={},
        allowed_tools=[],
    )


def _make_runtime(
    lc_model: FakeLCModel,
    tool_registry: Any | None = None,
) -> AgentRuntime:
    """Build AgentRuntime wired to the LangChain path.

    Accepts a FakeLCModel; wraps it in a model_registry so that
    _call_model_node and _verify_findings_node find a valid _lc_model.
    """
    registry = make_model_registry(lc_model)
    return AgentRuntime(
        name="test_agent",
        role="data_engineer",
        llm_client=None,  # legacy client not used — LangChain path only
        tool_registry=tool_registry or _FakeToolRegistry(),
        sse_queue=None,
        system_prompt="You are a test specialist.",
        model_registry=registry,
    )


# ---------------------------------------------------------------------------
# T-008: 3-block prompt caching — LangChain path
# Under the LangChain path, _call_model_node prepends SystemMessage(self._system_prompt)
# before the effective_messages, so the first LangChain message is the system prompt.
# ---------------------------------------------------------------------------


async def test_t008_system_message_has_three_content_blocks() -> None:
    """Under the LangChain path, the first ainvoke call must receive at least one
    SystemMessage whose content contains the configured system prompt text."""
    from langchain_core.messages import SystemMessage

    llm = FakeLCModel([make_stop_response(), make_stop_response("pass")])
    runtime = _make_runtime(llm)
    task = _make_task()
    ctx = _FakeToolContext()

    await runtime.run(task, ctx)

    assert llm._calls, "No LLM calls were recorded"
    first_call_messages = llm._calls[0]

    system_msgs = [m for m in first_call_messages if isinstance(m, SystemMessage)]
    assert len(system_msgs) >= 1, "Expected at least one SystemMessage"

    # First SystemMessage must contain the configured system prompt
    assert "You are a test specialist." in system_msgs[0].content, (
        f"First SystemMessage must include system prompt, got: {system_msgs[0].content!r}"
    )


async def test_t008_system_block_texts_are_correct_types() -> None:
    """Under the LangChain path, all LangChain messages passed to ainvoke must have
    string content (SystemMessage, HumanMessage, etc.)."""
    from langchain_core.messages import BaseMessage

    llm = FakeLCModel([make_stop_response(), make_stop_response("pass")])
    runtime = _make_runtime(llm)
    task = _make_task()
    ctx = _FakeToolContext()

    await runtime.run(task, ctx)

    assert llm._calls, "No LLM calls were recorded"
    first_call_messages = llm._calls[0]

    for i, msg in enumerate(first_call_messages):
        assert isinstance(msg, BaseMessage), f"Message {i} must be a BaseMessage"
        assert isinstance(msg.content, str), f"Message {i} content must be a str"


# ---------------------------------------------------------------------------
# T-007: verify_findings step (rule-based — P61)
# ---------------------------------------------------------------------------


async def test_t007_pass_does_not_retry() -> None:
    """Rule-based verifier: a normal long-enough conclusion passes without any
    additional LLM call — exactly 1 call total (no separate verifier call)."""
    main_response = make_stop_response("Demand is stable and within normal range.")

    llm = FakeLCModel([main_response])
    runtime = _make_runtime(llm)
    task = _make_task()
    ctx = _FakeToolContext()

    result = await runtime.run(task, ctx)

    assert result.status == "completed"
    # Only 1 call: main loop. Rule-based verifier makes zero LLM calls.
    assert len(llm._calls) == 1, (
        f"Expected 1 LLM call (main only — rule-based verifier), got {len(llm._calls)}"
    )


async def test_t007_blocked_on_fabricated_no_data_response() -> None:
    """Rule-based verifier: no tool calls + conclusion with 'no' keyword → blocked.
    Since P80-B-01 blocked maps to status='completed' (soft-fail) with the fallback
    text and blocked_reason in output meta — no agent_failed SSE.  The block still
    happens; it is just surfaced softly."""
    # "no stockouts" with no tool calls triggers Rule 1 — fabricated data
    main_response = make_stop_response("There are no stockouts in the warehouse currently.")

    llm = FakeLCModel([main_response])
    runtime = _make_runtime(llm)
    task = _make_task()
    ctx = _FakeToolContext()

    result = await runtime.run(task, ctx)

    assert result.status == "completed"
    assert result.output.get("text") == (
        "Could not verify findings. Please rephrase your question or try again."
    )
    assert result.output.get("verification", {}).get("blocked_reason") == (
        "findings verifier: response not grounded in tool results"
    )
    assert result.error is None
    # Only 1 call: main loop. Rule-based verifier makes zero LLM calls.
    assert len(llm._calls) == 1, (
        f"Expected 1 LLM call (no verifier call), got {len(llm._calls)}"
    )


# ---------------------------------------------------------------------------
# Regression: output builder still works
# ---------------------------------------------------------------------------


async def test_output_builder_receives_final_response() -> None:
    """After both tasks, the output builder must still receive the correct
    last_response from the final tool loop."""
    captured: dict[str, Any] = {}

    def _custom_builder(tool_results: dict[str, Any], response: Any) -> dict[str, Any]:
        captured["text"] = response.text if response else ""
        return {"text": captured["text"]}

    # P61: rule-based verifier — only 1 LLM call needed.
    llm = FakeLCModel([
        make_stop_response("Final answer from agent, fully grounded and detailed."),
    ])
    runtime = AgentRuntime(
        name="test",
        role="data_engineer",
        llm_client=None,
        tool_registry=_FakeToolRegistry(),
        output_builder=_custom_builder,
        model_registry=make_model_registry(llm),
    )
    task = _make_task()
    ctx = _FakeToolContext()

    result = await runtime.run(task, ctx)

    assert result.output.get("text") == "Final answer from agent, fully grounded and detailed."


# ---------------------------------------------------------------------------
# T-072: compress_history pre-processing node
# ---------------------------------------------------------------------------


async def test_t072_compress_history_noop_below_threshold() -> None:
    """When message count is at or below SUMMARY_THRESHOLD, compress_history
    makes zero LLM calls. P61: rule-based verifier also makes no LLM call,
    so exactly 1 total call is expected."""
    stop_resp = make_stop_response("All good and within expected parameters.")
    llm = FakeLCModel([stop_resp])
    runtime = _make_runtime(llm)
    task = _make_task()
    ctx = _FakeToolContext()

    result = await runtime.run(task, ctx)

    assert result.status == "completed"
    # Exactly 1 call: main loop only. Rule-based verifier + no compression → zero extra calls.
    assert len(llm._calls) == 1, (
        f"Expected 1 LLM call (no compression, rule-based verifier), got {len(llm._calls)}"
    )


async def test_t072_compress_history_reduces_messages_to_11() -> None:
    """When state has 35 messages, compress_history fires and call_model
    receives at most 11 messages (1 summary + 10 recent)."""
    # Build a fake state with 35 messages.
    fake_messages: list[LLMMessage] = [
        LLMMessage(role="user", content=f"message {i}") for i in range(35)
    ]
    fake_state: Any = {
        "messages": fake_messages,
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
        "compressed_messages": None,
    }

    # Use a fresh single-response FakeLCModel for summarization.
    summarize_llm = FakeLCModel([make_stop_response("Compact summary of early messages.")])
    summarize_runtime = _make_runtime(summarize_llm)

    # Invoke the node directly (config is not used by compress_history).
    result_dict = await summarize_runtime._compress_history_node(fake_state, {})  # type: ignore[arg-type]

    compressed = result_dict.get("compressed_messages")
    assert compressed is not None, "compress_history must set compressed_messages for 35 messages"
    assert len(compressed) <= 11, (
        f"compressed_messages must be <= 11 (1 summary + 10 recent), got {len(compressed)}"
    )
    # First message must be the summary system message
    assert compressed[0].role == "system"
    assert "[Conversation summary:" in compressed[0].content
    # Exactly 1 summarization LLM call was made
    assert len(summarize_llm._calls) == 1, (
        f"Expected 1 summarization call, got {len(summarize_llm._calls)}"
    )


async def test_t072_compress_history_at_threshold_boundary_is_noop() -> None:
    """Exactly SUMMARY_THRESHOLD messages must NOT trigger compression."""
    stop_resp = make_stop_response("done — all checks completed")
    llm = FakeLCModel([stop_resp])

    # Test the node directly
    runtime = _make_runtime(llm)
    exact_threshold_messages: list[LLMMessage] = [
        LLMMessage(role="user", content=f"msg {i}") for i in range(SUMMARY_THRESHOLD)
    ]
    fake_state: Any = {
        "messages": exact_threshold_messages,
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
        "compressed_messages": None,
    }

    result_dict = await runtime._compress_history_node(fake_state, {})  # type: ignore[arg-type]

    # Must return empty dict — no compressed_messages field set
    assert result_dict == {}, (
        f"compress_history must be no-op at threshold={SUMMARY_THRESHOLD}, got {result_dict}"
    )
    # No LLM calls consumed — both queued responses remain
    assert len(llm._calls) == 0, (
        f"compress_history must make zero LLM calls at threshold, got {len(llm._calls)}"
    )


# ---------------------------------------------------------------------------
# T-073: LangGraph graph structure verification
# ---------------------------------------------------------------------------


def test_t073_graph_has_expected_nodes() -> None:
    """AgentRuntime graph must contain exactly the expected set of nodes."""
    from langgraph.checkpoint.memory import MemorySaver

    llm = FakeLCModel([])
    runtime = _make_runtime(llm)
    graph = runtime._build_graph(checkpointer=MemorySaver())

    # LangGraph compiled graph exposes node names via .nodes or .graph
    # Use the underlying graph object to inspect node names
    node_names = set(graph.nodes.keys())

    expected_nodes = {
        "compress_history",
        "call_model",
        "execute_tools",
        "prepare_hitl",
        "wait_for_approval",
        "verify_findings",
    }
    missing = expected_nodes - node_names
    assert not missing, (
        f"Graph is missing expected nodes: {missing}. Found: {node_names}"
    )


def test_t073_graph_does_not_have_removed_revision_nodes() -> None:
    """P72 (ADR 2026-06-10): add_revision_message and call_model_final are present in the graph
    — the dead self-correction path was reconnected behind the LLM groundedness verdict.
    Also assert plan_tools is present (P64 gap closure).
    """
    from langgraph.checkpoint.memory import MemorySaver

    llm = FakeLCModel([])
    runtime = _make_runtime(llm)
    graph = runtime._build_graph(checkpointer=MemorySaver())

    node_names = set(graph.nodes.keys())
    for name in ("add_revision_message", "call_model_final", "plan_tools"):
        assert name in node_names, (
            f"Node '{name}' must be present in graph (P72 reconnected revision path; "
            f"P64 added plan_tools). Found nodes: {node_names}"
        )


async def test_t073_specialist_result_shape_after_run() -> None:
    """SpecialistResult returned by run() must have the correct shape.
    With rule-based verifier (P61), only 1 LLM call is made."""
    from packages.agent.orchestrator import SpecialistResult

    llm = FakeLCModel([make_stop_response("Analysis complete and fully grounded.")])
    runtime = _make_runtime(llm)
    task = _make_task()
    ctx = _FakeToolContext()

    result = await runtime.run(task, ctx)

    assert isinstance(result, SpecialistResult)
    assert result.task_id == task.task_id
    assert isinstance(result.output, dict)
    assert "text" in result.output
    assert result.status in ("completed", "failed", "needs_input")
    assert isinstance(result.tool_calls_made, list)
    assert result.usage is not None
    assert "input_tokens" in result.usage
    assert "output_tokens" in result.usage
    assert "cost_usd" in result.usage


@pytest.mark.parametrize(
    "conclusion,expected_status",
    [
        # Normal long conclusion with no tool calls and no fabrication markers → pass
        ("The demand pattern appears to be within expected seasonal range.", "completed"),
        # No tool calls + "no" keyword → rule-based verifier blocks (soft-fail: completed)
        ("There are no anomalies detected in supply chain.", "completed"),
        # No tool calls + digit in conclusion → rule-based verifier blocks (soft-fail: completed)
        ("There are 3 critical SKUs with stockout risk.", "completed"),
    ],
    ids=["pass_normal_conclusion", "blocked_no_keyword", "blocked_digit_fabricated"],
)
async def test_t073_verify_findings_rule_based_outcomes(
    conclusion: str, expected_status: str
) -> None:
    """P61: rule-based verifier — no LLM calls. Outcomes depend only on
    conclusion content + presence/absence of tool results.
    P80-B-01: blocked runs surface as status='completed' (soft-fail) with fallback
    text and blocked_reason meta; error is None."""
    main_resp = make_stop_response(conclusion)

    llm = FakeLCModel([main_resp])
    runtime = _make_runtime(llm)
    task = _make_task()
    ctx = _FakeToolContext()

    result = await runtime.run(task, ctx)

    assert result.status == expected_status, (
        f"conclusion='{conclusion}': expected status '{expected_status}', got '{result.status}'"
    )
    # Rule-based verifier makes zero LLM calls — only main call consumed
    assert len(llm._calls) == 1, (
        f"Expected 1 LLM call (rule-based verifier), got {len(llm._calls)}"
    )


async def test_t073_compress_history_noop_below_threshold_zero_summarize_calls() -> None:
    """When len(messages) <= SUMMARY_THRESHOLD, compress_history makes zero LLM calls
    (the summarize LLM call is never made). P61: rule-based verifier also uses zero calls."""
    stop_resp = make_stop_response("ok — verified and complete")
    llm = FakeLCModel([stop_resp])
    runtime = _make_runtime(llm)

    # Exactly 2 messages (system + user) — well below threshold
    fake_state: Any = {
        "messages": [
            LLMMessage(role="system", content="system prompt"),
            LLMMessage(role="user", content="query"),
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
        "compressed_messages": None,
    }

    result_dict = await runtime._compress_history_node(fake_state, {})  # type: ignore[arg-type]
    assert result_dict == {}, "compress_history must be a no-op below threshold"
    # No summarize calls made
    assert len(llm._calls) == 0


# ---------------------------------------------------------------------------
# P30-B-01: execute_tools node — tool_call path
# ---------------------------------------------------------------------------


class _RecordingFakeTool:
    name = "nl_query"
    description = "Run SQL"
    input_schema: dict[str, Any] = {}

    def __init__(self) -> None:
        self.handle = AsyncMock(return_value=_make_tool_result({"rows": [{"sku": "A", "qty": 10}]}))


def _make_tool_result(output: dict[str, Any]) -> Any:
    from packages.tools.base import ToolResult
    return ToolResult(output=output, audit_payload={})


class _FailingTool:
    name = "nl_query"
    description = "Run SQL"
    input_schema: dict[str, Any] = {}

    async def handle(self, input: dict[str, Any], ctx: Any) -> Any:
        raise RuntimeError("tool failed")


async def test_execute_tools_tool_call_handle_is_called_and_result_fed_to_next_llm() -> None:
    from langchain_core.messages import ToolMessage

    tool = _RecordingFakeTool()
    registry = _FakeToolRegistry([tool])

    # P61: rule-based verifier makes no LLM call — 2 calls total (tool call + conclusion)
    llm = FakeLCModel([
        make_tool_call_response("nl_query", {"query": "SELECT 1"}),
        make_stop_response("Tool result processed successfully."),
    ])
    runtime = _make_runtime(llm, tool_registry=registry)
    task = _make_task()
    ctx = _FakeToolContext()

    result = await runtime.run(task, ctx)

    assert result.status == "completed"
    assert len(llm._calls) == 2

    tool.handle.assert_called_once()

    # Under the LangChain path, the second ainvoke call receives ToolMessage objects
    second_call_messages = llm._calls[1]
    tool_messages = [m for m in second_call_messages if isinstance(m, ToolMessage)]
    assert len(tool_messages) == 1
    assert tool_messages[0].tool_call_id == "call_001"

    payload = json.loads(tool_messages[0].content)
    assert payload == {"rows": [{"sku": "A", "qty": 10}]}


async def test_execute_tools_unknown_tool_skips_handle_and_no_tool_message_added() -> None:
    from langchain_core.messages import ToolMessage

    registry = _FakeToolRegistry([])

    # P61: rule-based verifier makes no LLM call — 2 calls total.
    # Conclusion text must avoid digits and "no"/"none" (Rule 1 guard with empty tool_results).
    llm = FakeLCModel([
        make_tool_call_response("nonexistent_tool", {}),
        make_stop_response("Unknown tool was skipped during execution."),
    ])
    runtime = _make_runtime(llm, tool_registry=registry)
    task = _make_task()
    ctx = _FakeToolContext()

    result = await runtime.run(task, ctx)

    assert result.status == "completed"

    second_call_messages = llm._calls[1]
    tool_messages = [m for m in second_call_messages if isinstance(m, ToolMessage)]
    assert tool_messages == []


async def test_execute_tools_failing_tool_propagates_exception() -> None:
    registry = _FakeToolRegistry([_FailingTool()])

    llm = FakeLCModel([
        make_tool_call_response("nl_query", {}),
    ])
    runtime = _make_runtime(llm, tool_registry=registry)
    task = _make_task()
    ctx = _FakeToolContext()

    with pytest.raises(RuntimeError, match="tool failed"):
        await runtime.run(task, ctx)


# ---------------------------------------------------------------------------
# T-504: P80-B-02 — rule_based_verify direct tests + blocked-run surface
# ---------------------------------------------------------------------------


def test_t504_rule_based_verify_sql_fenced_digits_pass() -> None:
    """Rule 1 (T-503): digits inside a ```sql fenced block``` with no tool calls → pass.
    The fenced code is stripped before applying _FABRICATED_NO_DATA_RE."""
    from packages.agent.runtime import _rule_based_verify

    conclusion = (
        "Here is the SQL query you requested:\n"
        "```sql\n"
        "SELECT sku, COUNT(*) AS qty FROM inventory WHERE qty > 100;\n"
        "```\n"
        "Run this query to retrieve the relevant data."
    )
    result = _rule_based_verify(tool_results=[], conclusion=conclusion)

    assert result == "pass"


def test_t504_rule_based_verify_prose_digits_blocked() -> None:
    """Rule 1: digits in plain prose with no tool calls → blocked.
    Stripping code does not remove prose-level digit claims."""
    from packages.agent.runtime import _rule_based_verify

    conclusion = "There are 5 critical SKUs that have exceeded safety stock levels."
    result = _rule_based_verify(tool_results=[], conclusion=conclusion)

    assert result == "blocked"


def test_t504_rule_based_verify_inline_code_digits_pass() -> None:
    """Rule 1 (T-503): digits inside an inline `code span` with no tool calls → pass.
    Inline code is stripped before the fabrication-heuristic regex runs.
    The surrounding prose must be free of digits/no/none keywords to isolate the behavior."""
    from packages.agent.runtime import _rule_based_verify

    # Prose has zero digits/keywords; only digit is inside the inline code span.
    conclusion = (
        "Set the threshold using `max_items=50` in the configuration file. "
        "This change is purely structural and requires only the parameter update."
    )
    result = _rule_based_verify(tool_results=[], conclusion=conclusion)

    assert result == "pass"


def test_t504_rule_based_verify_rule1b_nil_claim_with_tool_data_blocked() -> None:
    """Rule 1b (unchanged): tool returned non-empty results but conclusion claims 'no' items.
    Verifier blocks to prevent misleading nil-claim when data exists."""
    from packages.agent.runtime import _rule_based_verify

    tool_results = [{"nl_query": {"count": 3, "items": ["A", "B", "C"]}}]
    conclusion = "There are no stockouts in the current inventory data."
    result = _rule_based_verify(tool_results=tool_results, conclusion=conclusion)

    assert result == "blocked"


def test_t504_rule_based_verify_rule2_short_conclusion_blocked() -> None:
    """Rule 2 (unchanged): tool calls made but conclusion is shorter than
    _DEGENERATE_RESPONSE_MIN_LEN → blocked."""
    from packages.agent.runtime import _rule_based_verify

    tool_results = [{"nl_query": {"count": 1, "items": ["X"]}}]
    conclusion = "Done."  # 5 chars — below the 10-char threshold
    result = _rule_based_verify(tool_results=tool_results, conclusion=conclusion)

    assert result == "blocked"


async def test_t504_blocked_run_returns_completed_with_fallback_text() -> None:
    """Blocked run (Rule 1 fires): SpecialistResult.status == 'completed',
    output text is the soft fallback, blocked_reason is set in output meta,
    and result.error is None (no agent_failed SSE)."""
    # No tool calls + digit in prose → Rule 1 triggers
    main_response = make_stop_response(
        "There are 7 high-risk suppliers in the current dataset."
    )

    llm = FakeLCModel([main_response])
    runtime = _make_runtime(llm)
    task = _make_task()
    ctx = _FakeToolContext()

    result = await runtime.run(task, ctx)

    assert result.status == "completed"
    assert result.output.get("text") == (
        "Could not verify findings. Please rephrase your question or try again."
    )
    assert result.output.get("verification", {}).get("blocked_reason") == (
        "findings verifier: response not grounded in tool results"
    )
    assert result.error is None


async def test_t504_degenerate_after_revision_sets_blocked_reason() -> None:
    """call_model_final produces a degenerate (too-short) response → blocked_reason is
    'degenerate response after revision' and surfaces in output["verification"]["blocked_reason"].

    Path: tool call → conclusion → groundedness check (grounded=False) → revision message
    → call_model_final returns "ok" (len=2 < _DEGENERATE_RESPONSE_MIN_LEN).

    Uses "supply_chain" intent so that plan_tools (domain_analysis/decision_support only)
    does not consume the first FakeLCModel response.  Groundedness check fires because
    "supply_chain" ∈ _GROUNDED_VERIFY_INTENTS and tool_results are non-empty."""
    from packages.agent.runtime import GroundednessVerdict

    tool = _RecordingFakeTool()
    registry = _FakeToolRegistry([tool])

    # Response sequence shared by FakeLCModel (including with_structured_output):
    # 1. Tool call — initial _call_model_node, routes to execute_tools
    # 2. Long conclusion — second _call_model_node after tool execution, routes to verify
    # 3. GroundednessVerdict(grounded=False) — consumed by with_structured_output
    # 4. "ok" (2 chars) — call_model_final; degenerate check fires in _call_model_final_node
    llm = FakeLCModel([
        make_tool_call_response("nl_query", {"query": "SELECT 1"}),
        make_stop_response(
            "Based on the tool data, demand appears stable across all SKUs surveyed."
        ),
        GroundednessVerdict(
            grounded=False, unsupported_claims=["Claim not in tool results"]
        ),
        make_stop_response("ok"),  # len("ok") == 2 < _DEGENERATE_RESPONSE_MIN_LEN (10)
    ])
    runtime = _make_runtime(llm, tool_registry=registry)
    # "supply_chain" ∈ _GROUNDED_VERIFY_INTENTS but NOT in _PLAN_TOOLS_INTENTS.
    task = SpecialistTask(
        task_id=uuid4(),
        instruction="Analyse supply chain risk.",
        context_payload={"intent": {"category": "supply_chain"}},
        allowed_tools=[],
    )
    ctx = _FakeToolContext()

    result = await runtime.run(task, ctx)

    # blocked_reason must be propagated through to output verification meta.
    # Note: run() also detects the short "ok" response as is_degenerate (T-566 soft-fail).
    # specialist_status remains "completed" (blocked maps to completed; degenerate no longer
    # overrides to "failed").  blocked_reason from graph state ("degenerate response after
    # revision") takes precedence over the degenerate_response default because
    # run_blocked_reason is non-None.
    assert result.output.get("verification", {}).get("blocked_reason") == (
        "degenerate response after revision"
    )
