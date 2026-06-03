from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

from packages.agent.orchestrator.models import (
    AgentRoute,
    SessionIntent,
    SessionResponse,
    SessionUserQuery,
    SpecialistResult,
    TaskNode,
)


def _make_result(node_id: str) -> SpecialistResult:
    return SpecialistResult(
        task_id=uuid4(),
        output={"node": node_id},
        tool_calls_made=[],
        status="completed",
    )


def _make_intent() -> SessionIntent:
    return SessionIntent(category="test", confidence=1.0, rationale="test")


def _make_route() -> AgentRoute:
    return AgentRoute(
        mode="dag_execution",
        agents=["a", "b"],
        requires_planning=False,
        requires_dag=True,
        rationale="test",
    )


async def test_dag_parallel_execution_launches_concurrent_nodes() -> None:
    """Two dependency-free nodes must be launched concurrently via Send fan-out."""
    call_order: list[str] = []
    concurrent_calls: list[int] = []
    active_calls = [0]

    async def mock_run_agent(
        orchestrator: Any,
        session_id: UUID,
        agent_role: str,
        instruction: str,
        context: Any,
        tools: Any,
    ) -> SpecialistResult:
        active_calls[0] += 1
        concurrent_calls.append(active_calls[0])
        call_order.append(agent_role)
        await asyncio.sleep(0.01)  # simulate async work
        active_calls[0] -= 1
        return _make_result(agent_role)

    nodes = [
        TaskNode(id="node_a", agent_role="demand", deps=[]),
        TaskNode(id="node_b", agent_role="inventory", deps=[]),
    ]

    mock_orchestrator = MagicMock()
    session_id = uuid4()
    query = SessionUserQuery(text="test query")
    intent = _make_intent()
    route = _make_route()

    mock_response = SessionResponse(
        mode="dag_execution",
        reply="done",
        intent=intent,
        route=route,
    )

    with (
        patch(
            "packages.agent.orchestrator.planning.create_task_nodes",
            new=AsyncMock(return_value=nodes),
        ),
        patch(
            "packages.agent.orchestrator.runtime._run_agent",
            side_effect=mock_run_agent,
        ),
        patch(
            "packages.agent.orchestrator.planning._synthesize_response",
            new=AsyncMock(return_value=mock_response),
        ),
    ):
        from packages.agent.orchestrator.planning import run_dag_execution

        result = await run_dag_execution(mock_orchestrator, session_id, query, intent, route)

    assert result is mock_response
    assert set(call_order) == {"demand", "inventory"}
    # Both nodes should have been active at the same time
    assert max(concurrent_calls) == 2, (
        f"Expected both nodes to run concurrently, but max concurrent was {max(concurrent_calls)}"
    )


async def test_dag_send_api_a_before_b_and_c() -> None:
    """DAG A -> B, A -> C: A must execute first; B and C must then run in parallel.

    This validates the LangGraph Send API fan-out: the first dispatch round emits
    Send(run_dag_node, A); after A completes the second round emits
    Send(run_dag_node, B) and Send(run_dag_node, C) concurrently.
    """
    call_log: list[str] = []
    active_calls = [0]
    max_concurrent = [0]

    async def mock_run_agent(
        orchestrator: Any,
        session_id: UUID,
        agent_role: str,
        instruction: str,
        context: Any,
        tools: Any,
    ) -> SpecialistResult:
        call_log.append(f"start:{agent_role}")
        active_calls[0] += 1
        if active_calls[0] > max_concurrent[0]:
            max_concurrent[0] = active_calls[0]
        await asyncio.sleep(0.05)  # enough overlap time for B and C
        active_calls[0] -= 1
        call_log.append(f"end:{agent_role}")
        return _make_result(agent_role)

    # A has no deps; B and C both depend on A
    nodes = [
        TaskNode(id="A", agent_role="demand", deps=[]),
        TaskNode(id="B", agent_role="inventory", deps=["A"]),
        TaskNode(id="C", agent_role="finance", deps=["A"]),
    ]

    mock_orchestrator = MagicMock()
    session_id = uuid4()
    query = SessionUserQuery(text="test query")
    intent = _make_intent()
    route = _make_route()

    mock_response = SessionResponse(
        mode="dag_execution",
        reply="done",
        intent=intent,
        route=route,
    )

    with (
        patch(
            "packages.agent.orchestrator.planning.create_task_nodes",
            new=AsyncMock(return_value=nodes),
        ),
        patch(
            "packages.agent.orchestrator.runtime._run_agent",
            side_effect=mock_run_agent,
        ),
        patch(
            "packages.agent.orchestrator.planning._synthesize_response",
            new=AsyncMock(return_value=mock_response),
        ),
    ):
        from packages.agent.orchestrator.planning import run_dag_execution

        result = await run_dag_execution(mock_orchestrator, session_id, query, intent, route)

    assert result is mock_response

    # A must start and finish before B or C start
    a_end_idx = call_log.index("end:demand")
    b_start_idx = call_log.index("start:inventory")
    c_start_idx = call_log.index("start:finance")
    assert a_end_idx < b_start_idx, (
        f"A must finish before B starts; call_log={call_log}"
    )
    assert a_end_idx < c_start_idx, (
        f"A must finish before C starts; call_log={call_log}"
    )

    # B and C must overlap — both active at the same time
    assert max_concurrent[0] == 2, (
        f"Expected B and C to run concurrently; max_concurrent={max_concurrent[0]}; call_log={call_log}"
    )

    # All three nodes must have completed
    assert "end:demand" in call_log
    assert "end:inventory" in call_log
    assert "end:finance" in call_log
