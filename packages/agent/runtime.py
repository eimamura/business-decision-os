from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from packages.agent.orchestrator import SpecialistResult, SpecialistTask
    from packages.tools.base import ToolContext

_log = logging.getLogger(__name__)

_MAX_ITERATIONS = 10

OutputBuilder = Callable[[dict[str, Any], Any], dict[str, Any]]


def _default_output_builder(name: str) -> OutputBuilder:
    def _build(tool_results: dict[str, Any], response: Any) -> dict[str, Any]:
        text = response.text if response else ""
        output: dict[str, Any] = {"text": text, "specialist": name}
        if tool_results:
            output["tool_results"] = tool_results
        return output

    return _build


def _role_aware_output_builder(role: str) -> OutputBuilder:
    def _build(tool_results: dict[str, Any], response: Any) -> dict[str, Any]:
        text = response.text if response else ""
        if role == "simulation_optimizer" and "optimize_replenishment" in tool_results:
            return {"candidates": tool_results["optimize_replenishment"].get("candidates", [])}
        if role == "data_engineer" and "sql_query" in tool_results:
            return {"data_summary": tool_results["sql_query"], "text": text}
        return {"text": text}

    return _build


class AgentRuntime:
    def __init__(
        self,
        name: str,
        role: str,
        llm_client: Any,  # Any: structural match to LLMClient Protocol
        tool_registry: Any,  # Any: structural match to ToolRegistry Protocol
        sse_queue: Any = None,  # Any: asyncio.Queue not generically typeable at runtime
        system_prompt: str | None = None,
        output_builder: OutputBuilder | None = None,
    ) -> None:
        self.name = name
        self.role = role
        self._llm_client = llm_client
        self._tool_registry = tool_registry
        self._sse_queue = sse_queue
        self._system_prompt = system_prompt or f"You are a {role} specialist."
        _ROLE_AWARE_ROLES = {"simulation_optimizer", "data_engineer"}
        self._output_builder: OutputBuilder = output_builder or (
            _role_aware_output_builder(role)
            if role in _ROLE_AWARE_ROLES
            else _default_output_builder(name)
        )

    async def _push(self, event: dict[str, Any]) -> None:
        if self._sse_queue is not None:
            from packages.agent.orchestrator.parsing import json_safe
            await self._sse_queue.put(json_safe(event))

    async def run(self, task: SpecialistTask, ctx: ToolContext) -> SpecialistResult:
        from packages.agent.llm import LLMMessage, LLMToolSpec
        from packages.agent.orchestrator import SpecialistResult

        system_prompt = self._system_prompt + "\n\nAlways respond in the same language the user writes in."
        messages: list[LLMMessage] = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=task.instruction),
        ]

        allowed_tool_names = set(task.allowed_tools or [])
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
        _total_input_tokens = 0
        _total_output_tokens = 0
        _total_cost_usd: Decimal = Decimal("0")

        for _ in range(_MAX_ITERATIONS):
            _log.info(
                "Specialist %s calling LLM (model=%s)",
                self.role,
                getattr(self._llm_client, "_model", "?"),
            )
            response = await self._llm_client.complete(
                messages=messages,
                tools=llm_tools if llm_tools else None,
                temperature=0.0,
                agent_step_id=task.task_id,
                specialist_role=self.role,
            )
            last_response = response
            _total_input_tokens += response.usage.input_tokens
            _total_output_tokens += response.usage.output_tokens
            _total_cost_usd += response.usage.total_cost_usd
            _log.info(
                "Specialist %s LLM response: finish_reason=%s tool_calls=%d model=%s",
                self.role, response.finish_reason, len(response.tool_calls), response.model,
            )

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
                    tool_call_id = call["id"]
                    tool_input = call.get("input", {})
                    tool_t0 = time.monotonic()
                    await self._push({
                        "type": "tool_started",
                        "tool_name": call["name"],
                        "tool_call_id": tool_call_id,
                        "step_id": str(ctx.agent_step_id),
                        "agent_role": self.role,
                        "input": tool_input,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                    try:
                        tool_result = await tool.handle(tool_input, ctx)
                        tool_duration_ms = int((time.monotonic() - tool_t0) * 1000)
                        tool_calls_made.append(ctx.agent_step_id)
                        tool_results[call["name"]] = tool_result.output
                        executed_query = (
                            tool_result.output.get("executed_query")
                            if isinstance(tool_result.output, dict)
                            else None
                        )
                        await self._push({
                            "type": "tool_completed",
                            "tool_name": call["name"],
                            "tool_call_id": tool_call_id,
                            "agent_role": self.role,
                            "duration_ms": tool_duration_ms,
                            "output": tool_result.output,
                            "executed_query": executed_query,
                            "status": "success",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        })
                    except Exception as exc:
                        tool_duration_ms = int((time.monotonic() - tool_t0) * 1000)
                        await self._push({
                            "type": "tool_completed",
                            "tool_name": call["name"],
                            "tool_call_id": tool_call_id,
                            "agent_role": self.role,
                            "duration_ms": tool_duration_ms,
                            "status": "error",
                            "error": str(exc),
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        })
                        raise
                    messages.append(LLMMessage(
                        role="tool",
                        content=json.dumps(tool_result.output),
                        tool_call_id=call["id"],
                    ))

        return SpecialistResult(
            task_id=task.task_id,
            output=self._output_builder(tool_results, last_response),
            tool_calls_made=tool_calls_made,
            status="completed",
            usage={
                "input_tokens": _total_input_tokens,
                "output_tokens": _total_output_tokens,
                "cost_usd": float(_total_cost_usd),
            },
        )
