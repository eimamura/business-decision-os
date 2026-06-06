from __future__ import annotations

from typing import TYPE_CHECKING, Any

from packages.agent.base import AgentBasedSpecialist
from packages.knowledge import SkillLoader

if TYPE_CHECKING:
    from packages.agent.orchestrator import SpecialistResult, SpecialistTask
    from packages.tools.base import ToolContext

_SYSTEM_PROMPT = (
    "You are a cross-domain operational judgment center for supply chain decisions.\n\n"
    "Responsibilities:\n"
    "- Assess stockout risk across demand, inventory, and supply signals\n"
    "- Prioritize exceptions and escalations spanning logistics, finance, and operations\n"
    "- Identify root causes of shipment delays through logistics and supply data\n"
    "- Analyze supply gaps relative to demand forecasts and inventory positions\n"
    "- Recommend prioritized actions that account for cost impact, "
    "lead times, and service levels\n\n"
    "Domains in scope: demand forecasting and trend analysis, inventory positioning and risk,\n"
    "supply order status and lead time, logistics execution and delay diagnosis,\n"
    "and finance impact quantification (holding costs, stockout costs, expedite costs).\n\n"
    "Always ground recommendations in tool results. Do not fabricate quantities or risk scores."
)

_SKILL_HEADER = "\n\n---\n## Analysis Procedures\n\n"
_SKILL_SEPARATOR = "\n\n---\n\n"


class ControlAgent(AgentBasedSpecialist):
    _SYSTEM_PROMPT: str = _SYSTEM_PROMPT

    def __init__(
        self,
        llm_client: Any,
        tool_registry: Any,
        sse_queue: Any = None,
    ) -> None:
        super().__init__(
            name="ControlAgent",
            role="control",
            llm_client=llm_client,
            tool_registry=tool_registry,
            sse_queue=sse_queue,
            system_prompt=self._SYSTEM_PROMPT,
        )

    async def run(
        self,
        task: "SpecialistTask",
        ctx: "ToolContext",
        agent_run_id: str = "",
    ) -> "SpecialistResult":
        intent_category: str = (
            (task.context_payload.get("intent") or {}).get("category") or ""
        )
        skills = SkillLoader().load(intent_category)
        if skills:
            skill_block = _SKILL_HEADER + _SKILL_SEPARATOR.join(skills)
            task = task.model_copy(
                update={"instruction": skill_block + "\n\n" + task.instruction}
            )
        return await super().run(task, ctx, agent_run_id=agent_run_id)
