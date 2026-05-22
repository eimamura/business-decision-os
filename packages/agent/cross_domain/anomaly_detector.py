from __future__ import annotations

from typing import Any

from packages.agent.base import AgentBasedSpecialist

_SYSTEM_PROMPT = (
    "You are an anomaly detector. "
    "Detect anomalies and items requiring attention across demand, inventory, procurement, "
    "production, and logistics — missing data, outliers, sudden changes, rule violations, "
    "and abnormal patterns. Surface root cause candidates for detected anomalies."
)


class AnomalyDetectorAgent(AgentBasedSpecialist):
    def __init__(
        self,
        llm_client: Any,
        tool_registry: Any,
        sse_queue: Any = None,
    ) -> None:
        super().__init__(
            name="anomaly_detector",
            role="anomaly_detector",
            llm_client=llm_client,
            tool_registry=tool_registry,
            sse_queue=sse_queue,
            system_prompt=_SYSTEM_PROMPT,
        )
