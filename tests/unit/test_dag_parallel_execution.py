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
    """Two dependency-free nodes must be launched concurrently via asyncio.gather."""
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
