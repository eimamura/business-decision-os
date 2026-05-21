from __future__ import annotations

from typing import Any

from packages.agent.base import PromptBasedSpecialist

_SYSTEM_PROMPT = (
    "You are a simulation and optimization specialist. "
    "Run inventory simulation and replenishment optimisation tools to generate candidate plans. "
    "Compare scenarios across demand, inventory, procurement, production, and logistics."
)


class SimulationOptimizerAgent(PromptBasedSpecialist):
    def __init__(
        self,
        llm_client: Any,
        tool_registry: Any,
        sse_queue: Any = None,
    ) -> None:
        super().__init__(
            name="simulation_optimizer",
            role="simulation_optimizer",
            llm_client=llm_client,
            tool_registry=tool_registry,
            sse_queue=sse_queue,
            system_prompt=_SYSTEM_PROMPT,
        )
