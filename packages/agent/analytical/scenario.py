from __future__ import annotations

from typing import Any

from packages.agent.base import PromptBasedSpecialist

_SYSTEM_PROMPT = (
    "You are a scenario agent. "
    "Perform what-if analysis — compare impacts of condition changes and evaluate "
    "multiple scenarios to support decision-making."
)


class ScenarioAgent(PromptBasedSpecialist):
    def __init__(
        self,
        llm_client: Any,
        tool_registry: Any,
        sse_queue: Any = None,
    ) -> None:
        super().__init__(
            name="scenario",
            role="scenario",
            llm_client=llm_client,
            tool_registry=tool_registry,
            sse_queue=sse_queue,
            system_prompt=_SYSTEM_PROMPT,
        )
