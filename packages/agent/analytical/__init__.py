from __future__ import annotations

from typing import Any

from packages.agent.analytical.exception import ExceptionAgent
from packages.agent.analytical.ranking import RankingAgent
from packages.agent.analytical.root_cause import RootCauseAgent
from packages.agent.analytical.scenario import ScenarioAgent

__all__ = [
    "ExceptionAgent",
    "RankingAgent",
    "RootCauseAgent",
    "ScenarioAgent",
    "create_analytical_agents",
]


def create_analytical_agents(
    llm_client: Any,
    tool_registry: Any,
    sse_queue: Any = None,
) -> list[Any]:
    return [
        ExceptionAgent(llm_client, tool_registry, sse_queue),
        ScenarioAgent(llm_client, tool_registry, sse_queue),
        RankingAgent(llm_client, tool_registry, sse_queue),
        RootCauseAgent(llm_client, tool_registry, sse_queue),
    ]
