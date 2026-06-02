from __future__ import annotations

from typing import Any

from packages.agent.base import AgentBasedSpecialist

_SYSTEM_PROMPT = (
    "You are a simulation and optimization specialist. "
    "Run inventory simulation and replenishment optimisation tools to generate candidate plans. "
    "Compare scenarios across demand, inventory, procurement, production, and logistics."
)


def _simulation_optimizer_output_builder(
    tool_results: dict[str, Any], response: Any
) -> dict[str, Any]:
    if "optimize_replenishment" in tool_results:
        return {"candidates": tool_results["optimize_replenishment"].get("candidates", [])}
    return {"text": response.text if response else ""}


class SimulationOptimizerAgent(AgentBasedSpecialist):
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
            output_builder=_simulation_optimizer_output_builder,
        )
