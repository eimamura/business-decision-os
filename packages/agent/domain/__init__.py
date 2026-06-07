from __future__ import annotations

from typing import Any

from packages.agent.control.control_agent import ControlAgent

__all__ = [
    "ControlAgent",
    "create_domain_agents",
]


def create_domain_agents(
    llm_client: Any,
    tool_registry: Any,
    sse_queue: Any = None,
    model_registry: Any = None,
) -> list[Any]:
    return [
        ControlAgent(llm_client, tool_registry, sse_queue, model_registry=model_registry),
    ]
