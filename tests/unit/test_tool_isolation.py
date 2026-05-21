from __future__ import annotations

import asyncio
from decimal import Decimal
from uuid import uuid4

import pytest

from packages.agent.base import PromptBasedSpecialist
from packages.agent.context_sanitizer import sanitize_for_llm, sanitize_sql_results
from packages.agent.llm import (
    LLMMessage,
    LLMResponse,
    StubClaudeClient,
)
from packages.agent.orchestrator import SessionGoal, SessionOrchestrator
from packages.agent.orchestrator.weights import (
    load_global_weights,
    load_sku_overrides,
    resolve_weights,
)
from packages.memory import StubMemoryStore
from packages.schemas.recommendation import Recommendation
from packages.tools import create_tool_registry
from packages.tools.approval_tool import ApprovalTool
from packages.tools.audit_tool import AuditLogTool
from packages.tools.base import ToolContext
from packages.tools.evaluator_tool import EvaluatorTool
from packages.tools.forecast_tool import ForecastTool
from packages.tools.optimizer_tool import OptimizerTool
from packages.tools.simulation_tool import SimulationTool
from packages.tools.sql_tool import SqlQueryTool


def _ctx() -> ToolContext:
    return ToolContext(
        session_id=uuid4(),
        agent_step_id=uuid4(),
        specialist_role="data_engineer",
        actor="test",
        correlation_id=uuid4(),
    )


# ===== T-1001: StubClaudeClient =====

@pytest.mark.asyncio
async def test_stub_client_complete_returns_schema_conformant():
    client = StubClaudeClient()
    messages = [LLMMessage(role="user", content="hello")]
    response = await client.complete(messages)
    assert isinstance(response, LLMResponse)
    assert response.text == "stub response"
    assert response.finish_reason == "stop"
    assert response.tool_calls == []
    assert response.usage.total_cost_usd == Decimal("0")


@pytest.mark.asyncio
async def test_stub_client_embed_returns_correct_shape():
    client = StubClaudeClient()
    embeddings = await client.embed(["text1", "text2"])
    assert len(embeddings) == 2
    assert len(embeddings[0]) == 1536


# ===== T-1002: UsageWriter callback =====

@pytest.mark.asyncio
async def test_usage_writer_called_on_complete():
    calls: list[tuple] = []

    async def writer(session_id, agent_step_id, specialist_role, provider, model, usage):
        calls.append((session_id, agent_step_id, specialist_role, provider, model, usage))

    client = StubClaudeClient(usage_writer=writer)
    messages = [LLMMessage(role="user", content="test")]
    await client.complete(messages, agent_step_id=uuid4(), specialist_role="evaluator")
    assert len(calls) == 1
    assert calls[0][3] == "anthropic"


# ===== T-1006: Weight resolution =====

def test_load_global_weights_returns_dict():
    weights = load_global_weights()
    assert isinstance(weights, dict)
    assert "service_level" in weights
    total = sum(weights.values())
    assert abs(total - 1.0) < 0.01


def test_load_sku_overrides_returns_dict():
    overrides = load_sku_overrides()
    assert isinstance(overrides, dict)


def test_resolve_weights_default():
    goal = SessionGoal(text="minimize cost")
    weights, source = resolve_weights(goal)
    assert source == "default"
    assert "service_level" in weights


def test_resolve_weights_session_goal_override():
    goal = SessionGoal(
        text="test",
        weight_override_json={"service_level": 0.8, "fill_rate": 0.2},
    )
    weights, source = resolve_weights(goal)
    assert source == "session_goal"
    assert weights["service_level"] == 0.8


# ===== T-1010: SqlQueryTool =====

@pytest.mark.asyncio
async def test_sql_tool_no_db_returns_empty():
    tool = SqlQueryTool()
    result = await tool.handle({"query": "SELECT * FROM sku_master"}, _ctx())
    assert result.output["row_count"] == 0
    assert "note" in result.output


@pytest.mark.asyncio
async def test_sql_tool_blocks_write_statements():
    tool = SqlQueryTool()
    result = await tool.handle({"query": "DELETE FROM sku_master WHERE 1=1"}, _ctx())
    assert "error" in result.output


@pytest.mark.asyncio
async def test_sql_tool_blocks_non_allowlist_table():
    tool = SqlQueryTool()
    result = await tool.handle({"query": "SELECT * FROM users"}, _ctx())
    assert "error" in result.output


# ===== T-1011: ApprovalTool =====

@pytest.mark.asyncio
async def test_approval_tool_returns_pending():
    tool = ApprovalTool()
    result = await tool.handle({"action_summary": "test action"}, _ctx())
    assert result.output["status"] == "pending"
    assert "approval_id" in result.output
    assert "expires_at" in result.output
    assert tool.requires_approval is True


# ===== T-1012: AuditLogTool =====

@pytest.mark.asyncio
async def test_audit_tool_returns_hash():
    tool = AuditLogTool()
    result = await tool.handle({"event_type": "test", "payload": {"key": "value"}}, _ctx())
    assert result.output["recorded"] is True
    assert "audit_hash" in result.output
    assert len(result.output["audit_hash"]) == 64  # SHA256 hex


# ===== T-1013: ForecastTool =====

@pytest.mark.asyncio
async def test_forecast_tool_stub_returns_schema():
    tool = ForecastTool()
    result = await tool.handle({"sku_id": "SKU001", "horizon_days": 7}, _ctx())
    assert result.output["sku_id"] == "SKU001"
    assert len(result.output["forecast_units"]) == 7
    assert result.output["model_version"] == "moving_avg_v1_stub"
    assert result.output["nulls_skipped"] == 0


# ===== T-1014: SimulationTool =====

@pytest.mark.asyncio
async def test_simulation_tool_returns_schema():
    tool = SimulationTool()
    result = await tool.handle({"sku_id": "SKU001", "order_qty": 200.0, "horizon_days": 90}, _ctx())
    assert result.output["sku_id"] == "SKU001"
    assert "ending_on_hand" in result.output
    assert "stockout_days" in result.output
    assert "mean_lead_time_days" in result.output


# ===== T-1015: OptimizerTool =====

@pytest.mark.asyncio
async def test_optimizer_tool_returns_3_candidates():
    tool = OptimizerTool()
    result = await tool.handle({"sku_id": "SKU001", "moq": 100.0, "horizon_days": 90}, _ctx())
    candidates = result.output["candidates"]
    assert len(candidates) == 3
    costs = [c["total_supply_chain_cost"] for c in candidates]
    assert costs == sorted(costs)


@pytest.mark.asyncio
async def test_optimizer_tool_moq_constraint():
    tool = OptimizerTool()
    result = await tool.handle({"sku_id": "SKU001", "moq": 50.0, "horizon_days": 90}, _ctx())
    for candidate in result.output["candidates"]:
        assert "MOQ" in candidate["constraints_satisfied"]


# ===== T-1016: EvaluatorTool =====

@pytest.mark.asyncio
async def test_evaluator_tool_8_kpis():
    tool = EvaluatorTool()
    candidates = [
        {"id": "c1", "order_qty": 100.0, "total_supply_chain_cost": 120.0},
        {"id": "c2", "order_qty": 200.0, "total_supply_chain_cost": 240.0},
    ]
    result = await tool.handle({"candidates": candidates}, _ctx())
    evaluations = result.output["evaluations"]
    assert len(evaluations) == 2
    for ev in evaluations:
        assert len(ev["kpi_scores"]) == 8
        assert ev["risk_level"] in ("low", "medium", "high")


@pytest.mark.asyncio
async def test_evaluator_no_collapsed_total():
    tool = EvaluatorTool()
    candidates = [{"id": "c1", "order_qty": 100.0}]
    result = await tool.handle({"candidates": candidates}, _ctx())
    ev = result.output["evaluations"][0]
    kpi_names = [s["name"] for s in ev["kpi_scores"]]
    assert "weighted_total" not in kpi_names
    assert len(kpi_names) == 8


# ===== T-1017: Context sanitizer =====

def test_sanitize_sql_results_no_raw_rows():
    rows = [{"sku": "A", "units": 10}, {"sku": "B", "units": 20}]
    result = sanitize_sql_results(rows)
    assert "rows" not in result
    assert result["row_count"] == 2
    assert "sample_aggregates" in result
    assert result["note"] == "summarized for LLM context"


def test_sanitize_sql_results_empty():
    result = sanitize_sql_results([])
    assert result["row_count"] == 0


def test_sanitize_for_llm_returns_string():
    data = {"key": "value", "number": 42}
    s = sanitize_for_llm(data)
    assert isinstance(s, str)
    import json
    parsed = json.loads(s)
    assert parsed["key"] == "value"


# ===== create_tool_registry =====

def test_create_tool_registry_has_all_tools():
    registry = create_tool_registry()
    expected = [
        "sql_query", "request_approval", "write_audit_log",
        "forecast", "simulate_inventory", "optimize_replenishment",
        "evaluate_candidates",
    ]
    for name in expected:
        assert registry.get(name) is not None


def test_list_for_role_domain_expert():
    registry = create_tool_registry()
    tools = registry.list_for_role("domain_expert")
    names = {t.name for t in tools}
    assert "sql_query" in names
    assert "forecast" in names
    assert "simulate_inventory" not in names


def test_list_for_role_sim_opt():
    registry = create_tool_registry()
    tools = registry.list_for_role("sim_opt")
    names = {t.name for t in tools}
    assert "simulate_inventory" in names
    assert "optimize_replenishment" in names
    assert "sql_query" not in names


def test_list_for_role_orchestrator_returns_empty():
    registry = create_tool_registry()
    tools = registry.list_for_role("orchestrator")
    assert tools == []


# ===== T-1003/T-1040: Orchestrator + MemoryStore =====

@pytest.mark.asyncio
async def test_orchestrator_run_returns_recommendation():
    client = StubClaudeClient()
    registry = create_tool_registry()
    memory = StubMemoryStore()
    sse_queue: asyncio.Queue = asyncio.Queue()

    orchestrator = SessionOrchestrator(
        llm_client=client,
        tool_registry=registry,
        memory_store=memory,
        sse_queue=sse_queue,
    )

    session_id = uuid4()
    goal = SessionGoal(text="optimize replenishment for SKU001")
    recommendation = await orchestrator.run(session_id, goal)

    assert isinstance(recommendation, Recommendation)
    assert recommendation.primary is not None
    assert len(recommendation.alternatives) >= 1
    assert recommendation.risk_level in ("low", "medium", "high")
    assert recommendation.tradeoff.weight_source in (
        "default", "session_goal", "critical_sku", "user_policy"
    )


@pytest.mark.asyncio
async def test_orchestrator_emits_sse_events():
    client = StubClaudeClient()
    registry = create_tool_registry()
    memory = StubMemoryStore()
    sse_queue: asyncio.Queue = asyncio.Queue()

    orchestrator = SessionOrchestrator(
        llm_client=client,
        tool_registry=registry,
        memory_store=memory,
        sse_queue=sse_queue,
    )

    session_id = uuid4()
    goal = SessionGoal(text="test goal")
    await orchestrator.run(session_id, goal)

    events = []
    while not sse_queue.empty():
        events.append(sse_queue.get_nowait())

    event_types = {e["type"] for e in events}
    assert "step_started" in event_types
    assert "step_completed" in event_types
    assert "recommendation_ready" in event_types


@pytest.mark.asyncio
async def test_orchestrator_session_goal_weight_override():
    client = StubClaudeClient()
    registry = create_tool_registry()
    memory = StubMemoryStore()

    orchestrator = SessionOrchestrator(
        llm_client=client,
        tool_registry=registry,
        memory_store=memory,
    )

    session_id = uuid4()
    goal = SessionGoal(
        text="maximize service level",
        weight_override_json={"service_level": 0.9, "total_supply_chain_cost": 0.1},
    )
    recommendation = await orchestrator.run(session_id, goal)
    assert recommendation.tradeoff.weight_source == "session_goal"


# ===== T-1004: PromptBasedSpecialist pipeline roles =====

def test_pipeline_specialist_roles_instantiate():
    client = StubClaudeClient()
    registry = create_tool_registry()
    specialists = {
        role: PromptBasedSpecialist(name=role, role=role, llm_client=client, tool_registry=registry)
        for role in ("domain_expert", "data_engineer", "sim_opt", "evaluator")
    }
    assert len(specialists) == 4
    for role in ["domain_expert", "data_engineer", "sim_opt", "evaluator"]:
        assert role in specialists


@pytest.mark.asyncio
async def test_specialist_run_returns_result():
    client = StubClaudeClient()
    registry = create_tool_registry()
    specialist = PromptBasedSpecialist(
        name="domain_expert", role="domain_expert",
        llm_client=client, tool_registry=registry,
    )

    from packages.agent.orchestrator import SpecialistTask
    task = SpecialistTask(
        task_id=uuid4(),
        instruction="analyze demand",
        context_payload={},
        allowed_tools=["sql_query", "forecast"],
    )

    ctx = ToolContext(
        session_id=uuid4(),
        agent_step_id=task.task_id,
        specialist_role="domain_expert",
        actor="test",
        correlation_id=uuid4(),
    )

    result = await specialist.run(task, ctx)
    assert result.status == "completed"
    assert isinstance(result.output, dict)
