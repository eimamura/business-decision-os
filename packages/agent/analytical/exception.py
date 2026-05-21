from __future__ import annotations

from typing import Any

from packages.agent.base import PromptBasedSpecialist

_SYSTEM_PROMPT = (
    "You are an exception agent. "
    "Detect anomalies and items requiring attention — missing data, outliers, sudden changes, "
    "rule violations, and abnormal patterns across operational data."
)


class ExceptionAgent(PromptBasedSpecialist):
    def __init__(
        self,
        llm_client: Any,
        tool_registry: Any,
        sse_queue: Any = None,
    ) -> None:
        super().__init__(
            name="exception",
            role="exception",
            llm_client=llm_client,
            tool_registry=tool_registry,
            sse_queue=sse_queue,
            system_prompt=_SYSTEM_PROMPT,
        )
