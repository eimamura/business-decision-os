from __future__ import annotations

"""T-114: Unit tests for ClaudeClient.stream() text extraction.

Verifies that ClaudeClient.stream() yields LLMStreamEvent objects with
event="text_delta" and the actual text tokens from the Anthropic SDK's
text_stream async iterable.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch


async def _collect(ait: Any) -> list[Any]:
    """Drain an async iterator into a list."""
    results = []
    async for item in ait:
        results.append(item)
    return results


def _make_client() -> Any:
    """Build a ClaudeClient with a dummy API key (no real network calls)."""
    from packages.agent.llm import ClaudeClient

    with patch.object(ClaudeClient, "_build_client", return_value=MagicMock()):
        client = ClaudeClient(api_key="test-key-placeholder")
    return client


def _make_messages() -> list[Any]:
    from packages.agent.llm import LLMMessage

    return [LLMMessage(role="user", content="hello")]


def _make_async_iter(tokens: list[str]) -> Any:
    """Return an async iterator that yields the given tokens."""

    async def _gen() -> Any:
        for t in tokens:
            yield t

    return _gen()


class _AsyncStreamCtx:
    """Async context manager that exposes text_stream as an async iterator."""

    def __init__(self, tokens: list[str]) -> None:
        self._tokens = tokens

    async def __aenter__(self) -> "_AsyncStreamCtx":
        return self

    async def __aexit__(self, *_: Any) -> None:
        pass

    @property
    def text_stream(self) -> Any:
        return _make_async_iter(self._tokens)


# ---------------------------------------------------------------------------
# T-114 scenario 1: text_stream yields ["Hello", " world"]
# ---------------------------------------------------------------------------


async def test_stream_yields_text_delta_events_for_each_token() -> None:
    """stream() yields one LLMStreamEvent(event='text_delta') per token."""
    from packages.agent.llm import LLMStreamEvent

    client = _make_client()
    messages = _make_messages()

    ctx = _AsyncStreamCtx(["Hello", " world"])
    client._client.messages.stream = MagicMock(return_value=ctx)

    events = await _collect(await client.stream(messages=messages))

    assert len(events) == 2


async def test_stream_first_token_is_correct_text_delta() -> None:
    """First emitted event has event='text_delta' and data='Hello'."""
    from packages.agent.llm import LLMStreamEvent

    client = _make_client()
    messages = _make_messages()

    ctx = _AsyncStreamCtx(["Hello", " world"])
    client._client.messages.stream = MagicMock(return_value=ctx)

    events = await _collect(await client.stream(messages=messages))

    assert events[0] == LLMStreamEvent(event="text_delta", data="Hello")


async def test_stream_second_token_is_correct_text_delta() -> None:
    """Second emitted event has event='text_delta' and data=' world'."""
    from packages.agent.llm import LLMStreamEvent

    client = _make_client()
    messages = _make_messages()

    ctx = _AsyncStreamCtx(["Hello", " world"])
    client._client.messages.stream = MagicMock(return_value=ctx)

    events = await _collect(await client.stream(messages=messages))

    assert events[1] == LLMStreamEvent(event="text_delta", data=" world")


# ---------------------------------------------------------------------------
# T-114 scenario 2: text_stream yields []
# ---------------------------------------------------------------------------


async def test_stream_yields_no_events_when_text_stream_is_empty() -> None:
    """stream() yields no events when text_stream produces no tokens."""
    client = _make_client()
    messages = _make_messages()

    ctx = _AsyncStreamCtx([])
    client._client.messages.stream = MagicMock(return_value=ctx)

    events = await _collect(await client.stream(messages=messages))

    assert events == []


# ---------------------------------------------------------------------------
# Additional: event shape assertions
# ---------------------------------------------------------------------------


async def test_stream_all_events_have_event_field_text_delta() -> None:
    """Every yielded event must have event='text_delta'."""
    client = _make_client()
    messages = _make_messages()

    tokens = ["tok1", "tok2", "tok3"]
    ctx = _AsyncStreamCtx(tokens)
    client._client.messages.stream = MagicMock(return_value=ctx)

    events = await _collect(await client.stream(messages=messages))

    for evt in events:
        assert evt.get("event") == "text_delta"


async def test_stream_data_values_match_tokens_in_order() -> None:
    """The data field of each event matches the corresponding token in order."""
    client = _make_client()
    messages = _make_messages()

    tokens = ["alpha", "beta", "gamma"]
    ctx = _AsyncStreamCtx(tokens)
    client._client.messages.stream = MagicMock(return_value=ctx)

    events = await _collect(await client.stream(messages=messages))

    data_values = [evt.get("data") for evt in events]
    assert data_values == tokens
