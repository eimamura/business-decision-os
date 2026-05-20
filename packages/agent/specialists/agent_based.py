from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from packages.agent.orchestrator import SpecialistResult, SpecialistTask
    from packages.tools.base import ToolContext

_log = logging.getLogger(__name__)

_SPECIALIST_PROMPTS: dict[str, str] = {
    "forecast": (
        "You are a demand forecasting specialist. "
        "Analyze historical demand patterns, seasonality, and trends to provide "
        "accurate demand forecasts for supply chain decisions."
    ),
    "inventory": (
        "You are an inventory management specialist. "
        "Evaluate current inventory levels, safety stock requirements, reorder points, "
        "and optimal inventory policies."
    ),
    "procurement": (
        "You are a procurement specialist. "
        "Assess supplier options, lead times, order quantities, costs, and "
        "procurement strategies to optimize sourcing decisions."
    ),
    "production": (
        "You are a production planning specialist. "
        "Analyze production capacity, scheduling constraints, batch sizes, and "
        "manufacturing efficiency to optimize production decisions."
    ),
    "cost": (
        "You are a supply chain cost specialist. "
        "Evaluate total cost of ownership, working capital, carrying costs, ordering costs, "
        "and cost trade-offs across supply chain decisions."
    ),
}

_SPECIALIST_TOOLS: dict[str, list[str]] = {
    "forecast": ["forecast", "sql_query"],
    "inventory": ["sql_query"],
    "procurement": ["sql_query"],
    "production": ["sql_query"],
    "cost": ["sql_query"],
}

_MAX_ITERATIONS = 10


class AgentBasedSpecialist:
    """Specialist with independent context and tool registry — safe for parallel execution."""

    def __init__(
        self,
        name: str,
        role: str,
        llm_client: Any,
        tool_registry: Any,
        sse_queue: Any = None,
    ) -> None:
        self.name = name
        self.role = role
        self._llm_client = llm_client
        self._tool_registry = tool_registry
        self._sse_queue = sse_queue

    async def _push(self, event: dict[str, Any]) -> None:
        if self._sse_queue is not None:
            await self._sse_queue.put(event)

    async def run(self, task: SpecialistTask, ctx: ToolContext) -> SpecialistResult:
        from packages.agent.llm import LLMMessage, LLMToolSpec
        from packages.agent.orchestrator import SpecialistResult

        await self._push({
            "type": "specialist_started",
            "specialist_name": self.name.replace("_", " ").title(),
            "specialist_role": self.role,
            "task_id": str(task.task_id),
            "started_at": datetime.now(timezone.utc).isoformat(),
        })

        system_prompt = _SPECIALIST_PROMPTS.get(self.role, f"You are a {self.role} specialist.")
        system_prompt += "\n\nAlways respond in the same language the user writes in."
        # Independent context per invocation — never shared across parallel agents
        messages: list[LLMMessage] = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=task.instruction),
        ]

        allowed_tool_names = set(task.allowed_tools or _SPECIALIST_TOOLS.get(self.role, []))
        tool_objects = [
            t for t in self._tool_registry.list_for_role(self.role)
            if t.name in allowed_tool_names
        ]
        llm_tools = [
            LLMToolSpec(name=t.name, description=t.description, input_schema=t.input_schema)
            for t in tool_objects
        ]

        tool_calls_made: list[Any] = []
        tool_results: dict[str, Any] = {}
        last_response: Any = None

        for _ in range(_MAX_ITERATIONS):
            _log.info("AgentBasedSpecialist %s calling LLM", self.name)
            response = await self._llm_client.complete(
                messages=messages,
                tools=llm_tools if llm_tools else None,
                temperature=0.0,
                agent_step_id=task.task_id,
                specialist_role=self.role,
            )
            last_response = response

            if not response.tool_calls or response.finish_reason == "stop":
                break

            content_blocks: list[dict[str, Any]] = []
            if response.text:
                content_blocks.append({"type": "text", "text": response.text})
            for call in response.tool_calls:
                content_blocks.append({
                    "type": "tool_use",
                    "id": call["id"],
                    "name": call["name"],
                    "input": call.get("input", {}),
                })
            messages.append(LLMMessage(
                role="assistant", content=response.text, content_blocks=content_blocks
            ))

            for call in response.tool_calls:
                tool = self._tool_registry.get(call["name"])
                if tool is not None:
                    tool_result = await tool.handle(call.get("input", {}), ctx)
                    tool_calls_made.append(ctx.agent_step_id)
                    tool_results[call["name"]] = tool_result.output
                    messages.append(LLMMessage(
                        role="tool",
                        content=json.dumps(tool_result.output),
                        tool_call_id=call["id"],
                    ))

        text = last_response.text if last_response else ""
        output: dict[str, Any] = {"text": text, "specialist": self.name}
        if tool_results:
            output["tool_results"] = tool_results

        return SpecialistResult(
            task_id=task.task_id,
            output=output,
            tool_calls_made=tool_calls_made,
            status="completed",
        )
