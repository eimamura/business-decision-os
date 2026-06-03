from __future__ import annotations

import warnings
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from packages.agent.llm import (
    BudgetedClaudeClient,
    BudgetGuard,
    BudgetHardLimitError,
    BudgetSoftLimitWarning,
    LLMMessage,
    LLMResponse,
    LLMUsage,
    StubClaudeClient,
)
from packages.persistence.notifications_repo import NotificationsRepository
from packages.persistence.policies_repo import PoliciesRepository

# ---------------------------------------------------------------------------
# BudgetGuard
# ---------------------------------------------------------------------------


def test_budget_guard_accumulates():
    guard = BudgetGuard(soft_limit_usd=Decimal("1.0"), hard_limit_usd=Decimal("2.0"))
    guard.check_and_accumulate(Decimal("0.5"))
    assert guard.accumulated_cost == Decimal("0.5")


def test_budget_guard_no_warning_below_soft():
    guard = BudgetGuard(soft_limit_usd=Decimal("1.0"), hard_limit_usd=Decimal("2.0"))
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        guard.check_and_accumulate(Decimal("0.5"))
    assert len(w) == 0


def test_budget_guard_soft_limit_warning():
    guard = BudgetGuard(soft_limit_usd=Decimal("1.0"), hard_limit_usd=Decimal("2.0"))
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        guard.check_and_accumulate(Decimal("1.0"))
    assert len(w) == 1
    assert issubclass(w[0].category, BudgetSoftLimitWarning)


def test_budget_guard_hard_limit_raises():
    guard = BudgetGuard(soft_limit_usd=Decimal("1.0"), hard_limit_usd=Decimal("2.0"))
    guard.check_and_accumulate(Decimal("1.5"))
    with pytest.raises(BudgetHardLimitError):
        guard.check_and_accumulate(Decimal("0.6"))


def test_budget_guard_none_limits_no_error():
    guard = BudgetGuard(soft_limit_usd=None, hard_limit_usd=None)
    guard.check_and_accumulate(Decimal("999.99"))
    assert guard.accumulated_cost == Decimal("999.99")


def test_budget_guard_hard_limit_message():
    guard = BudgetGuard(soft_limit_usd=None, hard_limit_usd=Decimal("1.0"))
    with pytest.raises(BudgetHardLimitError, match="hard limit"):
        guard.check_and_accumulate(Decimal("1.5"))


# ---------------------------------------------------------------------------
# BudgetedClaudeClient
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_budgeted_client_accumulates_on_complete():
    inner = StubClaudeClient()
    guard = BudgetGuard(soft_limit_usd=Decimal("100"), hard_limit_usd=Decimal("200"))
    client = BudgetedClaudeClient(inner=inner, guard=guard)
    messages = [LLMMessage(role="user", content="hello")]
    await client.complete(messages)
    assert guard.accumulated_cost == Decimal("0")


@pytest.mark.asyncio
async def test_budgeted_client_raises_on_hard_limit():
    _inner = StubClaudeClient()

    class FakeInner(StubClaudeClient):
        async def complete(self, *args, **kwargs) -> LLMResponse:
            usage = LLMUsage(
                input_tokens=1000,
                output_tokens=1000,
                total_cost_usd=Decimal("1.5"),
            )
            return LLMResponse(
                text="x",
                tool_calls=[],
                finish_reason="stop",
                usage=usage,
                model="stub",
                request_id="r1",
                latency_ms=0,
            )

    guard = BudgetGuard(soft_limit_usd=None, hard_limit_usd=Decimal("1.0"))
    client = BudgetedClaudeClient(inner=FakeInner(), guard=guard)
    messages = [LLMMessage(role="user", content="hello")]
    with pytest.raises(BudgetHardLimitError):
        await client.complete(messages)


# ---------------------------------------------------------------------------
# Repository stubs raise NotImplementedError
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_notifications_repo_get_raises():
    repo = NotificationsRepository()
    with pytest.raises(NotImplementedError):
        await repo.get(uuid4())


@pytest.mark.asyncio
async def test_notifications_repo_create_raises():
    repo = NotificationsRepository()
    with pytest.raises(NotImplementedError):
        await repo.create({})


@pytest.mark.asyncio
async def test_notifications_repo_list_raises():
    repo = NotificationsRepository()
    with pytest.raises(NotImplementedError):
        await repo.list()


@pytest.mark.asyncio
async def test_notifications_repo_mark_read_raises():
    repo = NotificationsRepository()
    with pytest.raises(NotImplementedError):
        await repo.mark_read(uuid4())


@pytest.mark.asyncio
async def test_policies_repo_get_current_raises():
    repo = PoliciesRepository()
    with pytest.raises(NotImplementedError):
        await repo.get_current()


@pytest.mark.asyncio
async def test_policies_repo_create_raises():
    repo = PoliciesRepository()
    with pytest.raises(NotImplementedError):
        await repo.create({})


@pytest.mark.asyncio
async def test_policies_repo_update_raises():
    repo = PoliciesRepository()
    with pytest.raises(NotImplementedError):
        await repo.update(uuid4(), budget_soft_limit_usd=5.0)


# ---------------------------------------------------------------------------
# Approver role enforcement — HTTP-level (T-4002)
# ---------------------------------------------------------------------------


@pytest.fixture()
def api_client() -> TestClient:
    import os
    os.environ.setdefault("APP_ENV", "test")
    from apps.api.main import app
    return TestClient(app, raise_server_exceptions=False)


def test_post_decision_403_for_analyst(api_client: TestClient) -> None:
    approval_id = str(uuid4())
    response = api_client.post(
        f"/api/v1/approvals/{approval_id}/decision",
        json={"decision": "approved"},
        headers={"X-Dev-User": "regular-analyst"},
    )
    assert response.status_code == 403


def test_post_decision_200_for_approver(api_client: TestClient) -> None:
    approval_id = str(uuid4())
    response = api_client.post(
        f"/api/v1/approvals/{approval_id}/decision",
        json={"decision": "approved"},
        headers={"X-Dev-User": "dev-approver"},
    )
    # 404 expected since approval_id doesn't exist in DB — but NOT 403
    assert response.status_code != 403


def test_post_approval_creates_201(api_client: TestClient) -> None:
    from unittest.mock import AsyncMock, patch
    session_id = str(uuid4())
    mock_record: dict = {
        "id": str(uuid4()), "session_id": session_id, "status": "pending", "actor": "dev-user"
    }
    with patch("apps.api.routers.approvals._approvals_repo") as mock_repo:
        mock_repo.create = AsyncMock(return_value=mock_record)
        mock_repo.create.__aenter__ = AsyncMock(return_value=mock_record)
        response = api_client.post(
            "/api/v1/approvals",
            json={"session_id": session_id},
            headers={"X-Dev-User": "dev-user"},
        )
    assert response.status_code == 201


def test_get_notifications_returns_200(api_client: TestClient) -> None:
    response = api_client.get(
        "/api/v1/notifications",
        headers={"X-Dev-User": "dev-user"},
    )
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_put_policies_returns_200(api_client: TestClient) -> None:
    response = api_client.put(
        "/api/v1/policies",
        json={"budget_soft_limit_usd": 5.0, "budget_hard_limit_usd": 25.0},
        headers={"X-Dev-User": "dev-user"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["budget_soft_limit_usd"] == 5.0
    assert data["budget_hard_limit_usd"] == 25.0


# ---------------------------------------------------------------------------
# T-073: SessionOrchestrator execution mode routing via conditional edges
# ---------------------------------------------------------------------------
#
# These tests compile the StateGraph-based SessionOrchestrator with MemorySaver
# and verify that each execution mode routes to the correct node.
# They use the conditional edge functions directly to avoid full graph traversal
# (which would require DB-backed repositories).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_t073_session_orchestrator_compiles_with_memory_saver() -> None:
    """SessionOrchestrator._build_graph() must compile successfully with MemorySaver."""
    from langgraph.checkpoint.memory import MemorySaver

    from packages.agent.llm import ScenarioStubClaudeClient
    from packages.agent.orchestrator.session_orchestrator import SessionOrchestrator
    from packages.memory import StubMemoryStore
    from packages.tools import create_tool_registry

    orchestrator = SessionOrchestrator(
        llm_client=ScenarioStubClaudeClient(),
        tool_registry=create_tool_registry(),
        memory_store=StubMemoryStore(),
    )
    graph = orchestrator._build_graph(checkpointer=MemorySaver())
    assert graph is not None


@pytest.mark.parametrize(
    "mode,expected_node",
    [
        ("direct_chat", "run_direct_chat"),
        ("single_agent", "run_sequential"),
        ("sequential_agents", "run_sequential"),
        ("planned_execution", "run_planned"),
        ("dag_execution", "run_dag"),
    ],
    ids=[
        "direct_chat_routes_to_run_direct_chat",
        "single_agent_routes_to_run_sequential",
        "sequential_agents_routes_to_run_sequential",
        "planned_execution_routes_to_run_planned",
        "dag_execution_routes_to_run_dag",
    ],
)
def test_t073_edge_after_select_mode_routes_correctly(mode: str, expected_node: str) -> None:
    """_edge_after_select_mode must route each mode to the correct graph node."""
    from packages.agent.llm import ScenarioStubClaudeClient
    from packages.agent.orchestrator.models import AgentRoute
    from packages.agent.orchestrator.session_orchestrator import (
        OrchestratorState,
        SessionOrchestrator,
    )
    from packages.memory import StubMemoryStore
    from packages.tools import create_tool_registry

    orchestrator = SessionOrchestrator(
        llm_client=ScenarioStubClaudeClient(),
        tool_registry=create_tool_registry(),
        memory_store=StubMemoryStore(),
    )

    # Build a minimal OrchestratorState with a route that has the given mode.
    # We need agents to satisfy validate_route:
    #  - direct_chat: no agents
    #  - single_agent: exactly one agent
    #  - sequential_agents: one or more agents
    #  - planned_execution / dag_execution: agents list is not validated (no constraint)
    agents: list[str]
    if mode == "direct_chat":
        agents = []
    else:
        agents = ["demand"]

    route = AgentRoute(
        mode=mode,  # type: ignore[arg-type]
        agents=agents,
        requires_planning=mode == "planned_execution",
        requires_dag=mode == "dag_execution",
        rationale="test",
    )

    from packages.agent.orchestrator.models import SessionUserQuery
    state: OrchestratorState = {
        "session_id": str(uuid4()),
        "query": SessionUserQuery(text="test"),
        "intent": None,
        "route": route,
        "result": None,
        "error": None,
        "ask_user_id": None,
        "ask_user_question": None,
        "ask_user_answer": None,
    }

    actual_node = orchestrator._edge_after_select_mode(state)
    assert actual_node == expected_node, (
        f"mode='{mode}': expected edge to '{expected_node}', got '{actual_node}'"
    )


def test_t073_edge_after_select_mode_unknown_mode_returns_end() -> None:
    """An unknown mode must route to END rather than raising."""
    from langgraph.graph import END

    from packages.agent.llm import ScenarioStubClaudeClient
    from packages.agent.orchestrator.models import AgentRoute, SessionUserQuery
    from packages.agent.orchestrator.session_orchestrator import (
        OrchestratorState,
        SessionOrchestrator,
    )
    from packages.memory import StubMemoryStore
    from packages.tools import create_tool_registry

    orchestrator = SessionOrchestrator(
        llm_client=ScenarioStubClaudeClient(),
        tool_registry=create_tool_registry(),
        memory_store=StubMemoryStore(),
    )

    route = AgentRoute(
        mode="direct_chat",  # we override the mode field after construction
        agents=[],
        requires_planning=False,
        requires_dag=False,
        rationale="test",
    )
    # Manually override to an unknown mode (bypasses Pydantic validation)
    object.__setattr__(route, "mode", "unknown_mode")

    state: OrchestratorState = {
        "session_id": str(uuid4()),
        "query": SessionUserQuery(text="test"),
        "intent": None,
        "route": route,
        "result": None,
        "error": None,
        "ask_user_id": None,
        "ask_user_question": None,
        "ask_user_answer": None,
    }

    actual = orchestrator._edge_after_select_mode(state)
    assert actual == END


def test_t073_edge_after_select_mode_none_route_returns_end() -> None:
    """When route is None, _edge_after_select_mode must return END."""
    from langgraph.graph import END

    from packages.agent.llm import ScenarioStubClaudeClient
    from packages.agent.orchestrator.models import SessionUserQuery
    from packages.agent.orchestrator.session_orchestrator import (
        OrchestratorState,
        SessionOrchestrator,
    )
    from packages.memory import StubMemoryStore
    from packages.tools import create_tool_registry

    orchestrator = SessionOrchestrator(
        llm_client=ScenarioStubClaudeClient(),
        tool_registry=create_tool_registry(),
        memory_store=StubMemoryStore(),
    )

    state: OrchestratorState = {
        "session_id": str(uuid4()),
        "query": SessionUserQuery(text="test"),
        "intent": None,
        "route": None,
        "result": None,
        "error": None,
        "ask_user_id": None,
        "ask_user_question": None,
        "ask_user_answer": None,
    }

    actual = orchestrator._edge_after_select_mode(state)
    assert actual == END


def test_t073_session_orchestrator_graph_node_names() -> None:
    """The compiled SessionOrchestrator graph must contain all expected node names."""
    from langgraph.checkpoint.memory import MemorySaver

    from packages.agent.llm import ScenarioStubClaudeClient
    from packages.agent.orchestrator.session_orchestrator import SessionOrchestrator
    from packages.memory import StubMemoryStore
    from packages.tools import create_tool_registry

    orchestrator = SessionOrchestrator(
        llm_client=ScenarioStubClaudeClient(),
        tool_registry=create_tool_registry(),
        memory_store=StubMemoryStore(),
    )
    graph = orchestrator._build_graph(checkpointer=MemorySaver())
    node_names = set(graph.nodes.keys())

    expected = {
        "classify_intent",
        "prepare_ask_user",
        "wait_for_answer",
        "select_mode",
        "run_direct_chat",
        "run_sequential",
        "run_planned",
        "run_dag",
    }
    missing = expected - node_names
    assert not missing, f"SessionOrchestrator graph missing nodes: {missing}"
