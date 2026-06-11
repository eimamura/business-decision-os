"""Unit tests for UsageRecordingCallbackHandler (T-525).

Tests:
1. on_chat_model_start + on_llm_end with usage_metadata → writer called once with correct
   model name, token counts, serialized prompt/response.
2. Metadata propagation: session_id / agent_step_id / specialist_role from run metadata
   reach the writer.
3. Writer raising an exception does not propagate to the caller.
4. on_llm_end without a prior matching on_chat_model_start does not crash.

Zero-network rule: all LLMResult / AIMessage objects are constructed directly
from langchain_core types — no real model calls.
asyncio_mode=auto — no @pytest.mark.asyncio.
"""
from __future__ import annotations

import json
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult

from packages.agent.llm import LLMUsage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ai_message(
    content: str = "Hello from model",
    model: str = "claude-sonnet-4-6",
    input_tokens: int = 10,
    output_tokens: int = 5,
    tool_calls: list[dict[str, Any]] | None = None,
) -> AIMessage:
    """Build an AIMessage with usage_metadata, response_metadata, and optional tool_calls."""
    usage_metadata: dict[str, Any] = {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
    }
    response_metadata: dict[str, Any] = {"model": model}
    kwargs: dict[str, Any] = {
        "content": content,
        "usage_metadata": usage_metadata,
        "response_metadata": response_metadata,
    }
    if tool_calls:
        kwargs["tool_calls"] = tool_calls
    return AIMessage(**kwargs)


def _make_llm_result(ai_message: AIMessage) -> LLMResult:
    """Wrap an AIMessage in a minimal LLMResult."""
    generation = ChatGeneration(message=ai_message)
    return LLMResult(generations=[[generation]])


def _make_handler(writer: Any | None = None) -> Any:
    """Instantiate UsageRecordingCallbackHandler with a writer (default: AsyncMock)."""
    from packages.agent.llm.usage_recording import UsageRecordingCallbackHandler

    return UsageRecordingCallbackHandler(
        writer=writer or AsyncMock(),
        provider="ollama",
        fallback_model_name="unknown",
    )


# ---------------------------------------------------------------------------
# 1. Basic round-trip: on_chat_model_start → on_llm_end
# ---------------------------------------------------------------------------


async def test_handler_writer_called_once_after_start_and_end() -> None:
    """Writer is called exactly once after a matching start/end pair."""
    writer = AsyncMock()
    handler = _make_handler(writer)
    run_id = uuid4()

    from langchain_core.messages import HumanMessage

    await handler.on_chat_model_start(
        serialized={},
        messages=[[HumanMessage(content="Analyze demand")]],
        run_id=run_id,
        metadata={},
    )

    ai_msg = _make_ai_message(content="Demand is up.", model="claude-sonnet-4-6")
    result = _make_llm_result(ai_msg)

    await handler.on_llm_end(response=result, run_id=run_id)

    writer.assert_awaited_once()


async def test_handler_writer_receives_correct_model_name() -> None:
    """Writer receives the model name extracted from AIMessage.response_metadata."""
    captured: list[Any] = []

    async def _writer(*args: Any) -> None:
        captured.extend(args)

    handler = _make_handler(_writer)
    run_id = uuid4()

    from langchain_core.messages import HumanMessage

    await handler.on_chat_model_start(
        serialized={},
        messages=[[HumanMessage(content="test")]],
        run_id=run_id,
        metadata={},
    )

    ai_msg = _make_ai_message(model="gemma4:12b")
    result = _make_llm_result(ai_msg)

    await handler.on_llm_end(response=result, run_id=run_id)

    # writer signature: (session_id, agent_step_id, specialist_role, provider, model_name, usage)
    model_name = captured[4]
    assert model_name == "gemma4:12b"


async def test_handler_writer_receives_correct_token_counts() -> None:
    """Writer's LLMUsage contains input_tokens and output_tokens from usage_metadata."""
    captured_usage: list[LLMUsage] = []

    async def _writer(
        session_id: Any,
        agent_step_id: Any,
        specialist_role: Any,
        provider: Any,
        model_name: Any,
        usage: LLMUsage,
    ) -> None:
        captured_usage.append(usage)

    handler = _make_handler(_writer)
    run_id = uuid4()

    from langchain_core.messages import HumanMessage

    await handler.on_chat_model_start(
        serialized={},
        messages=[[HumanMessage(content="test")]],
        run_id=run_id,
        metadata={},
    )

    ai_msg = _make_ai_message(input_tokens=123, output_tokens=456)
    result = _make_llm_result(ai_msg)

    await handler.on_llm_end(response=result, run_id=run_id)

    assert len(captured_usage) == 1
    assert captured_usage[0].input_tokens == 123
    assert captured_usage[0].output_tokens == 456


async def test_handler_writer_receives_serialized_prompt() -> None:
    """LLMUsage.prompt_messages_json is a non-None JSON string containing the prompt."""
    captured_usage: list[LLMUsage] = []

    async def _writer(*args: Any) -> None:
        captured_usage.append(args[-1])  # last arg is LLMUsage

    handler = _make_handler(_writer)
    run_id = uuid4()

    from langchain_core.messages import HumanMessage, SystemMessage

    await handler.on_chat_model_start(
        serialized={},
        messages=[[SystemMessage(content="You are an agent"), HumanMessage(content="Analyze")]],
        run_id=run_id,
        metadata={},
    )

    ai_msg = _make_ai_message(content="Done.")
    result = _make_llm_result(ai_msg)
    await handler.on_llm_end(response=result, run_id=run_id)

    assert captured_usage[0].prompt_messages_json is not None
    parsed = json.loads(captured_usage[0].prompt_messages_json)
    assert isinstance(parsed, list)
    assert len(parsed) == 2


async def test_handler_writer_receives_response_text() -> None:
    """LLMUsage.response_text matches the AIMessage content string."""
    captured_usage: list[LLMUsage] = []

    async def _writer(*args: Any) -> None:
        captured_usage.append(args[-1])

    handler = _make_handler(_writer)
    run_id = uuid4()

    from langchain_core.messages import HumanMessage

    await handler.on_chat_model_start(
        serialized={},
        messages=[[HumanMessage(content="test")]],
        run_id=run_id,
        metadata={},
    )

    ai_msg = _make_ai_message(content="Supply chain response.")
    result = _make_llm_result(ai_msg)
    await handler.on_llm_end(response=result, run_id=run_id)

    assert captured_usage[0].response_text == "Supply chain response."


# ---------------------------------------------------------------------------
# 2. Metadata propagation: session_id / agent_step_id / specialist_role
# ---------------------------------------------------------------------------


async def test_handler_metadata_session_id_propagates_to_writer() -> None:
    """session_id from run metadata reaches the writer as a UUID."""
    captured: list[Any] = []

    async def _writer(*args: Any) -> None:
        captured.extend(args)

    handler = _make_handler(_writer)
    run_id = uuid4()
    session_id = uuid4()

    from langchain_core.messages import HumanMessage

    await handler.on_chat_model_start(
        serialized={},
        messages=[[HumanMessage(content="test")]],
        run_id=run_id,
        metadata={"session_id": str(session_id)},
    )

    result = _make_llm_result(_make_ai_message())
    await handler.on_llm_end(response=result, run_id=run_id)

    # writer signature: (session_id, agent_step_id, specialist_role, provider, model_name, usage)
    assert captured[0] == session_id


async def test_handler_metadata_agent_step_id_propagates_to_writer() -> None:
    """agent_step_id from run metadata reaches the writer as a UUID."""
    captured: list[Any] = []

    async def _writer(*args: Any) -> None:
        captured.extend(args)

    handler = _make_handler(_writer)
    run_id = uuid4()
    step_id = uuid4()

    from langchain_core.messages import HumanMessage

    await handler.on_chat_model_start(
        serialized={},
        messages=[[HumanMessage(content="test")]],
        run_id=run_id,
        metadata={"agent_step_id": str(step_id)},
    )

    result = _make_llm_result(_make_ai_message())
    await handler.on_llm_end(response=result, run_id=run_id)

    assert captured[1] == step_id


async def test_handler_metadata_specialist_role_propagates_to_writer() -> None:
    """specialist_role from run metadata reaches the writer as a string."""
    captured: list[Any] = []

    async def _writer(*args: Any) -> None:
        captured.extend(args)

    handler = _make_handler(_writer)
    run_id = uuid4()

    from langchain_core.messages import HumanMessage

    await handler.on_chat_model_start(
        serialized={},
        messages=[[HumanMessage(content="test")]],
        run_id=run_id,
        metadata={"specialist_role": "control"},
    )

    result = _make_llm_result(_make_ai_message())
    await handler.on_llm_end(response=result, run_id=run_id)

    assert captured[2] == "control"


async def test_handler_metadata_all_three_fields_propagate_together() -> None:
    """session_id, agent_step_id, and specialist_role all reach the writer together."""
    captured: list[Any] = []

    async def _writer(*args: Any) -> None:
        captured.extend(args)

    handler = _make_handler(_writer)
    run_id = uuid4()
    session_id = uuid4()
    step_id = uuid4()

    from langchain_core.messages import HumanMessage

    await handler.on_chat_model_start(
        serialized={},
        messages=[[HumanMessage(content="test")]],
        run_id=run_id,
        metadata={
            "session_id": str(session_id),
            "agent_step_id": str(step_id),
            "specialist_role": "orchestrator",
        },
    )

    result = _make_llm_result(_make_ai_message())
    await handler.on_llm_end(response=result, run_id=run_id)

    assert captured[0] == session_id
    assert captured[1] == step_id
    assert captured[2] == "orchestrator"


async def test_handler_metadata_none_when_not_provided() -> None:
    """When metadata is empty, session_id, agent_step_id, specialist_role are all None."""
    captured: list[Any] = []

    async def _writer(*args: Any) -> None:
        captured.extend(args)

    handler = _make_handler(_writer)
    run_id = uuid4()

    from langchain_core.messages import HumanMessage

    await handler.on_chat_model_start(
        serialized={},
        messages=[[HumanMessage(content="test")]],
        run_id=run_id,
        metadata={},
    )

    result = _make_llm_result(_make_ai_message())
    await handler.on_llm_end(response=result, run_id=run_id)

    assert captured[0] is None   # session_id
    assert captured[1] is None   # agent_step_id
    assert captured[2] is None   # specialist_role


async def test_handler_invalid_session_id_does_not_crash() -> None:
    """An invalid session_id UUID string in metadata is silently skipped (logs warning)."""
    writer = AsyncMock()
    handler = _make_handler(writer)
    run_id = uuid4()

    from langchain_core.messages import HumanMessage

    await handler.on_chat_model_start(
        serialized={},
        messages=[[HumanMessage(content="test")]],
        run_id=run_id,
        metadata={"session_id": "not-a-uuid"},
    )

    result = _make_llm_result(_make_ai_message())
    await handler.on_llm_end(response=result, run_id=run_id)

    # Writer is still called; session_id is None (invalid UUID skipped)
    writer.assert_awaited_once()
    call_args = writer.call_args[0]
    assert call_args[0] is None  # session_id coerced to None


# ---------------------------------------------------------------------------
# 3. Writer raising an exception does not propagate to the caller
# ---------------------------------------------------------------------------


async def test_handler_writer_exception_does_not_propagate() -> None:
    """A writer that raises an exception must not crash the handler caller."""

    async def _raising_writer(*args: Any) -> None:
        raise RuntimeError("database unavailable")

    handler = _make_handler(_raising_writer)
    run_id = uuid4()

    from langchain_core.messages import HumanMessage

    await handler.on_chat_model_start(
        serialized={},
        messages=[[HumanMessage(content="test")]],
        run_id=run_id,
        metadata={},
    )

    result = _make_llm_result(_make_ai_message())

    # Must not raise
    await handler.on_llm_end(response=result, run_id=run_id)


async def test_handler_writer_exception_does_not_affect_subsequent_runs() -> None:
    """A writer failure on run 1 does not prevent successful processing of run 2."""
    call_count = 0

    async def _failing_first_writer(*args: Any) -> None:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("first call fails")

    handler = _make_handler(_failing_first_writer)

    from langchain_core.messages import HumanMessage

    for _ in range(2):
        run_id = uuid4()
        await handler.on_chat_model_start(
            serialized={},
            messages=[[HumanMessage(content="test")]],
            run_id=run_id,
            metadata={},
        )
        result = _make_llm_result(_make_ai_message())
        await handler.on_llm_end(response=result, run_id=run_id)

    assert call_count == 2


# ---------------------------------------------------------------------------
# 4. on_llm_end without a prior on_chat_model_start does not crash
# ---------------------------------------------------------------------------


async def test_handler_on_llm_end_without_prior_start_does_not_crash() -> None:
    """on_llm_end for an unknown run_id must return gracefully (benign no-op)."""
    writer = AsyncMock()
    handler = _make_handler(writer)
    unknown_run_id = uuid4()

    result = _make_llm_result(_make_ai_message())

    # Must not raise
    await handler.on_llm_end(response=result, run_id=unknown_run_id)

    # Writer must NOT be called when there is no matching start event
    writer.assert_not_awaited()


async def test_handler_on_llm_error_cleans_up_run_state() -> None:
    """on_llm_error removes the run state so a subsequent on_llm_end is a safe no-op."""
    writer = AsyncMock()
    handler = _make_handler(writer)
    run_id = uuid4()

    from langchain_core.messages import HumanMessage

    await handler.on_chat_model_start(
        serialized={},
        messages=[[HumanMessage(content="test")]],
        run_id=run_id,
        metadata={},
    )

    # Simulate an error
    await handler.on_llm_error(error=RuntimeError("timeout"), run_id=run_id)

    # State should be cleaned up — a late on_llm_end for the same run_id is a no-op
    result = _make_llm_result(_make_ai_message())
    await handler.on_llm_end(response=result, run_id=run_id)

    writer.assert_not_awaited()


# ---------------------------------------------------------------------------
# 5. Tool calls serialisation
# ---------------------------------------------------------------------------


async def test_handler_tool_calls_json_populated_when_tool_calls_present() -> None:
    """LLMUsage.tool_calls_json is a JSON array when the AIMessage has tool_calls."""
    captured_usage: list[LLMUsage] = []

    async def _writer(*args: Any) -> None:
        captured_usage.append(args[-1])

    handler = _make_handler(_writer)
    run_id = uuid4()

    from langchain_core.messages import HumanMessage

    await handler.on_chat_model_start(
        serialized={},
        messages=[[HumanMessage(content="test")]],
        run_id=run_id,
        metadata={},
    )

    tool_calls = [{"name": "nl_query", "id": "call_001", "args": {"query": "SELECT 1"}}]
    ai_msg = _make_ai_message(tool_calls=tool_calls)
    result = _make_llm_result(ai_msg)
    await handler.on_llm_end(response=result, run_id=run_id)

    assert captured_usage[0].tool_calls_json is not None
    parsed = json.loads(captured_usage[0].tool_calls_json)
    assert isinstance(parsed, list)
    assert len(parsed) == 1


async def test_handler_tool_calls_json_none_when_no_tool_calls() -> None:
    """LLMUsage.tool_calls_json is None when the AIMessage has no tool_calls."""
    captured_usage: list[LLMUsage] = []

    async def _writer(*args: Any) -> None:
        captured_usage.append(args[-1])

    handler = _make_handler(_writer)
    run_id = uuid4()

    from langchain_core.messages import HumanMessage

    await handler.on_chat_model_start(
        serialized={},
        messages=[[HumanMessage(content="test")]],
        run_id=run_id,
        metadata={},
    )

    ai_msg = _make_ai_message()  # no tool_calls
    result = _make_llm_result(ai_msg)
    await handler.on_llm_end(response=result, run_id=run_id)

    assert captured_usage[0].tool_calls_json is None


# ---------------------------------------------------------------------------
# 6. Model name fallback and llm_output path
# ---------------------------------------------------------------------------


async def test_handler_model_name_from_llm_output_takes_precedence() -> None:
    """When LLMResult.llm_output contains model_name, it is preferred over response_metadata."""
    captured: list[Any] = []

    async def _writer(*args: Any) -> None:
        captured.extend(args)

    handler = _make_handler(_writer)
    run_id = uuid4()

    from langchain_core.messages import HumanMessage

    await handler.on_chat_model_start(
        serialized={},
        messages=[[HumanMessage(content="test")]],
        run_id=run_id,
        metadata={},
    )

    ai_msg = _make_ai_message(model="response_meta_model")
    # Override llm_output with a different model name — this should take precedence
    result = LLMResult(
        generations=[[ChatGeneration(message=ai_msg)]],
        llm_output={"model_name": "llm_output_model"},
    )
    await handler.on_llm_end(response=result, run_id=run_id)

    model_name = captured[4]
    assert model_name == "llm_output_model"


async def test_handler_model_name_fallback_when_no_model_info() -> None:
    """When neither llm_output nor response_metadata has model info, fallback is used."""
    captured: list[Any] = []

    async def _writer(*args: Any) -> None:
        captured.extend(args)

    handler = _make_handler(_writer)
    handler._fallback_model_name = "my-fallback"
    run_id = uuid4()

    from langchain_core.messages import HumanMessage

    await handler.on_chat_model_start(
        serialized={},
        messages=[[HumanMessage(content="test")]],
        run_id=run_id,
        metadata={},
    )

    # AIMessage with no response_metadata and no llm_output
    # total_tokens is required by the AIMessage schema
    ai_msg = AIMessage(
        content="response",
        usage_metadata={"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
    )
    result = LLMResult(generations=[[ChatGeneration(message=ai_msg)]])
    await handler.on_llm_end(response=result, run_id=run_id)

    model_name = captured[4]
    assert model_name == "my-fallback"


# ---------------------------------------------------------------------------
# 7. Cache token extraction (Anthropic input_token_details)
# ---------------------------------------------------------------------------


async def test_handler_cache_tokens_extracted_from_input_token_details() -> None:
    """Cache read/write tokens are extracted from usage_metadata.input_token_details."""
    captured_usage: list[LLMUsage] = []

    async def _writer(*args: Any) -> None:
        captured_usage.append(args[-1])

    handler = _make_handler(_writer)
    run_id = uuid4()

    from langchain_core.messages import HumanMessage

    await handler.on_chat_model_start(
        serialized={},
        messages=[[HumanMessage(content="test")]],
        run_id=run_id,
        metadata={},
    )

    ai_msg = AIMessage(
        content="cached response",
        usage_metadata={
            "input_tokens": 100,
            "output_tokens": 20,
            "total_tokens": 120,
            "input_token_details": {
                "cache_read": 50,
                "cache_creation": 10,
            },
        },
    )
    result = _make_llm_result(ai_msg)
    await handler.on_llm_end(response=result, run_id=run_id)

    usage = captured_usage[0]
    assert usage.cache_read_tokens == 50
    assert usage.cache_write_tokens == 10


# ---------------------------------------------------------------------------
# 8. Multiple concurrent runs do not interfere
# ---------------------------------------------------------------------------


async def test_handler_multiple_concurrent_runs_are_independent() -> None:
    """State for run_id_A must not bleed into run_id_B."""
    session_a = uuid4()
    session_b = uuid4()
    captured: dict[UUID, Any] = {}

    async def _writer(
        session_id: Any,
        agent_step_id: Any,
        specialist_role: Any,
        provider: Any,
        model_name: Any,
        usage: LLMUsage,
    ) -> None:
        # Key by session so we can assert isolation
        if session_id is not None:
            captured[session_id] = model_name

    handler = _make_handler(_writer)
    run_a = uuid4()
    run_b = uuid4()

    from langchain_core.messages import HumanMessage

    # Start both runs
    await handler.on_chat_model_start(
        serialized={},
        messages=[[HumanMessage(content="A")]],
        run_id=run_a,
        metadata={"session_id": str(session_a)},
    )
    await handler.on_chat_model_start(
        serialized={},
        messages=[[HumanMessage(content="B")]],
        run_id=run_b,
        metadata={"session_id": str(session_b)},
    )

    # End in reverse order
    await handler.on_llm_end(
        response=_make_llm_result(_make_ai_message(model="model-b")),
        run_id=run_b,
    )
    await handler.on_llm_end(
        response=_make_llm_result(_make_ai_message(model="model-a")),
        run_id=run_a,
    )

    assert captured[session_a] == "model-a"
    assert captured[session_b] == "model-b"
