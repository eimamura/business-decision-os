"""Unit tests for ScenarioStubClaudeClient (T-059) and MOCK_LLM env var (T-060)."""
from __future__ import annotations

import json

import pytest

from packages.agent.llm import (
    LLMMessage,
    LLMToolSpec,
    ScenarioStubClaudeClient,
    create_llm_client,
)


@pytest.mark.asyncio
async def test_intent_detection_returns_session_intent_json() -> None:
    client = ScenarioStubClaudeClient()
    msgs = [
        LLMMessage(role="system", content="Classify the category and intent of this message"),
        LLMMessage(role="user", content="What is my inventory level?"),
    ]
    resp = await client.complete(msgs)
    data = json.loads(resp.text)
    assert data["category"] == "lookup"
    assert "confidence" in data


@pytest.mark.asyncio
async def test_route_detection_returns_agent_route_json() -> None:
    client = ScenarioStubClaudeClient()
    msgs = [
        LLMMessage(role="system", content="Select primary_role and route for execution"),
        LLMMessage(role="user", content="analyze demand"),
    ]
    resp = await client.complete(msgs)
    data = json.loads(resp.text)
    assert data["mode"] == "single_agent"
    assert "primary_role" in data


@pytest.mark.asyncio
async def test_verify_detection_returns_verification_json() -> None:
    client = ScenarioStubClaudeClient()
    msgs = [
        LLMMessage(role="system", content="verify the findings and conclusions"),
        LLMMessage(role="user", content="check"),
    ]
    resp = await client.complete(msgs)
    data = json.loads(resp.text)
    assert data["status"] == "pass"


@pytest.mark.asyncio
async def test_default_returns_plain_text() -> None:
    client = ScenarioStubClaudeClient()
    msgs = [
        LLMMessage(role="system", content="You are a helpful assistant"),
        LLMMessage(role="user", content="hello"),
    ]
    resp = await client.complete(msgs)
    assert "Mock mode" in resp.text
    assert resp.finish_reason == "stop"


@pytest.mark.asyncio
async def test_stream_yields_text_delta() -> None:
    client = ScenarioStubClaudeClient()
    msgs = [LLMMessage(role="user", content="hello")]
    gen = await client.stream(msgs)
    events = [e async for e in gen]
    assert len(events) == 1
    assert events[0]["event"] == "text_delta"
    assert "Mock mode" in events[0]["data"]


def test_create_llm_client_mock_llm_true_returns_scenario_stub(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MOCK_LLM", "true")
    client = create_llm_client()
    assert isinstance(client, ScenarioStubClaudeClient)


def test_create_llm_client_mock_llm_false_requires_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MOCK_LLM", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        create_llm_client()
