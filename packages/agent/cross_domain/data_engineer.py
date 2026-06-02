from __future__ import annotations

from typing import Any

from packages.agent.base import AgentBasedSpecialist

_SYSTEM_PROMPT = (
    "You are a data engineer. "
    "Query operational data tables using SQL to gather facts for the decision."
)


def _data_engineer_output_builder(
    tool_results: dict[str, Any], response: Any
) -> dict[str, Any]:
    text = response.text if response else ""
    if "sql_query" in tool_results:
        return {"data_summary": tool_results["sql_query"], "text": text}
    return {"text": text}


class DataEngineerAgent(AgentBasedSpecialist):
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
            output_builder=_data_engineer_output_builder,
        )
