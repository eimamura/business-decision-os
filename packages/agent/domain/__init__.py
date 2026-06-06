from __future__ import annotations

from typing import Any

from packages.agent.control.control_agent import ControlAgent
from packages.agent.domain.logistics import LogisticsAgent
from packages.agent.domain.procurement import ProcurementAgent
from packages.agent.domain.production import ProductionAgent
from packages.agent.domain.replenishment import ReplenishmentAgent
from packages.agent.domain.supplier import SupplierAgent

__all__ = [
    "ControlAgent",
    "LogisticsAgent",
    "ProcurementAgent",
    "ProductionAgent",
    "ReplenishmentAgent",
    "SupplierAgent",
    "create_domain_agents",
]


def create_domain_agents(
    llm_client: Any,
    tool_registry: Any,
    sse_queue: Any = None,
) -> list[Any]:
    return [
        ControlAgent(llm_client, tool_registry, sse_queue),
        ReplenishmentAgent(llm_client, tool_registry, sse_queue),
        ProcurementAgent(llm_client, tool_registry, sse_queue),
        SupplierAgent(llm_client, tool_registry, sse_queue),
        ProductionAgent(llm_client, tool_registry, sse_queue),
        LogisticsAgent(llm_client, tool_registry, sse_queue),
    ]
