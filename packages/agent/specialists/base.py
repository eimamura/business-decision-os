from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Protocol

SpecialistRole = Literal["orchestrator", "domain_expert", "data_engineer", "sim_opt", "evaluator"]

if TYPE_CHECKING:
    from packages.agent.orchestrator import SpecialistResult, SpecialistTask
    from packages.tools.base import ToolContext


class Specialist(Protocol):
    name: str
    role: SpecialistRole

    async def run(self, task: SpecialistTask, ctx: ToolContext) -> SpecialistResult: ...


class PromptBasedSpecialist:
    def __init__(self, name: str, role: SpecialistRole) -> None:
        self.name = name
        self.role = role

    async def run(self, task: SpecialistTask, ctx: ToolContext) -> SpecialistResult:
        raise NotImplementedError("Phase 1")
