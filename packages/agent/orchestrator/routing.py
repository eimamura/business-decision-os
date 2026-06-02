from __future__ import annotations

from packages.agent.orchestrator.models import AgentRoute, SessionIntent
from packages.agent.orchestrator.roles import VALID_AGENT_ROLES

_INTENT_MODE_MAP: dict[str, str] = {
    "chat": "direct_chat",
    "lookup": "single_agent",
    "domain_analysis": "single_agent",
    "cross_domain_analysis": "sequential_agents",
    "decision_support": "planned_execution",
}


def route_after_intent(intent: SessionIntent) -> str:
    return _INTENT_MODE_MAP.get(intent.category, "direct_chat")


def validate_route(route: AgentRoute) -> None:
    if route.mode == "direct_chat" and route.agents:
        raise ValueError("direct_chat route must not include agents")
    if route.mode == "single_agent" and len(route.agents) != 1:
        raise ValueError("single_agent route requires exactly one agent")
    if route.mode == "sequential_agents" and len(route.agents) < 1:
        raise ValueError("sequential_agents route requires at least one agent")
    unknown = [agent for agent in route.agents if agent not in VALID_AGENT_ROLES]
    if unknown:
        raise ValueError(f"unknown agent role(s): {', '.join(unknown)}")
