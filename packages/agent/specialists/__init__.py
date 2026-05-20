from __future__ import annotations

from typing import Any

from packages.agent.specialists.agent_based import AgentBasedSpecialist
from packages.agent.specialists.base import PromptBasedSpecialist, SpecialistRole

_DOMAIN_SPECIALIST_NAMES: list[str] = [
    "forecast",
    "inventory",
    "procurement",
    "production",
    "cost",
]


def create_domain_specialists(
    llm_client: Any,
    tool_registry: Any,
    sse_queue: Any = None,
) -> list[AgentBasedSpecialist]:
    return [
        AgentBasedSpecialist(
            name=name,
            role=name,
            llm_client=llm_client,
            tool_registry=tool_registry,
            sse_queue=sse_queue,
        )
        for name in _DOMAIN_SPECIALIST_NAMES
    ]


def create_specialists(
    llm_client: Any,
    tool_registry: Any,
) -> dict[str, PromptBasedSpecialist]:
    roles: list[tuple[str, SpecialistRole]] = [
        ("domain_expert", "domain_expert"),
        ("data_engineer", "data_engineer"),
        ("sim_opt", "sim_opt"),
        ("evaluator", "evaluator"),
    ]
    return {
        role: PromptBasedSpecialist(
            name=name,
            role=role,
            llm_client=llm_client,
            tool_registry=tool_registry,
        )
        for name, role in roles
    }


__all__ = [
    "AgentBasedSpecialist",
    "create_domain_specialists",
    "create_specialists",
    "PromptBasedSpecialist",
]
