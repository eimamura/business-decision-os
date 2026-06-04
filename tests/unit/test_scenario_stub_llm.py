from __future__ import annotations

import json
import os

import pytest

from packages.agent.llm import LLMMessage, ScenarioStubClaudeClient
from packages.agent.orchestrator import AgentRoute, SessionIntent
from packages.agent.orchestrator.prompts import ASK_USER_SYSTEM, INTENT_SYSTEM, ROUTER_SYSTEM


def _system_msg(text: str) -> LLMMessage:
    return LLMMessage(role="system", content=text)


def _user_msg(text: str) -> LLMMessage:
    return LLMMessage(role="user", content=text)


@pytest.fixture
def stub() -> ScenarioStubClaudeClient:
    return ScenarioStubClaudeClient()


async def test_stub_intent_system_parses_as_session_intent(
    stub: ScenarioStubClaudeClient,
) -> None:
    response = await stub.complete([_system_msg(INTENT_SYSTEM), _user_msg("Analyze inventory")])
    data = json.loads(response.text)
    intent = SessionIntent(**data)
    assert intent.category
    assert 0.0 <= intent.confidence <= 1.0
    assert intent.rationale


async def test_stub_router_system_parses_as_agent_route(
    stub: ScenarioStubClaudeClient,
) -> None:
    response = await stub.complete([_system_msg(ROUTER_SYSTEM), _user_msg("Route this")])
    data = json.loads(response.text)
    route = AgentRoute(**data)
    assert route.mode in (
        "direct_chat",
        "single_agent",
        "sequential_agents",
        "planned_execution",
        "dag_execution",
    )
    assert route.rationale


async def test_stub_router_single_agent_has_exactly_one_agent(
    stub: ScenarioStubClaudeClient,
) -> None:
    response = await stub.complete([_system_msg(ROUTER_SYSTEM), _user_msg("Route this")])
    data = json.loads(response.text)
    route = AgentRoute(**data)
    if route.mode == "single_agent":
        assert len(route.agents) == 1, "single_agent mode requires exactly one agent"


async def test_stub_ask_user_system_needs_input_false_by_default(
    stub: ScenarioStubClaudeClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MOCK_ASK_USER", raising=False)
    response = await stub.complete([_system_msg(ASK_USER_SYSTEM), _user_msg("Analyze inventory")])
    data = json.loads(response.text)
    assert data["needs_input"] is False


async def test_stub_ask_user_system_needs_input_true_when_mock_ask_user(
    stub: ScenarioStubClaudeClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MOCK_ASK_USER", "true")
    response = await stub.complete([_system_msg(ASK_USER_SYSTEM), _user_msg("Analyze inventory")])
    data = json.loads(response.text)
    assert data["needs_input"] is True
    assert data["question"]
    assert isinstance(data["suggestions"], list)
    assert len(data["suggestions"]) > 0


async def test_stub_intent_analytical_category_with_mock_ask_user(
    stub: ScenarioStubClaudeClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MOCK_ASK_USER", "true")
    response = await stub.complete([_system_msg(INTENT_SYSTEM), _user_msg("Analyze inventory")])
    data = json.loads(response.text)
    intent = SessionIntent(**data)
    # MOCK_ASK_USER=true must return an analytical intent so the ask_user flow is exercised
    analytical_intents = {"domain_analysis", "cross_domain_analysis", "decision_support"}
    assert intent.category in analytical_intents, (
        f"Expected analytical intent but got '{intent.category}'. "
        "MOCK_ASK_USER=true must trigger an analytical category so prepare_ask_user runs."
    )
