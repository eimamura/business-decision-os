"""Unit tests for ScenarioStubClaudeClient (T-059)."""
from __future__ import annotations

import json

from packages.agent.llm import (
    LLMMessage,
    LLMToolSpec,
    ScenarioStubClaudeClient,
)


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


async def test_route_detection_returns_agent_route_json() -> None:
    client = ScenarioStubClaudeClient()
    msgs = [
        LLMMessage(role="system", content="Select primary_role and route for execution"),
        LLMMessage(role="user", content="analyze demand"),
    ]
    resp = await client.complete(msgs)
    data = json.loads(resp.text)
    assert data["mode"] == "single_agent"
    # Bug 3 fix: stub now returns "agents" list (matches AgentRoute model), not "primary_role"
    assert "agents" in data
    assert len(data["agents"]) == 1


async def test_verify_detection_returns_verification_json() -> None:
    client = ScenarioStubClaudeClient()
    msgs = [
        LLMMessage(role="system", content="verify the findings and conclusions"),
        LLMMessage(role="user", content="check"),
    ]
    resp = await client.complete(msgs)
    data = json.loads(resp.text)
    assert data["status"] == "pass"


async def test_default_returns_plain_text() -> None:
    client = ScenarioStubClaudeClient()
    msgs = [
        LLMMessage(role="system", content="You are a helpful assistant"),
        LLMMessage(role="user", content="hello"),
    ]
    resp = await client.complete(msgs)
    assert "Mock mode" in resp.text
    assert resp.finish_reason == "stop"


async def test_stream_yields_text_delta() -> None:
    client = ScenarioStubClaudeClient()
    msgs = [LLMMessage(role="user", content="hello")]
    gen = await client.stream(msgs)
    events = [e async for e in gen]
    assert len(events) == 1
    assert events[0]["event"] == "text_delta"
    assert "Mock mode" in events[0]["data"]


