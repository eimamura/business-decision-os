from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest

from packages.agent.llm import LLMMessage, LLMResponse, LLMUsage
from packages.agent.orchestrator.models import SpecialistTask
from packages.agent.runtime import AgentRuntime


# ---------------------------------------------------------------------------
# Helpers / fakes
# ---------------------------------------------------------------------------

def _make_usage() -> LLMUsage:
    return LLMUsage(
        input_tokens=10,
        output_tokens=5,
        total_cost_usd=Decimal("0"),
    )


def _stop_response(text: str = "The analysis shows demand is stable.") -> LLMResponse:
    return LLMResponse(
        text=text,
        tool_calls=[],
        finish_reason="stop",
        usage=_make_usage(),
        model="claude-sonnet-4-6-test",
        request_id=str(uuid4()),
        latency_ms=1,
    )


class _RecordingLLMClient:
    """A mock LLM client that records every `complete()` call and returns
    pre-configured responses in order."""

    def __init__(self, responses: list[LLMResponse]) -> None:
        self._responses = list(responses)
        self._calls: list[list[LLMMessage]] = []
        self._model = "claude-sonnet-4-6-mock"

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
        self._calls.append(list(messages))
        if not self._responses:
            return _stop_response("fallback")
        return self._responses.pop(0)


class _FakeTool:
    name = "sql_query"
    description = "Run SQL"
    input_schema: dict[str, Any] = {}
    requires_approval = False

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
    llm = _RecordingLLMClient([_stop_response()])
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
    llm = _RecordingLLMClient([_stop_response()])
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
    main_response = _stop_response("Demand is trending upward based on analysis.")
    verifier_response = _stop_response("needs_revision: conclusion overstates the data")
    retry_response = _stop_response("Demand is stable based on the SQL results.")

    llm = _RecordingLLMClient([main_response, verifier_response, retry_response])
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
    main_response = _stop_response("Demand is stable.")
    verifier_response = _stop_response("pass: conclusion is well-grounded")

    llm = _RecordingLLMClient([main_response, verifier_response])
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
    main_response = _stop_response("Demand is stable.")
    verifier_response = _stop_response("blocked: fabricated data detected")

    llm = _RecordingLLMClient([main_response, verifier_response])
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
    main_response = _stop_response("Demand is stable.")
    verifier_response = _stop_response("needs_revision: missing detail")
    retry_response = _stop_response("Here is the revised answer.")

    llm = _RecordingLLMClient([main_response, verifier_response, retry_response])
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
                return _stop_response("Demand is stable.")
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

    llm = _RecordingLLMClient([
        _stop_response("Final answer from agent."),
        _stop_response("pass"),
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
