from __future__ import annotations

from typing import Any

from packages.agent.base import PromptBasedSpecialist

_SYSTEM_PROMPT = (
    "You are a data engineer. "
    "Query operational data tables using SQL to gather facts for the decision."
)


class DataEngineerAgent(PromptBasedSpecialist):
    def __init__(
        self,
        llm_client: Any,
        tool_registry: Any,
        sse_queue: Any = None,
    ) -> None:
        super().__init__(
            name="data_engineer",
            role="data_engineer",
            llm_client=llm_client,
            tool_registry=tool_registry,
            sse_queue=sse_queue,
            system_prompt=_SYSTEM_PROMPT,
        )
