from __future__ import annotations

"""T-114: Unit tests for ClaudeClient.stream() text extraction."""

from typing import Any
from unittest.mock import MagicMock, patch


async def _collect(ait: Any) -> list[Any]:
    results = []
    async for item in ait:
        results.append(item)
    return results


def _make_client() -> Any:
    from packages.agent.llm import ClaudeClient

    with patch.object(ClaudeClient, "_build_client", return_value=MagicMock()):
        return ClaudeClient(api_key="test-key-placeholder")


def _make_messages() -> list[Any]:
    from packages.agent.llm import LLMMessage

    return [LLMMessage(role="user", content="hello")]


class _AsyncStreamCtx:
    def __init__(self, tokens: list[str]) -> None:
        self._tokens = tokens

    async def __aenter__(self) -> "_AsyncStreamCtx":
        return self

    async def __aexit__(self, *_: Any) -> None:
        pass

    @property
    def text_stream(self) -> Any:
        async def _gen() -> Any:
            for t in self._tokens:
                yield t

        return _gen()


async def test_stream_yields_text_delta_event_per_token() -> None:
    """stream() yields one LLMStreamEvent per token with correct shape and data."""
    from packages.agent.llm import LLMStreamEvent

    client = _make_client()
    tokens = ["alpha", "beta", "gamma"]
    client._client.messages.stream = MagicMock(return_value=_AsyncStreamCtx(tokens))

    events = await _collect(await client.stream(messages=_make_messages()))

    assert len(events) == len(tokens)
    assert all(e.get("event") == "text_delta" for e in events)
    assert [e.get("data") for e in events] == tokens


async def test_stream_yields_no_events_when_text_stream_is_empty() -> None:
    """stream() yields no events when the SDK text_stream is empty."""
    client = _make_client()
    client._client.messages.stream = MagicMock(return_value=_AsyncStreamCtx([]))

    events = await _collect(await client.stream(messages=_make_messages()))

    assert events == []
