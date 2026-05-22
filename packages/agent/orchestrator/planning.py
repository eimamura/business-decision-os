from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from packages.agent.orchestrator.decision import _synthesize_response
from packages.agent.orchestrator.models import (
    AgentRoute,
    ExecutionPlan,
    SessionIntent,
    SessionResponse,
    SessionUserQuery,
    SpecialistResult,
    TaskNode,
)
from packages.agent.orchestrator.parsing import _iso_now, _json_array, _json_obj
from packages.agent.orchestrator.prompts import DAG_SYSTEM, PLAN_SYSTEM
from packages.agent.orchestrator.roles import VALID_AGENT_ROLES


def _validate_agent_role(agent_role: str, *, source: str) -> None:
    if agent_role not in VALID_AGENT_ROLES:
        raise ValueError(f"unknown agent role in {source}: {agent_role}")


async def _run_agents_in_order(
    orchestrator: Any,
    session_id: UUID,
    query: SessionUserQuery,
    agent_roles: list[str],
    intent: SessionIntent,
) -> dict[str, SpecialistResult]:
    from packages.agent.orchestrator.runtime import _default_tools, _run_agent

    results: dict[str, SpecialistResult] = {}
    for agent_role in agent_roles:
        context_payload = {
            "query": query.text,
            "conversation_context": query.conversation_context,
            "intent": intent.model_dump(),
            "previous_results": {role: result.output for role, result in results.items()},
        }
        result = await _run_agent(
            orchestrator=orchestrator,
            session_id=session_id,
            agent_role=agent_role,
            instruction=intent.goal_text or query.text,
            context_payload=context_payload,
            allowed_tools=_default_tools(agent_role),
        )
        results[agent_role] = result
    return results


async def create_execution_plan(
    orchestrator: Any,
    query: SessionUserQuery,
    intent: SessionIntent,
    route: AgentRoute,
) -> ExecutionPlan:
    from packages.agent.llm import LLMMessage

    response = await orchestrator._llm_client.complete(
        messages=[
            LLMMessage(role="system", content=PLAN_SYSTEM),
            LLMMessage(
                role="user",
                content=json.dumps(
                    {
                        "query": orchestrator._query_text(query),
                        "intent": intent.model_dump(),
                        "route": route.model_dump(),
                    }
                ),
            ),
        ],
        tools=None,
        temperature=0.0,
        max_tokens=1024,
        prompt_cache=False,
        specialist_role="orchestrator",
    )
    plan = ExecutionPlan(**_json_obj(response.text))
    for step in plan.steps:
        _validate_agent_role(step.agent_role, source="plan")
    await orchestrator._push({
        "type": "plan_created",
        "mode": "planned_execution",
        "steps": [s.model_dump() for s in plan.steps],
        "timestamp": _iso_now(),
    })
    return plan


async def run_planned_execution(
    orchestrator: Any,
    session_id: UUID,
    query: SessionUserQuery,
    intent: SessionIntent,
    route: AgentRoute,
) -> SessionResponse:
    from packages.agent.orchestrator.runtime import _run_agent

    plan = await create_execution_plan(orchestrator, query, intent, route)
    results: dict[str, SpecialistResult] = {}
    for step in plan.steps:
        context_payload = {
            "query": query.text,
            "intent": intent.model_dump(),
            "previous_results": {k: v.output for k, v in results.items()},
        }
        results[step.id] = await _run_agent(
            orchestrator,
            session_id,
            step.agent_role,
            step.instruction,
            context_payload,
            step.tools,
        )
    return await _synthesize_response(orchestrator, session_id, query, intent, route, results)


async def create_task_nodes(
    orchestrator: Any,
    query: SessionUserQuery,
    intent: SessionIntent,
    route: AgentRoute,
) -> list[TaskNode]:
    from packages.agent.llm import LLMMessage

    response = await orchestrator._llm_client.complete(
        messages=[
            LLMMessage(role="system", content=DAG_SYSTEM),
            LLMMessage(
                role="user",
                content=json.dumps(
                    {
                        "query": orchestrator._query_text(query),
                        "intent": intent.model_dump(),
                        "route": route.model_dump(),
                    }
                ),
            ),
        ],
        tools=None,
        temperature=0.0,
        max_tokens=1024,
        prompt_cache=False,
        specialist_role="orchestrator",
    )
    nodes = [TaskNode(**item) for item in _json_array(response.text)]
    for node in nodes:
        _validate_agent_role(node.agent_role, source="DAG")
    await orchestrator._push({
        "type": "plan_created",
        "mode": "dag_execution",
        "nodes": [n.model_dump() for n in nodes],
        "timestamp": _iso_now(),
    })
    return nodes


async def run_dag_execution(
    orchestrator: Any,
    session_id: UUID,
    query: SessionUserQuery,
    intent: SessionIntent,
    route: AgentRoute,
) -> SessionResponse:
    from packages.agent.orchestrator.runtime import _run_agent

    nodes = await create_task_nodes(orchestrator, query, intent, route)
    remaining = {node.id: node for node in nodes}
    completed: dict[str, SpecialistResult] = {}
    while remaining:
        ready = [
            node for node in remaining.values()
            if all(dep in completed for dep in node.deps)
        ]
        if not ready:
            raise ValueError(f"DAG has unresolvable dependencies: {list(remaining)}")
        for node in ready:
            context_payload = {
                "query": query.text,
                "intent": intent.model_dump(),
                "dependency_results": {dep: completed[dep].output for dep in node.deps},
            }
            completed[node.id] = await _run_agent(
                orchestrator,
                session_id,
                node.agent_role,
                node.instruction or (intent.goal_text or query.text),
                context_payload,
                node.tools,
            )
            del remaining[node.id]
    return await _synthesize_response(orchestrator, session_id, query, intent, route, completed)
