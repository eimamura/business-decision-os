from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from pydantic import BaseModel

from packages.agent.base import SpecialistRole

_ROLE_TOOL_ALLOWLIST: dict[str, list[str]] = {
    "orchestrator": [],
    "data_engineer": ["sql_query", "nl_query", "data_catalog_search", "table_schema_reader", "data_quality_checker"],
    "simulation_optimizer": ["simulate_inventory", "optimize_replenishment"],
    "evaluator": ["evaluate_candidates", "write_audit_log"],
    "anomaly_detector": ["sql_query", "nl_query", "data_catalog_search", "table_schema_reader", "data_quality_checker"],
    "demand": ["sql_query", "nl_query", "forecast", "train_forecast"],
    "inventory": ["sql_query", "nl_query"],
    "replenishment": ["sql_query", "nl_query"],
    "procurement": ["sql_query", "nl_query"],
    "supplier": ["sql_query", "nl_query"],
    "production": ["sql_query", "nl_query"],
    "logistics": ["sql_query", "nl_query"],
}


class ToolContext(BaseModel):
    session_id: UUID
    agent_step_id: UUID
    specialist_role: SpecialistRole
    actor: str
    correlation_id: UUID


class ToolResult(BaseModel):
    output: dict[str, Any]
    audit_payload: dict[str, Any]


class Tool(Protocol):
    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    requires_approval: bool

    async def handle(self, input: dict[str, Any], ctx: ToolContext) -> ToolResult: ...


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list_for_role(self, role: SpecialistRole) -> list[Tool]:
        allowed = _ROLE_TOOL_ALLOWLIST.get(role)
        if allowed is None:
            return list(self._tools.values())
        if not allowed:
            return []
        return [t for name, t in self._tools.items() if name in allowed]
