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
# T-007: verify_findings step
# ---------------------------------------------------------------------------


async def test_t007_needs_revision_retries_loop_once() -> None:
    """When the verifier returns 'needs_revision', the tool loop runs a second
    time (retry), and then the runtime produces a final SpecialistResult."""
    # Call sequence:
    #   1. Main tool loop LLM call  -> stop response (conclusion)
    #   2. Verifier LLM call        -> "needs_revision: some issues found"
    #   3. Retry tool loop LLM call -> stop response (revised conclusion)
    # Total: 3 LLM calls
    main_response = make_stop_response("Demand is trending upward based on analysis.")
    verifier_response = make_stop_response("needs_revision: conclusion overstates the data")
    retry_response = make_stop_response("Demand is stable based on the SQL results.")

    llm = FakeLCModel([main_response, verifier_response, retry_response])
    runtime = _make_runtime(llm)
    task = _make_task()
    ctx = _FakeToolContext()

    result = await runtime.run(task, ctx)

    # Must produce a completed result (not raise)
    assert result.status == "completed"

    # 3 calls: main loop, verifier, retry loop
    assert len(llm._calls) == 3, (
        f"Expected 3 LLM calls (main + verifier + retry), got {len(llm._calls)}"
    )


async def test_t007_pass_does_not_retry() -> None:
    """When the verifier returns 'pass', no retry happens — only 2 LLM calls total."""
    main_response = make_stop_response("Demand is stable.")
    verifier_response = make_stop_response("pass: conclusion is well-grounded")

    llm = FakeLCModel([main_response, verifier_response])
    runtime = _make_runtime(llm)
    task = _make_task()
    ctx = _FakeToolContext()

    result = await runtime.run(task, ctx)

    assert result.status == "completed"
    # 2 calls: main loop + verifier
    assert len(llm._calls) == 2, (
        f"Expected 2 LLM calls (main + verifier), got {len(llm._calls)}"
    )


async def test_t007_blocked_does_not_retry() -> None:
    """When the verifier returns 'blocked', the loop does NOT retry.
    Since P60-B-04 the runtime maps blocked → status='failed' so that the
    orchestrator can surface a safe fallback message rather than fabricated text."""
    main_response = make_stop_response("Demand is stable.")
    verifier_response = make_stop_response("blocked: fabricated data detected")

    llm = FakeLCModel([main_response, verifier_response])
    runtime = _make_runtime(llm)
    task = _make_task()
    ctx = _FakeToolContext()

    result = await runtime.run(task, ctx)

    assert result.status == "failed"
    # 2 calls: main loop + verifier only (no retry on blocked)
    assert len(llm._calls) == 2, (
        f"Expected 2 LLM calls (main + verifier), got {len(llm._calls)}"
    )


async def test_t007_needs_revision_only_retries_once() -> None:
    """When verifier returns 'needs_revision', the tool loop retries exactly once.
    After the retry, the runtime builds the final result without another verification
    round (_verify_findings_done guard prevents an infinite loop).

    Call sequence:
      1. Main tool loop call  -> stop response
      2. Verifier call        -> needs_revision
      3. Retry tool loop call -> stop response (final — no second verifier call)
    Total: 3 LLM calls.
    """
    main_response = make_stop_response("Demand is stable.")
    verifier_response = make_stop_response("needs_revision: missing detail")
    retry_response = make_stop_response("Here is the revised answer.")

    llm = FakeLCModel([main_response, verifier_response, retry_response])
    runtime = _make_runtime(llm)
    task = _make_task()
    ctx = _FakeToolContext()

    result = await runtime.run(task, ctx)

    assert result.status == "completed"
    # Exactly 3 calls: main loop + verifier + retry loop.
    # The _verify_findings_done flag prevents a second verification pass.
    assert len(llm._calls) == 3, (
        f"Expected 3 LLM calls (main + verifier + retry), got {len(llm._calls)}"
    )


async def test_t007_verifier_failure_defaults_to_pass() -> None:
    """If the verifier LLM call raises an exception, runtime defaults to 'pass'
    and returns a completed result without retrying."""
    call_count = 0

    class _FailOnSecondCall(FakeLCModel):
        """Returns a valid response on the first ainvoke, raises on the second."""

        async def ainvoke(self, messages: Any, **kwargs: Any) -> Any:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return await super().ainvoke(messages, **kwargs)
            raise RuntimeError("LLM API error")

    llm = _FailOnSecondCall([make_stop_response("Demand is stable.")])
    runtime = _make_runtime(llm)
    task = _make_task()
    ctx = _FakeToolContext()

    result = await runtime.run(task, ctx)

    assert result.status == "completed"
    assert call_count == 2  # main call + failed verifier call (no retry)


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

    llm = FakeLCModel([
        make_stop_response("Final answer from agent."),
        make_stop_response("pass"),
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

    assert result.output.get("text") == "Final answer from agent."


# ---------------------------------------------------------------------------
# T-072: compress_history pre-processing node
# ---------------------------------------------------------------------------


async def test_t072_compress_history_noop_below_threshold() -> None:
    """When message count is at or below SUMMARY_THRESHOLD, compress_history
    makes zero LLM calls."""
    # 2 system/user initial messages + SUMMARY_THRESHOLD - 2 extra user messages
    # equals exactly SUMMARY_THRESHOLD total — no compression should occur.
    # We expect: 1 main LLM call + 1 verifier call = 2 total.
    stop_resp = make_stop_response("All good.")
    verifier_resp = make_stop_response("pass: well-grounded")
    llm = FakeLCModel([stop_resp, verifier_resp])
    runtime = _make_runtime(llm)
    task = _make_task()
    ctx = _FakeToolContext()

    result = await runtime.run(task, ctx)

    assert result.status == "completed"
    # Exactly 2 calls: main + verifier. No summarization call.
    assert len(llm._calls) == 2, (
        f"Expected 2 LLM calls (no compression), got {len(llm._calls)}"
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
    stop_resp = make_stop_response("done")
    verifier_resp = make_stop_response("pass")
    llm = FakeLCModel([stop_resp, verifier_resp])

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


def test_t073_graph_also_has_revision_nodes() -> None:
    """Graph must also contain the add_revision_message and call_model_final nodes."""
    from langgraph.checkpoint.memory import MemorySaver

    llm = FakeLCModel([])
    runtime = _make_runtime(llm)
    graph = runtime._build_graph(checkpointer=MemorySaver())

    node_names = set(graph.nodes.keys())
    for name in ("add_revision_message", "call_model_final"):
        assert name in node_names, (
            f"Expected node '{name}' in graph, found: {node_names}"
        )


async def test_t073_specialist_result_shape_after_run() -> None:
    """SpecialistResult returned by run() must have the correct shape."""
    from packages.agent.orchestrator import SpecialistResult

    llm = FakeLCModel([make_stop_response("Analysis complete."), make_stop_response("pass")])
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
    "verifier_text,expected_call_count,expected_status",
    [
        ("needs_revision: minor issues found", 3, "completed"),
        ("pass: all good", 2, "completed"),
        # Since P60-B-04 blocked maps to specialist_status="failed"
        ("blocked: fabricated data", 2, "failed"),
    ],
    ids=["needs_revision_calls_model_twice", "pass_calls_model_once", "blocked_calls_model_once"],
)
async def test_t073_verify_findings_retry_call_counts(
    verifier_text: str, expected_call_count: int, expected_status: str
) -> None:
    """verify_findings retry behavior: needs_revision triggers a second call_model invocation.
    Since P60-B-04, blocked → specialist_status='failed'."""
    main_resp = make_stop_response("Initial conclusion.")
    verifier_resp = make_stop_response(verifier_text)
    retry_resp = make_stop_response("Revised conclusion.")

    responses = [main_resp, verifier_resp]
    if expected_call_count == 3:
        responses.append(retry_resp)

    llm = FakeLCModel(responses)
    runtime = _make_runtime(llm)
    task = _make_task()
    ctx = _FakeToolContext()

    result = await runtime.run(task, ctx)

    assert result.status == expected_status, (
        f"verifier='{verifier_text}': expected status '{expected_status}', got '{result.status}'"
    )
    assert len(llm._calls) == expected_call_count, (
        f"verifier='{verifier_text}': expected {expected_call_count} LLM calls, "
        f"got {len(llm._calls)}"
    )


async def test_t073_compress_history_noop_below_threshold_zero_summarize_calls() -> None:
    """When len(messages) <= SUMMARY_THRESHOLD, compress_history makes zero LLM calls
    (the summarize LLM call is never made)."""
    stop_resp = make_stop_response("ok")
    verifier_resp = make_stop_response("pass")
    llm = FakeLCModel([stop_resp, verifier_resp])
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


async def test_t073_compress_history_active_above_threshold_reduces_to_11() -> None:
    """When len(messages) > SUMMARY_THRESHOLD, compressed_messages has at most 11 items."""
    summary_resp = make_stop_response("Compact summary.")
    summarize_llm = FakeLCModel([summary_resp])
    runtime = _make_runtime(summarize_llm)

    msg_count = SUMMARY_THRESHOLD + 5
    fake_state: Any = {
        "messages": [LLMMessage(role="user", content=f"msg {i}") for i in range(msg_count)],
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

    compressed = result_dict.get("compressed_messages")
    assert compressed is not None, "compress_history must set compressed_messages above threshold"
    assert len(compressed) <= 11, (
        f"call_model must receive <= 11 messages after compression, got {len(compressed)}"
    )
    # Exactly one summarize call was made
    assert len(summarize_llm._calls) == 1


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

    llm = FakeLCModel([
        make_tool_call_response("nl_query", {"query": "SELECT 1"}),
        make_stop_response("Tool result processed."),
        make_stop_response("pass"),
    ])
    runtime = _make_runtime(llm, tool_registry=registry)
    task = _make_task()
    ctx = _FakeToolContext()

    result = await runtime.run(task, ctx)

    assert result.status == "completed"
    assert len(llm._calls) == 3

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

    llm = FakeLCModel([
        make_tool_call_response("nonexistent_tool", {}),
        make_stop_response("Skipped unknown tool."),
        make_stop_response("pass"),
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
