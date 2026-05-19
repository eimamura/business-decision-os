from __future__ import annotations

from typing import Protocol
from uuid import UUID

from pydantic import BaseModel

from packages.agent.specialists.base import SpecialistRole


class ToolContext(BaseModel):
    session_id: UUID
    agent_step_id: UUID
    specialist_role: SpecialistRole
    actor: str
    correlation_id: UUID


class ToolResult(BaseModel):
    output: dict
    audit_payload: dict


class Tool(Protocol):
    name: str
    description: str
    input_schema: dict
    output_schema: dict
    requires_approval: bool

    async def handle(self, input: dict, ctx: ToolContext) -> ToolResult: ...


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list_for_role(self, role: SpecialistRole) -> list[Tool]:
        return list(self._tools.values())
