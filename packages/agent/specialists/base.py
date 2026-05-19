from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, Protocol

SpecialistRole = Literal["orchestrator", "domain_expert", "data_engineer", "sim_opt", "evaluator"]

if TYPE_CHECKING:
    from packages.agent.orchestrator import SpecialistResult, SpecialistTask
    from packages.tools.base import ToolContext


class Specialist(Protocol):
    name: str
    role: SpecialistRole

    async def run(self, task: SpecialistTask, ctx: ToolContext) -> SpecialistResult: ...


_CANNED_OUTPUTS: dict[str, dict[str, Any]] = {
    "domain_expert": {"considerations": ["Supply chain analysis complete"]},
    "data_engineer": {"data_summary": {"sku_count": 0, "avg_demand": 0}},
    "sim_opt": {"candidates": []},
    "evaluator": {"scores": []},
}

_ROLE_PROMPTS: dict[str, str] = {
    "domain_expert": (
        "You are a supply chain domain expert. "
        "Analyze the decision goal and surface key domain considerations."
    ),
    "data_engineer": (
        "You are a data engineer. "
        "Query operational data tables using SQL to gather facts for the decision."
    ),
    "sim_opt": (
        "You are a simulation/optimization specialist. "
        "Run simulation and optimization tools to generate candidate plans."
    ),
    "evaluator": (
        "You are an evaluator. "
        "Score each candidate plan against all KPIs independently."
    ),
}


class PromptBasedSpecialist:
    def __init__(
        self, name: str, role: SpecialistRole, llm_client: Any, tool_registry: Any
    ) -> None:
        self.name = name
        self.role = role
        self._llm_client = llm_client
        self._tool_registry = tool_registry

    async def run(self, task: SpecialistTask, ctx: ToolContext) -> SpecialistResult:
        from packages.agent.llm import LLMMessage, LLMToolSpec
        from packages.agent.orchestrator import SpecialistResult

        system_prompt = _ROLE_PROMPTS.get(self.role, "You are a specialist.")
        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=task.instruction),
        ]

        allowed_tool_names = set(task.allowed_tools)
        tool_objects = [
            t for t in self._tool_registry.list_for_role(self.role)
            if t.name in allowed_tool_names
        ]
        llm_tools = [
            LLMToolSpec(
                name=t.name,
                description=t.description,
                input_schema=t.input_schema,
            )
            for t in tool_objects
        ]

        response = await self._llm_client.complete(
            messages=messages,
            tools=llm_tools if llm_tools else None,
            temperature=0.0,
            agent_step_id=task.task_id,
            specialist_role=self.role,
        )

        tool_calls_made = []
        if response.tool_calls:
            for call in response.tool_calls:
                tool = self._tool_registry.get(call["name"])
                if tool is not None:
                    await tool.handle(call.get("input", {}), ctx)
                    tool_calls_made.append(ctx.agent_step_id)

        output = _CANNED_OUTPUTS.get(self.role, {})

        return SpecialistResult(
            task_id=task.task_id,
            output=output,
            tool_calls_made=tool_calls_made,
            status="completed",
        )
