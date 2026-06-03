from __future__ import annotations

import json
import operator
import uuid as _uuid_mod
from typing import Annotated, Any
from uuid import UUID

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send
from typing_extensions import TypedDict

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
    session_id: UUID,
    query: SessionUserQuery,
    intent: SessionIntent,
    route: AgentRoute,
) -> ExecutionPlan:
    from packages.agent.llm import LLMMessage
    from packages.persistence.agent_steps_repo import make_step

    step_id = await make_step(str(session_id), "planning")
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
        agent_step_id=step_id,
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

    plan = await create_execution_plan(orchestrator, session_id, query, intent, route)
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
    session_id: UUID,
    query: SessionUserQuery,
    intent: SessionIntent,
    route: AgentRoute,
) -> list[TaskNode]:
    from packages.agent.llm import LLMMessage
    from packages.persistence.agent_steps_repo import make_step

    step_id = await make_step(str(session_id), "dag_planning")
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
        agent_step_id=step_id,
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


# ---------------------------------------------------------------------------
# LangGraph Send-based DAG execution
# ---------------------------------------------------------------------------


class _DagState(TypedDict):
    """Internal graph state for the DAG execution sub-graph."""

    # Serialisable snapshot of all TaskNode objects (node_id -> node.model_dump())
    all_nodes: dict[str, Any]
    # Accumulated list of completed node IDs (reducer: append)
    completed_ids: Annotated[list[str], operator.add]
    # Accumulated list of single-key dicts mapping node_id -> SpecialistResult.model_dump()
    # (reducer: append; merged to dict[str, SpecialistResult] after the graph finishes)
    result_entries: Annotated[list[dict[str, Any]], operator.add]


class _DagNodePayload(TypedDict):
    """Payload carried by each Send(target='run_dag_node', arg=payload)."""

    node_id: str
    node_data: dict[str, Any]  # TaskNode.model_dump()


def _fan_out_edge(
    state: _DagState,
) -> "list[Send] | str":
    """Conditional edge from 'dispatch': emit Send for every ready node or END."""
    completed = set(state.get("completed_ids") or [])
    all_nodes: dict[str, Any] = state.get("all_nodes") or {}

    ready_ids = [
        node_id
        for node_id, node_data in all_nodes.items()
        if node_id not in completed
        and all(dep in completed for dep in (node_data.get("deps") or []))
    ]

    if not ready_ids:
        remaining = [nid for nid in all_nodes if nid not in completed]
        if remaining:
            raise ValueError(f"DAG has unresolvable dependencies: {remaining}")
        return END

    return [
        Send(
            "run_dag_node",
            _DagNodePayload(node_id=node_id, node_data=all_nodes[node_id]),
        )
        for node_id in ready_ids
    ]


async def _dispatch_node(state: _DagState) -> dict[str, Any]:
    """No-op synchronisation node.  Acts as the entry point for each fan-out round."""
    return {}


async def _run_dag_node_impl(
    state: _DagNodePayload,
    config: RunnableConfig,
) -> dict[str, Any]:
    """Execute one DAG task node and accumulate its result into graph state."""
    from packages.agent.orchestrator.runtime import _run_agent

    cfg = config.get("configurable") or {}
    orchestrator: Any = cfg["orchestrator"]
    session_id: UUID = cfg["session_id"]
    query: SessionUserQuery = cfg["query"]
    intent: SessionIntent = cfg["intent"]
    completed_results: dict[str, SpecialistResult] = cfg["completed_results"]

    node_id: str = state["node_id"]
    node_data: dict[str, Any] = state["node_data"]

    node = TaskNode(**node_data)

    context_payload: dict[str, Any] = {
        "query": query.text,
        "intent": intent.model_dump(),
        "dependency_results": {
            dep: completed_results[dep].output
            for dep in node.deps
            if dep in completed_results
        },
    }

    result = await _run_agent(
        orchestrator,
        session_id,
        node.agent_role,
        node.instruction or (intent.goal_text or query.text),
        context_payload,
        node.tools,
    )

    # Keep the live dict in sync so the next round's dependency_results are available
    completed_results[node_id] = result

    return {
        "completed_ids": [node_id],
        "result_entries": [{node_id: result.model_dump()}],
    }


def _build_dag_graph() -> Any:
    """Build and compile the LangGraph StateGraph for Send-based DAG execution.

    Graph nodes
    -----------
    dispatch      — no-op synchronisation point; entry for each fan-out round
    run_dag_node  — executes one task; receives its payload via Send

    Graph edges
    -----------
    START           -> dispatch
    dispatch        -> [Send(run_dag_node, ...), ...] | END   (conditional / fan-out)
    run_dag_node    -> dispatch                               (loop back for next round)
    """
    sg: StateGraph = StateGraph(_DagState)  # type: ignore[type-arg]

    sg.add_node("dispatch", _dispatch_node)
    sg.add_node("run_dag_node", _run_dag_node_impl)

    sg.add_edge(START, "dispatch")
    sg.add_conditional_edges("dispatch", _fan_out_edge, ["run_dag_node", END])
    sg.add_edge("run_dag_node", "dispatch")

    return sg.compile(checkpointer=MemorySaver())


async def run_dag_execution(
    orchestrator: Any,
    session_id: UUID,
    query: SessionUserQuery,
    intent: SessionIntent,
    route: AgentRoute,
) -> SessionResponse:
    """Execute a task DAG using LangGraph's Send API for parallel fan-out.

    The ``completed_results`` mapping is threaded through ``configurable`` so
    that each ``run_dag_node`` invocation can read dependency outputs without
    those outputs having to be serialised into the LangGraph checkpoint.

    Signature is unchanged from the previous asyncio.gather implementation so
    that callers (``session_orchestrator.py`` bridge node) require no changes.
    """
    nodes = await create_task_nodes(orchestrator, session_id, query, intent, route)

    all_nodes_raw: dict[str, Any] = {node.id: node.model_dump() for node in nodes}

    # Live dict updated in-place by _run_dag_node_impl so dependency outputs are
    # visible to subsequent rounds without going through the checkpoint.
    completed_results: dict[str, SpecialistResult] = {}

    graph = _build_dag_graph()
    thread_id = str(_uuid_mod.uuid4())

    initial_state: _DagState = {
        "all_nodes": all_nodes_raw,
        "completed_ids": [],
        "result_entries": [],
    }

    run_config: dict[str, Any] = {
        "configurable": {
            "thread_id": thread_id,
            "orchestrator": orchestrator,
            "session_id": session_id,
            "query": query,
            "intent": intent,
            "completed_results": completed_results,
        }
    }

    final_state: dict[str, Any] = await graph.ainvoke(initial_state, config=run_config)

    # Reconstruct completed dict from the accumulated result_entries list
    completed: dict[str, SpecialistResult] = {}
    for entry in final_state.get("result_entries") or []:
        for node_id, result_raw in entry.items():
            completed[node_id] = SpecialistResult(**result_raw)

    return await _synthesize_response(orchestrator, session_id, query, intent, route, completed)
