from __future__ import annotations

import asyncio
import json

import pytest

from packages.agent.llm import LLMMessage, ScenarioStubClaudeClient


async def _complete(system_content: str) -> str:
    client = ScenarioStubClaudeClient()
    response = await client.complete(
        messages=[LLMMessage(role="system", content=system_content)],
    )
    return response.text


def test_scenario_stub_intent_returns_valid_json() -> None:
    text = asyncio.run(_complete("You are the intent classifier. Return category."))
    parsed = json.loads(text)
    assert "category" in parsed


def test_scenario_stub_route_returns_valid_json() -> None:
    text = asyncio.run(_complete("You are the router. Return primary_role."))
    parsed = json.loads(text)
    assert "mode" in parsed


def test_scenario_stub_verify_returns_valid_json() -> None:
    text = asyncio.run(_complete("You are the verify findings checker."))
    parsed = json.loads(text)
    assert "status" in parsed


def test_scenario_stub_ask_user_returns_valid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MOCK_ASK_USER", raising=False)
    text = asyncio.run(_complete("You are the information-gathering assistant."))
    parsed = json.loads(text)
    assert "needs_input" in parsed
    assert parsed["needs_input"] is False


def test_scenario_stub_ask_user_does_not_raise(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MOCK_ASK_USER", raising=False)
    # Should not raise even without second user message
    system = "You are the information-gathering assistant inside SessionOrchestrator."
    asyncio.run(_complete(system))


def test_scenario_stub_ask_user_mock_ask_user_true_returns_needs_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MOCK_ASK_USER", "true")
    text = asyncio.run(_complete("You are the information-gathering assistant."))
    parsed = json.loads(text)
    assert parsed["needs_input"] is True
    assert isinstance(parsed["question"], str)
    assert len(parsed["question"]) > 0


def test_scenario_stub_default_returns_text() -> None:
    text = asyncio.run(_complete("You are a domain analyst."))
    assert isinstance(text, str)
    assert len(text) > 0
