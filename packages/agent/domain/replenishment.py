from __future__ import annotations

from typing import Any

from packages.agent.base import AgentBasedSpecialist

_SYSTEM_PROMPT = (
    "You are a replenishment planning specialist in a supply chain decision system.\n\n"
    "Responsibilities:\n"
    "- Determine when, where, and how much to replenish for each SKU-location pair\n"
    "- Balance service level targets against inventory holding costs and supplier constraints\n"
    "- Use simulate_inventory to evaluate the effect of replenishment scenarios on stock levels\n"
    "- Use optimize_replenishment to generate and rank order proposals that satisfy constraints\n"
    "- Account for lead time variability, MOQ, and capacity limits in your recommendations\n\n"
    "Always ground your analysis in tool results. Do not fabricate order quantities."
)


class ReplenishmentAgent(AgentBasedSpecialist):
    def __init__(
        self,
        llm_client: Any,
        tool_registry: Any,
        sse_queue: Any = None,
    ) -> None:
        super().__init__(
            name="replenishment",
            role="replenishment",
            llm_client=llm_client,
            tool_registry=tool_registry,
            sse_queue=sse_queue,
            system_prompt=_SYSTEM_PROMPT,
        )
