"""Unit tests for OllamaClient and related create_llm_client behaviour (T-151)."""
from __future__ import annotations

import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import httpx


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_client(response: MagicMock) -> AsyncMock:
    """Return a mock async context-manager client whose .post returns *response*."""
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=response)
    return mock_client


def _make_response(status_code: int, json_body: dict) -> MagicMock:  # type: ignore[type-arg]
    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = json_body
    return mock_response


def _minimal_messages() -> list:  # type: ignore[type-arg]
    from packages.agent.llm import LLMMessage
    return [LLMMessage(role="user", content="hi")]


# ---------------------------------------------------------------------------
# T-151: OllamaClient tests
# ---------------------------------------------------------------------------


def test_ollama_client_init_raises_on_empty_base_url() -> None:
    from packages.agent.llm import OllamaClient

    with pytest.raises(RuntimeError):
        OllamaClient(base_url="")


async def test_ollama_client_complete_returns_llm_response() -> None:
    from packages.agent.llm import OllamaClient

    json_body = {
        "id": "resp-1",
        "choices": [
            {
                "message": {"content": "hello", "tool_calls": None},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }
    mock_response = _make_response(200, json_body)
    mock_client = _make_mock_client(mock_response)

    client = OllamaClient()
    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await client.complete(_minimal_messages())

    assert result.text == "hello"
    assert result.finish_reason == "stop"
    assert result.usage.input_tokens == 10
    assert result.usage.total_cost_usd == Decimal("0")


async def test_ollama_client_complete_maps_tool_calls() -> None:
    from packages.agent.llm import OllamaClient

    json_body = {
        "id": "r",
        "choices": [
            {
                "message": {
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "tc-1",
                            "function": {"name": "my_tool", "arguments": {"key": "val"}},
                        }
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ],
        "usage": {},
    }
    mock_response = _make_response(200, json_body)
    mock_client = _make_mock_client(mock_response)

    client = OllamaClient()
    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await client.complete(_minimal_messages())

    assert result.tool_calls == [{"id": "tc-1", "name": "my_tool", "input": {"key": "val"}}]
    assert result.finish_reason == "tool_use"


async def test_ollama_client_complete_raises_on_http_error() -> None:
    from packages.agent.llm import OllamaClient

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(side_effect=httpx.HTTPError("connection refused"))

    client = OllamaClient()
    with patch("httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(RuntimeError):
            await client.complete(_minimal_messages())


async def test_ollama_client_embed_returns_zero_vectors() -> None:
    from packages.agent.llm import OllamaClient

    client = OllamaClient()
    result = await client.embed(["a", "b"])

    assert result == [[0.0] * 1536, [0.0] * 1536]


def test_create_llm_client_returns_ollama_when_provider_env_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.delenv("MOCK_LLM", raising=False)
    from packages.agent.llm import OllamaClient, create_llm_client

    client = create_llm_client()

    assert isinstance(client, OllamaClient)
    assert client._model == "qwen2.5-coder:7b"


def test_create_llm_client_ollama_respects_env_vars(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://myhost:11434")
    monkeypatch.setenv("OLLAMA_MODEL", "mistral:7b")
    monkeypatch.delenv("MOCK_LLM", raising=False)
    from packages.agent.llm import create_llm_client

    client = create_llm_client()

    assert client._base_url == "http://myhost:11434"
    assert client._model == "mistral:7b"


# ---------------------------------------------------------------------------
# T-183: OllamaClient.complete() populates LLMUsage fields
# ---------------------------------------------------------------------------


async def test_ollama_client_complete_populates_prompt_messages_json() -> None:
    """OllamaClient.complete() serializes input messages into LLMUsage.prompt_messages_json."""
    import json
    from packages.agent.llm import OllamaClient

    json_body = {
        "id": "resp-1",
        "choices": [
            {
                "message": {"content": "ollama says hi", "tool_calls": None},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 8, "completion_tokens": 3},
    }
    mock_response = _make_response(200, json_body)
    mock_client = _make_mock_client(mock_response)

    captured_usage: dict = {}

    async def _fake_writer(
        session_id, agent_step_id, specialist_role, provider, model, usage
    ) -> None:
        captured_usage["usage"] = usage

    client = OllamaClient(usage_writer=_fake_writer)
    with patch("httpx.AsyncClient", return_value=mock_client):
        await client.complete(_minimal_messages())

    usage = captured_usage["usage"]
    parsed = json.loads(usage.prompt_messages_json)
    assert isinstance(parsed, list)
    assert parsed[0]["role"] == "user"


async def test_ollama_client_complete_populates_response_text() -> None:
    """OllamaClient.complete() stores the text response in LLMUsage.response_text."""
    from packages.agent.llm import OllamaClient

    json_body = {
        "id": "resp-2",
        "choices": [
            {
                "message": {"content": "the answer", "tool_calls": None},
                "finish_reason": "stop",
            }
        ],
        "usage": {},
    }
    mock_response = _make_response(200, json_body)
    mock_client = _make_mock_client(mock_response)

    captured_usage: dict = {}

    async def _fake_writer(
        session_id, agent_step_id, specialist_role, provider, model, usage
    ) -> None:
        captured_usage["usage"] = usage

    client = OllamaClient(usage_writer=_fake_writer)
    with patch("httpx.AsyncClient", return_value=mock_client):
        await client.complete(_minimal_messages())

    assert captured_usage["usage"].response_text == "the answer"


async def test_ollama_client_complete_truncates_long_prompt_messages() -> None:
    """OllamaClient.complete() caps prompt_messages_json at 65536 chars."""
    from packages.agent.llm import LLMMessage, OllamaClient, _PROMPT_MESSAGES_MAX_LEN

    long_content = "y" * 100_000
    messages = [LLMMessage(role="user", content=long_content)]

    json_body = {
        "id": "resp-3",
        "choices": [
            {
                "message": {"content": "ok", "tool_calls": None},
                "finish_reason": "stop",
            }
        ],
        "usage": {},
    }
    mock_response = _make_response(200, json_body)
    mock_client = _make_mock_client(mock_response)

    captured_usage: dict = {}

    async def _fake_writer(
        session_id, agent_step_id, specialist_role, provider, model, usage
    ) -> None:
        captured_usage["usage"] = usage

    client = OllamaClient(usage_writer=_fake_writer)
    with patch("httpx.AsyncClient", return_value=mock_client):
        await client.complete(messages)

    assert len(captured_usage["usage"].prompt_messages_json) <= _PROMPT_MESSAGES_MAX_LEN


async def test_ollama_client_complete_populates_tool_calls_json() -> None:
    """OllamaClient.complete() serializes tool calls into LLMUsage.tool_calls_json."""
    import json
    from packages.agent.llm import OllamaClient

    json_body = {
        "id": "resp-tc",
        "choices": [
            {
                "message": {
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "tc-1",
                            "function": {"name": "my_tool", "arguments": {"key": "val"}},
                        }
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ],
        "usage": {"prompt_tokens": 5, "completion_tokens": 2},
    }
    mock_response = _make_response(200, json_body)
    mock_client = _make_mock_client(mock_response)

    captured_usage: dict = {}

    async def _fake_writer(
        session_id, agent_step_id, specialist_role, provider, model, usage
    ) -> None:
        captured_usage["usage"] = usage

    client = OllamaClient(usage_writer=_fake_writer)
    with patch("httpx.AsyncClient", return_value=mock_client):
        await client.complete(_minimal_messages())

    usage = captured_usage["usage"]
    parsed = json.loads(usage.tool_calls_json)
    assert isinstance(parsed, list)
    assert len(parsed) == 1
    assert parsed[0]["name"] == "my_tool"
    assert parsed[0]["input"] == {"key": "val"}


async def test_ollama_client_error_path_does_not_call_usage_writer() -> None:
    """OllamaClient raises RuntimeError on HTTP error without calling usage_writer."""
    from packages.agent.llm import OllamaClient

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(side_effect=httpx.HTTPError("connection refused"))

    writer_calls: list = []

    async def _fake_writer(
        session_id, agent_step_id, specialist_role, provider, model, usage
    ) -> None:
        writer_calls.append(usage)

    client = OllamaClient(usage_writer=_fake_writer)
    with patch("httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(RuntimeError):
            await client.complete(_minimal_messages())

    assert writer_calls == [], "usage_writer must not be called on HTTP error"


async def test_ollama_client_complete_truncates_long_response_text() -> None:
    """OllamaClient.complete() caps response_text at _RESPONSE_TEXT_MAX_LEN chars."""
    from packages.agent.llm import LLMMessage, OllamaClient, _RESPONSE_TEXT_MAX_LEN

    long_response = "r" * 100_000

    json_body = {
        "id": "resp-rt",
        "choices": [
            {
                "message": {"content": long_response, "tool_calls": None},
                "finish_reason": "stop",
            }
        ],
        "usage": {},
    }
    mock_response = _make_response(200, json_body)
    mock_client = _make_mock_client(mock_response)

    captured_usage: dict = {}

    async def _fake_writer(
        session_id, agent_step_id, specialist_role, provider, model, usage
    ) -> None:
        captured_usage["usage"] = usage

    client = OllamaClient(usage_writer=_fake_writer)
    with patch("httpx.AsyncClient", return_value=mock_client):
        await client.complete([LLMMessage(role="user", content="hi")])

    assert len(captured_usage["usage"].response_text) <= _RESPONSE_TEXT_MAX_LEN


async def test_ollama_client_complete_truncates_long_tool_calls_json() -> None:
    """OllamaClient.complete() caps tool_calls_json at _TOOL_CALLS_MAX_LEN chars."""
    import json
    from packages.agent.llm import LLMMessage, OllamaClient, _TOOL_CALLS_MAX_LEN

    # Build a tool call with a very large argument value
    many_tool_calls = [
        {
            "id": f"tc-{i}",
            "function": {"name": "big_tool", "arguments": {"data": "z" * 1_000}},
        }
        for i in range(50)
    ]

    json_body = {
        "id": "resp-tclj",
        "choices": [
            {
                "message": {
                    "content": "",
                    "tool_calls": many_tool_calls,
                },
                "finish_reason": "tool_calls",
            }
        ],
        "usage": {},
    }
    mock_response = _make_response(200, json_body)
    mock_client = _make_mock_client(mock_response)

    captured_usage: dict = {}

    async def _fake_writer(
        session_id, agent_step_id, specialist_role, provider, model, usage
    ) -> None:
        captured_usage["usage"] = usage

    client = OllamaClient(usage_writer=_fake_writer)
    with patch("httpx.AsyncClient", return_value=mock_client):
        await client.complete([LLMMessage(role="user", content="hi")])

    assert len(captured_usage["usage"].tool_calls_json) <= _TOOL_CALLS_MAX_LEN
