from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from packages.agent.llm import LLMMessage, LLMResponse
from packages.agent.orchestrator.models import SpecialistTask
from packages.agent.runtime import SUMMARY_THRESHOLD, AgentRuntime
from tests.unit.helpers import RecordingLLMClient, make_stop_response, make_tool_call_response


class _FakeTool:
    name = "sql_query"
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
    llm_client: Any,
    tool_registry: Any | None = None,
) -> AgentRuntime:
    return AgentRuntime(
        name="test_agent",
        role="data_engineer",
        llm_client=llm_client,
        tool_registry=tool_registry or _FakeToolRegistry(),
        sse_queue=None,
        system_prompt="You are a test specialist.",
    )


# ---------------------------------------------------------------------------
# T-008: 3-block prompt caching
# ---------------------------------------------------------------------------


async def test_t008_system_message_has_three_content_blocks() -> None:
    """The first complete() call must receive a system LLMMessage whose
    content_blocks has exactly 3 elements with the correct cache_control
    values (ephemeral on blocks 0 and 1, absent on block 2)."""
    llm = RecordingLLMClient([make_stop_response()])
    runtime = _make_runtime(llm)
    task = _make_task()
    ctx = _FakeToolContext()

    await runtime.run(task, ctx)

    assert llm._calls, "No LLM calls were recorded"
    first_call_messages = llm._calls[0]

    system_msgs = [m for m in first_call_messages if m.role == "system"]
    assert len(system_msgs) == 1, "Expected exactly one system message"

    system_msg = system_msgs[0]
    blocks = system_msg.content_blocks
    assert blocks is not None, "system LLMMessage.content_blocks must not be None"
    assert len(blocks) == 3, f"Expected 3 content blocks, got {len(blocks)}"

    # Block 0: static base prompt — must have ephemeral cache_control
    assert blocks[0].get("type") == "text"
    assert blocks[0].get("cache_control") == {"type": "ephemeral"}, (
        f"Block 0 must have ephemeral cache_control, got: {blocks[0].get('cache_control')}"
    )
    assert "You are a test specialist." in blocks[0]["text"]

    # Block 1: schema context — must have ephemeral cache_control
    assert blocks[1].get("type") == "text"
    assert blocks[1].get("cache_control") == {"type": "ephemeral"}, (
        f"Block 1 must have ephemeral cache_control, got: {blocks[1].get('cache_control')}"
    )

    # Block 2: dynamic context — must NOT have cache_control
    assert blocks[2].get("type") == "text"
    assert "cache_control" not in blocks[2], (
        f"Block 2 must NOT have cache_control, got: {blocks[2].get('cache_control')}"
    )
    assert "Role:" in blocks[2]["text"]
    assert "Available tools:" in blocks[2]["text"]


async def test_t008_system_block_texts_are_correct_types() -> None:
    """Each block must be a dict with at least 'type' and 'text' keys."""
    llm = RecordingLLMClient([make_stop_response()])
    runtime = _make_runtime(llm)
    task = _make_task()
    ctx = _FakeToolContext()

    await runtime.run(task, ctx)

    first_call_messages = llm._calls[0]
    system_msg = [m for m in first_call_messages if m.role == "system"][0]
    blocks = system_msg.content_blocks
    assert blocks is not None

    for i, block in enumerate(blocks):
        assert isinstance(block, dict), f"Block {i} must be a dict"
        assert block.get("type") == "text", f"Block {i} type must be 'text'"
        assert isinstance(block.get("text"), str), f"Block {i} text must be a str"


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

    llm = RecordingLLMClient([main_response, verifier_response, retry_response])
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

    llm = RecordingLLMClient([main_response, verifier_response])
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
    """When the verifier returns 'blocked', the loop does NOT retry — runtime
    still returns a completed result (blocked is not an error, it continues)."""
    main_response = make_stop_response("Demand is stable.")
    verifier_response = make_stop_response("blocked: fabricated data detected")

    llm = RecordingLLMClient([main_response, verifier_response])
    runtime = _make_runtime(llm)
    task = _make_task()
    ctx = _FakeToolContext()

    result = await runtime.run(task, ctx)

    assert result.status == "completed"
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

    llm = RecordingLLMClient([main_response, verifier_response, retry_response])
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

    class _FailOnVerifier:
        _model = "mock"

        async def complete(
            self,
            messages: list[LLMMessage],
            tools: Any = None,
            temperature: float = 0.0,
            max_tokens: int = 4096,
            prompt_cache: bool = True,
            agent_step_id: Any = None,
            specialist_role: Any = None,
        ) -> LLMResponse:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Main loop call — succeeds
                return make_stop_response("Demand is stable.")
            # Verifier call — raises
            raise RuntimeError("LLM API error")

    runtime = _make_runtime(_FailOnVerifier())
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

    llm = RecordingLLMClient([
        make_stop_response("Final answer from agent."),
        make_stop_response("pass"),
    ])
    runtime = AgentRuntime(
        name="test",
        role="data_engineer",
        llm_client=llm,
        tool_registry=_FakeToolRegistry(),
        output_builder=_custom_builder,
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
    llm = RecordingLLMClient([stop_resp, verifier_resp])
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
    # The LLM client receives calls in order:
    #   1. compress_history summarization call (35 - 10 = 25 oldest messages)
    #   2. call_model call (receives compressed_messages: 11 messages)
    #   3. verify_findings call
    summary_resp = make_stop_response("Summary of 25 messages.")
    main_resp = make_stop_response("Final conclusion based on compressed context.")
    verifier_resp = make_stop_response("pass")

    class RecordingLLMClientWithMessageCount(RecordingLLMClient):
        """Also records the message count for each call."""

        def __init__(self, responses: list[LLMResponse]) -> None:
            super().__init__(responses)
            self.message_counts: list[int] = []

        async def complete(
            self,
            messages: list[LLMMessage],
            tools: Any = None,
            temperature: float = 0.0,
            max_tokens: int = 4096,
            prompt_cache: bool = True,
            agent_step_id: Any = None,
            specialist_role: Any = None,
        ) -> LLMResponse:
            self.message_counts.append(len(messages))
            return await super().complete(
                messages=messages,
                tools=tools,
                temperature=temperature,
                max_tokens=max_tokens,
                prompt_cache=prompt_cache,
                agent_step_id=agent_step_id,
                specialist_role=specialist_role,
            )

    llm = RecordingLLMClientWithMessageCount([summary_resp, main_resp, verifier_resp])
    _make_runtime(llm)  # pre-warms import paths; actual test uses summarize_runtime below

    # Build initial state with 35 messages by injecting extra messages via a
    # custom run — we patch the graph's initial_state directly.
    # We do this by adding 33 extra user messages to the task instruction; the
    # graph builds initial_messages from the task so we instead use a fake
    # task with many messages by subclassing and injecting into initial_state.
    #
    # Since we cannot easily inject into run() directly, we drive the graph
    # node logic at a lower level: call _compress_history_node directly to
    # check the output, then verify the end-to-end path via run().

    # -- Direct node test: verify compress_history output --
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

    # Use a fresh single-response summarization LLM to avoid consuming responses.
    summarize_llm = RecordingLLMClient([make_stop_response("Compact summary of early messages.")])
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
    llm = RecordingLLMClient([stop_resp, verifier_resp])

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

    llm = RecordingLLMClient([])
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

    llm = RecordingLLMClient([])
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

    llm = RecordingLLMClient([make_stop_response("Analysis complete."), make_stop_response("pass")])
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
    "verifier_text,expected_call_count",
    [
        ("needs_revision: minor issues found", 3),
        ("pass: all good", 2),
        ("blocked: fabricated data", 2),
    ],
    ids=["needs_revision_calls_model_twice", "pass_calls_model_once", "blocked_calls_model_once"],
)
async def test_t073_verify_findings_retry_call_counts(
    verifier_text: str, expected_call_count: int
) -> None:
    """verify_findings retry behavior: needs_revision triggers a second call_model invocation."""
    main_resp = make_stop_response("Initial conclusion.")
    verifier_resp = make_stop_response(verifier_text)
    retry_resp = make_stop_response("Revised conclusion.")

    responses = [main_resp, verifier_resp]
    if expected_call_count == 3:
        responses.append(retry_resp)

    llm = RecordingLLMClient(responses)
    runtime = _make_runtime(llm)
    task = _make_task()
    ctx = _FakeToolContext()

    result = await runtime.run(task, ctx)

    assert result.status == "completed"
    assert len(llm._calls) == expected_call_count, (
        f"verifier='{verifier_text}': expected {expected_call_count} LLM calls, "
        f"got {len(llm._calls)}"
    )


async def test_t073_compress_history_noop_below_threshold_zero_summarize_calls() -> None:
    """When len(messages) <= SUMMARY_THRESHOLD, compress_history makes zero LLM calls
    (the summarize LLM call is never made)."""
    stop_resp = make_stop_response("ok")
    verifier_resp = make_stop_response("pass")
    llm = RecordingLLMClient([stop_resp, verifier_resp])
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
    summarize_llm = RecordingLLMClient([summary_resp])
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
    name = "sql_query"
    description = "Run SQL"
    input_schema: dict[str, Any] = {}

    def __init__(self) -> None:
        self.handle = AsyncMock(return_value=_make_tool_result({"rows": [{"sku": "A", "qty": 10}]}))


def _make_tool_result(output: dict[str, Any]) -> Any:
    from packages.tools.base import ToolResult
    return ToolResult(output=output, audit_payload={})


class _FailingTool:
    name = "sql_query"
    description = "Run SQL"
    input_schema: dict[str, Any] = {}

    async def handle(self, input: dict[str, Any], ctx: Any) -> Any:
        raise RuntimeError("tool failed")


async def test_execute_tools_tool_call_handle_is_called_and_result_fed_to_next_llm() -> None:
    tool = _RecordingFakeTool()
    registry = _FakeToolRegistry([tool])

    llm = RecordingLLMClient([
        make_tool_call_response("sql_query", {"query": "SELECT 1"}),
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

    second_call_messages = llm._calls[1]
    tool_messages = [m for m in second_call_messages if m.role == "tool"]
    assert len(tool_messages) == 1
    assert tool_messages[0].tool_call_id == "call_001"

    payload = json.loads(tool_messages[0].content)
    assert payload == {"rows": [{"sku": "A", "qty": 10}]}


async def test_execute_tools_unknown_tool_skips_handle_and_no_tool_message_added() -> None:
    registry = _FakeToolRegistry([])

    llm = RecordingLLMClient([
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
    tool_messages = [m for m in second_call_messages if m.role == "tool"]
    assert tool_messages == []


async def test_execute_tools_failing_tool_propagates_exception() -> None:
    registry = _FakeToolRegistry([_FailingTool()])

    llm = RecordingLLMClient([
        make_tool_call_response("sql_query", {}),
    ])
    runtime = _make_runtime(llm, tool_registry=registry)
    task = _make_task()
    ctx = _FakeToolContext()

    with pytest.raises(RuntimeError, match="tool failed"):
        await runtime.run(task, ctx)
