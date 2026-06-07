from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from packages.agent.orchestrator.models import (
    AgentRoute,
    DagPlan,
    ExecutionPlan,
    PlanStep,
    SessionIntent,
    SessionUserQuery,
    TaskNode,
)
from packages.agent.orchestrator.planning import create_execution_plan, create_task_nodes


class _MockOrchestrator:
    _model_registry = None
    _llm_client: MagicMock = MagicMock()

    def _query_text(self, query: SessionUserQuery) -> str:
        return query.text


def _make_intent() -> SessionIntent:
    return SessionIntent(category="lookup", confidence=0.9, rationale="test intent")


def _make_route() -> AgentRoute:
    return AgentRoute(mode="single_agent", rationale="test route")


def _make_query(text: str = "What is the inventory level?") -> SessionUserQuery:
    return SessionUserQuery(text=text)


async def test_create_execution_plan_uses_structured_output_when_registry_provided() -> None:
    """create_execution_plan uses model.with_structured_output(ExecutionPlan) when registry set."""
    plan = ExecutionPlan(steps=[
        PlanStep(id="step-1", agent_role="control", instruction="Analyse inventory", tools=[])
    ])

    model_mock = MagicMock()
    structured = MagicMock()
    structured.ainvoke = AsyncMock(return_value=plan)
    model_mock.with_structured_output.return_value = structured

    registry = MagicMock()
    registry.get.return_value = model_mock

    orchestrator = _MockOrchestrator()
    orchestrator._model_registry = registry  # type: ignore[assignment]

    query = _make_query()
    intent = _make_intent()
    route = _make_route()
    session_id = uuid4()

    with patch(
        "packages.persistence.agent_steps_repo.make_step",
        AsyncMock(return_value="step-1"),
    ):
        result = await create_execution_plan(orchestrator, session_id, query, intent, route)

    model_mock.with_structured_output.assert_called_once_with(ExecutionPlan)
    structured.ainvoke.assert_called_once()
    assert result is plan


async def test_create_task_nodes_uses_dag_plan_when_registry_provided() -> None:
    """create_task_nodes uses model.with_structured_output(DagPlan) and returns list[TaskNode]."""
    nodes = [
        TaskNode(id="data", agent_role="control", deps=[], instruction="Fetch data", tools=[]),
        TaskNode(id="analyse", agent_role="control", deps=["data"], instruction="Analyse", tools=[]),
    ]
    dag = DagPlan(nodes=nodes)

    model_mock = MagicMock()
    structured = MagicMock()
    structured.ainvoke = AsyncMock(return_value=dag)
    model_mock.with_structured_output.return_value = structured

    registry = MagicMock()
    registry.get.return_value = model_mock

    orchestrator = _MockOrchestrator()
    orchestrator._model_registry = registry  # type: ignore[assignment]

    query = _make_query()
    intent = _make_intent()
    route = _make_route()
    session_id = uuid4()

    with patch(
        "packages.persistence.agent_steps_repo.make_step",
        AsyncMock(return_value="step-1"),
    ):
        result = await create_task_nodes(orchestrator, session_id, query, intent, route)

    model_mock.with_structured_output.assert_called_once_with(DagPlan)
    structured.ainvoke.assert_called_once()
    assert isinstance(result, list)
    assert len(result) == 2
    assert all(isinstance(n, TaskNode) for n in result)


async def test_create_execution_plan_raises_when_no_registry() -> None:
    """create_execution_plan raises AttributeError when _model_registry is None (no fallback)."""
    import pytest

    orchestrator = _MockOrchestrator()
    orchestrator._model_registry = None  # type: ignore[assignment]

    query = _make_query()
    intent = _make_intent()
    route = _make_route()
    session_id = uuid4()

    with patch(
        "packages.persistence.agent_steps_repo.make_step",
        AsyncMock(return_value="step-1"),
    ):
        with pytest.raises(AttributeError):
            await create_execution_plan(orchestrator, session_id, query, intent, route)


async def test_create_task_nodes_raises_when_no_registry() -> None:
    """create_task_nodes raises AttributeError when _model_registry is None (no fallback)."""
    import pytest

    orchestrator = _MockOrchestrator()
    orchestrator._model_registry = None  # type: ignore[assignment]

    query = _make_query()
    intent = _make_intent()
    route = _make_route()
    session_id = uuid4()

    with patch(
        "packages.persistence.agent_steps_repo.make_step",
        AsyncMock(return_value="step-1"),
    ):
        with pytest.raises(AttributeError):
            await create_task_nodes(orchestrator, session_id, query, intent, route)
