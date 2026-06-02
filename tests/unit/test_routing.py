from __future__ import annotations

import pytest

from packages.agent.orchestrator.models import AgentRoute, SessionIntent
from packages.agent.orchestrator.routing import route_after_intent, validate_route


def _intent(category: str) -> SessionIntent:
    return SessionIntent(category=category, confidence=1.0, rationale="test")


def test_route_after_intent_chat() -> None:
    assert route_after_intent(_intent("chat")) == "direct_chat"


def test_route_after_intent_decision_support() -> None:
    assert route_after_intent(_intent("decision_support")) == "planned_execution"


def test_validate_route_direct_chat_with_agents_raises() -> None:
    route = AgentRoute(mode="direct_chat", agents=["demand"], rationale="test")
    with pytest.raises(ValueError, match="direct_chat route must not include agents"):
        validate_route(route)


def test_validate_route_single_agent_wrong_count_raises() -> None:
    route = AgentRoute(mode="single_agent", agents=["demand", "inventory"], rationale="test")
    with pytest.raises(ValueError, match="single_agent route requires exactly one agent"):
        validate_route(route)


def test_validate_route_unknown_agent_raises() -> None:
    route = AgentRoute(mode="single_agent", agents=["nonexistent_agent"], rationale="test")
    with pytest.raises(ValueError, match="unknown agent role"):
        validate_route(route)
