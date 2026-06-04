from __future__ import annotations

"""T-123: Unit tests for ClaudeClient model dispatch (T-120) and cost table (T-121).

Covers:
- specialist_role="orchestrator" selects the Haiku orchestrator model
- any other specialist_role selects the default Sonnet model
- ORCHESTRATOR_MODEL env var overrides the default Haiku model
- _compute_cost returns a lower cost for Haiku than Sonnet at identical token counts
- _compute_cost falls back to Sonnet pricing for an unknown model name
"""

from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_client(monkeypatch: pytest.MonkeyPatch | None = None) -> Any:
    """Build a ClaudeClient whose underlying Anthropic SDK is mocked.

    Uses patch.object(_build_client) so the autouse network guard is never
    triggered and no real network I/O occurs.
    """
    from packages.agent.llm import ClaudeClient

    with patch.object(ClaudeClient, "_build_client", return_value=MagicMock()):
        client = ClaudeClient(api_key="test-key-placeholder")
    return client


def _make_fake_response(model: str = "claude-sonnet-4-6") -> MagicMock:
    """Return a minimal fake Anthropic API response."""
    usage = MagicMock()
    usage.input_tokens = 10
    usage.output_tokens = 5
    usage.cache_read_input_tokens = 0
    usage.cache_creation_input_tokens = 0

    block = MagicMock()
    block.type = "text"
    block.text = "ok"

    response = MagicMock()
    response.content = [block]
    response.stop_reason = "end_turn"
    response.usage = usage
    response.id = "req-id"
    response.model = model
    return response


def _make_messages() -> list[Any]:
    from packages.agent.llm import LLMMessage

    return [LLMMessage(role="user", content="hello")]


def _make_usage(input_tokens: int = 1000, output_tokens: int = 500) -> MagicMock:
    """Return a usage object compatible with _compute_cost."""
    usage = MagicMock()
    usage.input_tokens = input_tokens
    usage.output_tokens = output_tokens
    usage.cache_read_input_tokens = 0
    usage.cache_creation_input_tokens = 0
    return usage


# ---------------------------------------------------------------------------
# T-120: model dispatch
# ---------------------------------------------------------------------------


async def test_orchestrator_role_uses_haiku_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """complete() passes the Haiku orchestrator model when specialist_role='orchestrator'."""
    monkeypatch.delenv("ORCHESTRATOR_MODEL", raising=False)
    client = _make_client()
    messages = _make_messages()

    captured: dict[str, Any] = {}

    async def _fake_create(**kwargs: Any) -> MagicMock:
        captured.update(kwargs)
        return _make_fake_response(model=kwargs["model"])

    client._client.messages.create = _fake_create

    await client.complete(messages=messages, specialist_role="orchestrator")

    assert captured["model"] == "claude-haiku-4-5-20251001"


async def test_specialist_role_uses_sonnet_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """complete() passes the default Sonnet model for a non-orchestrator specialist_role."""
    monkeypatch.delenv("ORCHESTRATOR_MODEL", raising=False)
    client = _make_client()
    messages = _make_messages()

    captured: dict[str, Any] = {}

    async def _fake_create(**kwargs: Any) -> MagicMock:
        captured.update(kwargs)
        return _make_fake_response(model=kwargs["model"])

    client._client.messages.create = _fake_create

    await client.complete(messages=messages, specialist_role="data_engineer")

    assert captured["model"] == "claude-sonnet-4-6"


async def test_none_specialist_role_uses_sonnet_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """complete() passes the default Sonnet model when specialist_role is None."""
    monkeypatch.delenv("ORCHESTRATOR_MODEL", raising=False)
    client = _make_client()
    messages = _make_messages()

    captured: dict[str, Any] = {}

    async def _fake_create(**kwargs: Any) -> MagicMock:
        captured.update(kwargs)
        return _make_fake_response(model=kwargs["model"])

    client._client.messages.create = _fake_create

    await client.complete(messages=messages, specialist_role=None)

    assert captured["model"] == "claude-sonnet-4-6"


# ---------------------------------------------------------------------------
# T-120: ORCHESTRATOR_MODEL env var override
# ---------------------------------------------------------------------------


async def test_orchestrator_model_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """ORCHESTRATOR_MODEL env var is used instead of the hard-coded default."""
    custom_model = "claude-haiku-4-5-20251001"
    monkeypatch.setenv("ORCHESTRATOR_MODEL", custom_model)

    from packages.agent.llm import ClaudeClient

    with patch.object(ClaudeClient, "_build_client", return_value=MagicMock()):
        client = ClaudeClient(api_key="test-key-placeholder")

    messages = _make_messages()
    captured: dict[str, Any] = {}

    async def _fake_create(**kwargs: Any) -> MagicMock:
        captured.update(kwargs)
        return _make_fake_response(model=kwargs["model"])

    client._client.messages.create = _fake_create

    await client.complete(messages=messages, specialist_role="orchestrator")

    assert captured["model"] == custom_model


# ---------------------------------------------------------------------------
# T-121: cost table
# ---------------------------------------------------------------------------


def test_compute_cost_haiku_cheaper_than_sonnet() -> None:
    """Haiku cost < Sonnet cost at equal token counts."""
    client = _make_client()
    usage = _make_usage(input_tokens=1000, output_tokens=500)

    haiku_cost = client._compute_cost(usage, "claude-haiku-4-5-20251001")
    sonnet_cost = client._compute_cost(usage, "claude-sonnet-4-6")

    assert isinstance(haiku_cost, Decimal)
    assert isinstance(sonnet_cost, Decimal)
    assert haiku_cost < sonnet_cost


def test_compute_cost_unknown_model_falls_back_to_sonnet_pricing() -> None:
    """An unrecognised model name produces the same cost as Sonnet (fallback)."""
    client = _make_client()
    usage = _make_usage(input_tokens=1000, output_tokens=500)

    unknown_cost = client._compute_cost(usage, "unknown-model-xyz")
    sonnet_cost = client._compute_cost(usage, "claude-sonnet-4-6")

    assert unknown_cost == sonnet_cost


def test_compute_cost_haiku_prefix_matched_by_longest_prefix() -> None:
    """A model name that starts with 'claude-haiku-4-5' gets Haiku pricing."""
    client = _make_client()
    usage = _make_usage(input_tokens=1000, output_tokens=500)

    # "claude-haiku-4-5-20251001" starts with the "claude-haiku-4-5" pricing key
    haiku_versioned_cost = client._compute_cost(usage, "claude-haiku-4-5-20251001")
    haiku_base_cost = client._compute_cost(usage, "claude-haiku-4-5")

    assert haiku_versioned_cost == haiku_base_cost


def test_compute_cost_zero_tokens_returns_zero() -> None:
    """Zero input and output tokens always produce zero cost."""
    client = _make_client()
    usage = _make_usage(input_tokens=0, output_tokens=0)

    assert client._compute_cost(usage, "claude-sonnet-4-6") == Decimal("0")
    assert client._compute_cost(usage, "claude-haiku-4-5-20251001") == Decimal("0")


# ---------------------------------------------------------------------------
# T-180: LLMUsage optional fields
# ---------------------------------------------------------------------------


def test_llm_usage_optional_fields_default_to_none() -> None:
    """LLMUsage new optional fields default to None when not supplied."""
    from packages.agent.llm import LLMUsage

    usage = LLMUsage(input_tokens=1, output_tokens=1, total_cost_usd=Decimal("0"))

    assert usage.prompt_messages_json is None
    assert usage.response_text is None
    assert usage.tool_calls_json is None


def test_llm_usage_optional_fields_accept_values() -> None:
    """LLMUsage optional fields can be set to string values."""
    from packages.agent.llm import LLMUsage

    usage = LLMUsage(
        input_tokens=1,
        output_tokens=1,
        total_cost_usd=Decimal("0"),
        prompt_messages_json='[{"role": "user", "content": "hi"}]',
        response_text="hello",
        tool_calls_json="[]",
    )

    assert usage.prompt_messages_json == '[{"role": "user", "content": "hi"}]'
    assert usage.response_text == "hello"
    assert usage.tool_calls_json == "[]"


# ---------------------------------------------------------------------------
# T-182: ClaudeClient.complete() populates LLMUsage fields
# ---------------------------------------------------------------------------


async def test_claude_client_complete_populates_prompt_messages_json() -> None:
    """ClaudeClient.complete() serializes input messages into LLMUsage.prompt_messages_json."""
    client = _make_client()
    messages = _make_messages()

    captured_usage: dict[str, Any] = {}

    async def _fake_writer(
        session_id: Any, agent_step_id: Any, specialist_role: Any,
        provider: Any, model: Any, usage: Any,
    ) -> None:
        captured_usage["usage"] = usage

    client._usage_writer = _fake_writer

    async def _fake_create(**kwargs: Any) -> MagicMock:
        return _make_fake_response()

    client._client.messages.create = _fake_create

    await client.complete(messages=messages)

    usage = captured_usage["usage"]
    import json
    parsed = json.loads(usage.prompt_messages_json)
    assert isinstance(parsed, list)
    assert parsed[0]["role"] == "user"
    assert parsed[0]["content"] == "hello"


async def test_claude_client_complete_populates_response_text() -> None:
    """ClaudeClient.complete() stores the text response in LLMUsage.response_text."""
    client = _make_client()
    messages = _make_messages()

    captured_usage: dict[str, Any] = {}

    async def _fake_writer(
        session_id: Any, agent_step_id: Any, specialist_role: Any,
        provider: Any, model: Any, usage: Any,
    ) -> None:
        captured_usage["usage"] = usage

    client._usage_writer = _fake_writer

    async def _fake_create(**kwargs: Any) -> MagicMock:
        return _make_fake_response()

    client._client.messages.create = _fake_create

    await client.complete(messages=messages)

    assert captured_usage["usage"].response_text == "ok"


async def test_claude_client_complete_populates_tool_calls_json_empty() -> None:
    """ClaudeClient.complete() stores an empty JSON array when there are no tool calls."""
    client = _make_client()
    messages = _make_messages()

    captured_usage: dict[str, Any] = {}

    async def _fake_writer(
        session_id: Any, agent_step_id: Any, specialist_role: Any,
        provider: Any, model: Any, usage: Any,
    ) -> None:
        captured_usage["usage"] = usage

    client._usage_writer = _fake_writer

    async def _fake_create(**kwargs: Any) -> MagicMock:
        return _make_fake_response()

    client._client.messages.create = _fake_create

    await client.complete(messages=messages)

    import json
    assert json.loads(captured_usage["usage"].tool_calls_json) == []


async def test_claude_client_complete_error_path_sets_fields_to_none() -> None:
    """ClaudeClient.complete() sets all 3 new fields to None in the APIError error path."""
    import anthropic

    client = _make_client()
    messages = _make_messages()

    captured_usage: dict[str, Any] = {}

    async def _fake_writer(
        session_id: Any, agent_step_id: Any, specialist_role: Any,
        provider: Any, model: Any, usage: Any,
    ) -> None:
        captured_usage["usage"] = usage

    client._usage_writer = _fake_writer

    async def _fake_create(**kwargs: Any) -> MagicMock:
        raise anthropic.APIStatusError(
            "bad request",
            response=MagicMock(status_code=400),
            body={},
        )

    client._client.messages.create = _fake_create

    with pytest.raises(anthropic.APIError):
        await client.complete(messages=messages)

    usage = captured_usage["usage"]
    assert usage.prompt_messages_json is None
    assert usage.response_text is None
    assert usage.tool_calls_json is None


async def test_claude_client_complete_truncates_long_prompt_messages() -> None:
    """prompt_messages_json is capped at 65536 characters."""
    from packages.agent.llm import LLMMessage, _PROMPT_MESSAGES_MAX_LEN

    client = _make_client()
    long_content = "x" * 100_000
    messages = [LLMMessage(role="user", content=long_content)]

    captured_usage: dict[str, Any] = {}

    async def _fake_writer(
        session_id: Any, agent_step_id: Any, specialist_role: Any,
        provider: Any, model: Any, usage: Any,
    ) -> None:
        captured_usage["usage"] = usage

    client._usage_writer = _fake_writer

    async def _fake_create(**kwargs: Any) -> MagicMock:
        return _make_fake_response()

    client._client.messages.create = _fake_create

    await client.complete(messages=messages)

    assert len(captured_usage["usage"].prompt_messages_json) <= _PROMPT_MESSAGES_MAX_LEN
