from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, Protocol

from packages.agent.runtime import AgentRuntime, OutputBuilder

if TYPE_CHECKING:
    from packages.agent.orchestrator import SpecialistResult, SpecialistTask
    from packages.tools.base import ToolContext

SpecialistRole = Literal[
    "orchestrator",
    "inventory",
    "procurement",
    "production",
    "data_engineer",
    "simulation_optimizer",
    "evaluator",
    "anomaly_detector",
    "demand",
    "replenishment",
    "supplier",
    "logistics",
]


class Specialist(Protocol):
    name: str
    role: SpecialistRole

    async def run(
        self,
        task: SpecialistTask,
        ctx: ToolContext,
        agent_run_id: str = "",
    ) -> SpecialistResult: ...


class AgentBasedSpecialist:
    def __init__(
        self,
        name: str,
        role: str,
        llm_client: Any,
        tool_registry: Any,
        sse_queue: Any = None,
        system_prompt: str | None = None,
        output_builder: OutputBuilder | None = None,
    ) -> None:
        self.name = name
        self.role = role
        self._runtime = AgentRuntime(
            name=name,
            role=role,
            llm_client=llm_client,
            tool_registry=tool_registry,
            sse_queue=sse_queue,
            system_prompt=system_prompt,
            output_builder=output_builder,
        )

    async def run(
        self,
        task: SpecialistTask,
        ctx: ToolContext,
        agent_run_id: str = "",
    ) -> SpecialistResult:
        return await self._runtime.run(task, ctx, agent_run_id=agent_run_id)
