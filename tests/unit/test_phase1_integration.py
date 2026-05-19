"""Phase 1 integration tests: Orchestrator + Specialists + Tools with StubClaudeClient."""
import asyncio
from pathlib import Path
from uuid import uuid4

import pytest
import yaml

from packages.agent.llm import StubClaudeClient
from packages.agent.orchestrator import PhaseOrchestrator, SessionGoal
from packages.memory import StubMemoryStore
from packages.tools import create_tool_registry


@pytest.fixture
def scenarios():
    """Load test scenarios from YAML fixture."""
    fixture_path = Path("data/fixtures/scenarios.yaml")
    with open(fixture_path) as f:
        data = yaml.safe_load(f)
    return data["scenarios"]


@pytest.fixture
def stub_orchestrator():
    """Orchestrator wired with StubClaudeClient and in-memory tools."""
    llm_client = StubClaudeClient()
    tool_registry = create_tool_registry()
    memory_store = StubMemoryStore()
    queue = asyncio.Queue()
    return PhaseOrchestrator(llm_client, tool_registry, memory_store, sse_queue=queue), queue


@pytest.mark.asyncio
async def test_orchestrator_run_basic(stub_orchestrator):
    """Orchestrator.run() returns a valid Recommendation."""
    orchestrator, queue = stub_orchestrator
    session_id = uuid4()
    goal = SessionGoal(text="Optimize replenishment for SKU-001")

    recommendation = await orchestrator.run(session_id, goal)

    assert recommendation is not None
    assert recommendation.primary is not None
    assert len(recommendation.alternatives) >= 2
    assert recommendation.risk_level in ("low", "medium", "high")
    assert recommendation.tradeoff is not None
    assert recommendation.tradeoff.weight_source in (
        "default", "session_goal", "critical_sku", "user_policy"
    )


@pytest.mark.asyncio
async def test_orchestrator_emits_sse_events(stub_orchestrator):
    """Orchestrator pushes SSE events to the queue."""
    orchestrator, queue = stub_orchestrator
    session_id = uuid4()
    goal = SessionGoal(text="Test SSE event emission")

    await orchestrator.run(session_id, goal)

    events = []
    while not queue.empty():
        events.append(await queue.get())

    event_types = [e.get("type") for e in events]
    assert "step_started" in event_types
    assert "step_completed" in event_types


@pytest.mark.asyncio
async def test_orchestrator_recommendation_has_kpi_scores(stub_orchestrator):
    """Each candidate has per-KPI scores (no collapsed total)."""
    orchestrator, _ = stub_orchestrator
    session_id = uuid4()
    goal = SessionGoal(text="Test KPI scores")

    recommendation = await orchestrator.run(session_id, goal)

    assert len(recommendation.primary.kpi_scores) > 0
    kpi_names = {s.name for s in recommendation.primary.kpi_scores}
    assert "service_level" in kpi_names
    assert "total_supply_chain_cost" in kpi_names

    for score in recommendation.primary.kpi_scores:
        assert score.name != "total_weighted_score"
        assert score.direction in ("higher_better", "lower_better")


@pytest.mark.asyncio
async def test_orchestrator_scenarios_yaml(stub_orchestrator, scenarios):
    """Run each scenario from YAML fixtures."""
    orchestrator, _ = stub_orchestrator

    for scenario in scenarios:
        session_id = uuid4()
        goal = SessionGoal(text=scenario["goal"]["text"])
        recommendation = await orchestrator.run(session_id, goal)

        expected = scenario["expected"]
        if expected.get("has_recommendation"):
            assert recommendation is not None
        if "min_alternatives" in expected:
            assert len(recommendation.alternatives) >= expected["min_alternatives"]


@pytest.mark.asyncio
async def test_stub_llm_client_returns_valid_response():
    """StubClaudeClient returns a schema-conformant LLMResponse."""
    from packages.agent.llm import LLMMessage

    client = StubClaudeClient()
    response = await client.complete(
        messages=[LLMMessage(role="user", content="test")],
    )
    assert response.text == "stub response"
    assert response.finish_reason == "stop"
    assert response.tool_calls == []
    assert response.usage.total_cost_usd >= 0
    assert response.model is not None


@pytest.mark.asyncio
async def test_memory_store_write_persists():
    """StubMemoryStore.write() stores and get() retrieves."""
    from datetime import datetime, timezone

    from packages.memory import Memory, StubMemoryStore

    store = StubMemoryStore()
    memory_id = uuid4()
    memory = Memory(
        id=memory_id,
        scope="global",
        type="decision",
        content="Test memory",
        metadata={"session_id": str(uuid4())},
        created_at=datetime.now(timezone.utc).isoformat(),
    )

    returned_id = await store.write(memory)
    assert returned_id == memory_id

    retrieved = await store.get(memory_id)
    assert retrieved is not None
    assert retrieved.content == "Test memory"


@pytest.mark.asyncio
async def test_memory_store_search_returns_empty():
    """StubMemoryStore.search() always returns [] in Phase 1."""
    from packages.memory import MemoryQuery, StubMemoryStore

    store = StubMemoryStore()
    results = await store.search(MemoryQuery(query_text="test"))
    assert results == []
