from __future__ import annotations

from typing import Any

from packages.agent.base import AgentBasedSpecialist

_SYSTEM_PROMPT = (
    "You are an inventory analysis specialist in a supply chain decision system.\n\n"
    "Responsibilities:\n"
    "- Analyze current inventory levels across warehouses and SKUs\n"
    "- Identify stockout risk, days-of-supply, and safety stock adequacy\n"
    "- Detect excess inventory and working capital tied up in slow-moving stock\n"
    "- Use simulate_inventory to model how proposed orders affect future inventory levels\n"
    "- Quantify inventory health using fill rate, stockout frequency, and turnover metrics\n\n"
    "Always ground your analysis in tool results. Do not fabricate inventory figures."
)


class InventoryAgent(AgentBasedSpecialist):
    def __init__(
        self,
        llm_client: Any,
        tool_registry: Any,
        sse_queue: Any = None,
    ) -> None:
        super().__init__(
            name="inventory",
            role="inventory",
            llm_client=llm_client,
            tool_registry=tool_registry,
            sse_queue=sse_queue,
            system_prompt=_SYSTEM_PROMPT,
        )
