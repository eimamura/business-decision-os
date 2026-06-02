from __future__ import annotations

from typing import Any

from packages.agent.base import AgentBasedSpecialist

_SYSTEM_PROMPT = (
    "You are a demand analysis specialist in a supply chain decision system.\n\n"
    "Responsibilities:\n"
    "- Analyze historical demand data for trends, seasonality, and anomalies\n"
    "- Evaluate forecast accuracy and diagnose sources of forecast error\n"
    "- Assess demand volatility and its impact on safety stock and service levels\n"
    "- Identify high-risk SKUs with erratic or low-predictability demand patterns\n"
    "- Use forecast and train_forecast tools to generate or refresh demand predictions\n\n"
    "Always ground your analysis in tool results. Do not fabricate demand figures."
)


class DemandAgent(AgentBasedSpecialist):
    def __init__(
        self,
        llm_client: Any,
        tool_registry: Any,
        sse_queue: Any = None,
    ) -> None:
        super().__init__(
            name="demand",
            role="demand",
            llm_client=llm_client,
            tool_registry=tool_registry,
            sse_queue=sse_queue,
            system_prompt=_SYSTEM_PROMPT,
        )
