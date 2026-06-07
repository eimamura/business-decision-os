from __future__ import annotations

import asyncio
from decimal import Decimal
from uuid import uuid4

import pytest

from packages.agent.base import AgentBasedSpecialist
from packages.agent.context_sanitizer import sanitize_for_llm, sanitize_sql_results
from packages.agent.llm import (
    LLMMessage,
    LLMResponse,
    LLMUsage,
    StubClaudeClient,
)
from packages.agent.orchestrator import SessionGoal, SessionOrchestrator, SessionUserQuery
from packages.agent.orchestrator.models import AgentRoute, AskUserDecision, SessionIntent
from tests.unit.helpers import FakeLCModel, MultiRoleModelRegistry, StructuredOutputFakeModel, make_stop_response
from packages.agent.orchestrator.weights import (
    load_global_weights,
    load_sku_overrides,
    resolve_weights,
)
from packages.memory import StubMemoryStore
from packages.tools import create_tool_registry
from packages.tools.approval_tool import ApprovalTool
from packages.tools.audit_tool import AuditLogTool
from packages.tools.base import ToolContext
from packages.tools.data_catalog_search_tool import DataCatalogSearchTool
from packages.tools.data_quality_checker_tool import DataQualityCheckerTool
from packages.tools.evaluator_tool import EvaluatorTool
from packages.tools.forecast_tool import ForecastTool
from packages.tools.nl_query_tool import NlQueryTool
from packages.tools.optimizer_tool import OptimizerTool
from packages.tools.simulation_tool import SimulationTool
from packages.tools.sql_allowlist import ALLOWED_READ_TABLES
from packages.tools.sql_guardrail import SQLGuardrailError, validate_read_sql
from packages.tools.table_schema_reader_tool import TableSchemaReaderTool


def _ctx() -> ToolContext:
    return ToolContext(
        session_id=uuid4(),
        agent_step_id=uuid4(),
        specialist_role="data_engineer",
        actor="test",
        correlation_id=uuid4(),
    )


def _extract_system_text(messages: list) -> str:
    """Read system text from plain content or content_blocks (T-008 3-block caching)."""
    if not messages:
        return ""
    msg = messages[0]
    if not msg.content and getattr(msg, "content_blocks", None):
        blocks = msg.content_blocks or []
        return blocks[0].get("text", "") if blocks else ""
    return msg.content or ""


class PlanningStubClaudeClient(StubClaudeClient):
    async def complete(self, messages, **kwargs) -> LLMResponse:
        system = _extract_system_text(messages)
        if "intent classifier" in system:
            return LLMResponse(
                text=(
                    '{"category":"decision_support","confidence":0.9,'
                    '"rationale":"Optimization requested","goal_text":"optimize replenishment"}'
                ),
                tool_calls=[],
                finish_reason="stop",
                usage=LLMUsage(input_tokens=0, output_tokens=0, total_cost_usd=Decimal("0")),
                model="stub",
                request_id=str(uuid4()),
                latency_ms=0,
            )
        if "router inside SessionOrchestrator" in system:
            return LLMResponse(
                text=(
                    '{"mode":"single_agent","agents":["control"],'
                    '"requires_planning":false,"requires_dag":false,"rationale":"control-only"}'
                ),
                tool_calls=[],
                finish_reason="stop",
                usage=LLMUsage(input_tokens=0, output_tokens=0, total_cost_usd=Decimal("0")),
                model="stub",
                request_id=str(uuid4()),
                latency_ms=0,
            )
        if messages and "Return ONLY a JSON array of task nodes" in system:
            return LLMResponse(
                text=(
                    '[{"id":"domain","specialist_type":"demand","deps":[],"tools":[]},'
                    '{"id":"data","specialist_type":"data_engineer","deps":[],"tools":["sql_query"]},'
                    '{"id":"sim","specialist_type":"simulation_optimizer","deps":["data"],'
                    '"tools":["simulate_inventory","optimize_replenishment"]},'
                    '{"id":"eval","specialist_type":"evaluator","deps":["sim"],'
                    '"tools":["evaluate_candidates","write_audit_log"]}]'
                ),
                tool_calls=[],
                finish_reason="stop",
                usage=LLMUsage(input_tokens=0, output_tokens=0, total_cost_usd=Decimal("0")),
                model="stub",
                request_id=str(uuid4()),
                latency_ms=0,
            )
        # ControlAgent (P45: single control agent architecture)
        if "cross-domain operational judgment center" in system:
            return LLMResponse(
                text="Supply chain analysis complete. No critical issues detected.",
                tool_calls=[],
                finish_reason="stop",
                usage=LLMUsage(
                    input_tokens=0, output_tokens=0, total_cost_usd=Decimal("0")
                ),
                model="stub",
                request_id=str(uuid4()),
                latency_ms=0,
            )
        return await super().complete(messages, **kwargs)


# ===== T-1001: StubClaudeClient =====

async def test_stub_client_complete_returns_schema_conformant():
    client = StubClaudeClient()
    messages = [LLMMessage(role="user", content="hello")]
    response = await client.complete(messages)
    assert isinstance(response, LLMResponse)
    assert response.text == "stub response"
    assert response.finish_reason == "stop"
    assert response.tool_calls == []
    assert response.usage.total_cost_usd == Decimal("0")


async def test_stub_client_embed_returns_correct_shape():
    client = StubClaudeClient()
    embeddings = await client.embed(["text1", "text2"])
    assert len(embeddings) == 2
    assert len(embeddings[0]) == 1536


# ===== T-1002: UsageWriter callback =====

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


# ===== T-1007: DataCatalogSearchTool =====

async def test_data_catalog_search_no_db_returns_all_tables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import packages.persistence.db as _db
    monkeypatch.delenv("DATABASE_URL", raising=False)
    _db._pool = None
    tool = DataCatalogSearchTool()
    result = await tool.handle({}, _ctx())
    assert result.output["count"] == len(ALLOWED_READ_TABLES)
    assert all(row["row_count"] is None for row in result.output["tables"])


async def test_data_catalog_search_keyword_filter_no_db():
    tool = DataCatalogSearchTool()
    result = await tool.handle({"keyword": "inv"}, _ctx())
    names = [row["table_name"] for row in result.output["tables"]]
    assert names == ["inventory_snapshot"]
    assert result.output["count"] == 1


# ===== T-1008: TableSchemaReaderTool =====

async def test_table_schema_reader_rejects_non_allowlist_table():
    tool = TableSchemaReaderTool()
    result = await tool.handle({"table_name": "users"}, _ctx())
    assert "error" in result.output


async def test_table_schema_reader_no_db_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import packages.persistence.db as _db
    monkeypatch.delenv("DATABASE_URL", raising=False)
    _db._pool = None
    tool = TableSchemaReaderTool()
    result = await tool.handle({"table_name": "sku_master"}, _ctx())
    assert "error" not in result.output
    assert "note" in result.output
    assert result.output["column_count"] == 0


# ===== T-1009: DataQualityCheckerTool =====

async def test_data_quality_checker_rejects_non_allowlist_table():
    tool = DataQualityCheckerTool()
    result = await tool.handle({"table_name": "users"}, _ctx())
    assert "error" in result.output


async def test_data_quality_checker_no_db_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import packages.persistence.db as _db
    monkeypatch.delenv("DATABASE_URL", raising=False)
    _db._pool = None
    tool = DataQualityCheckerTool()
    result = await tool.handle({"table_name": "inventory_snapshot"}, _ctx())
    assert "error" not in result.output
    assert result.output["total_rows"] == 0
    assert result.output["has_issues"] is False
    assert "note" in result.output


# ===== T-1010: SqlQueryTool =====

@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM sku_master",
        "SELECT * FROM public.sku_master",
        'SELECT * FROM "sku_master"',
    ],
)
def test_sql_guardrail_allows_allowlisted_tables(sql: str):
    validate_read_sql(sql)


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 1",
        "SELECT pg_sleep(10)",
        "COPY sku_master TO STDOUT",
        "DELETE FROM sku_master WHERE 1=1",
        "SELECT * FROM sku_master; DELETE FROM sku_master WHERE 1=1",
        "SELECT * FROM users",
        'SELECT * FROM "users"',
        'SELECT * FROM sku_master JOIN "users" u ON u.id = sku_master.sku_id',
        "SELECT * FROM sku_master, users",
        "WITH u AS (SELECT * FROM users) SELECT * FROM sku_master",
        "SELECT * FROM (SELECT * FROM users) u JOIN sku_master s ON 1=1",
        "SELECT * FROM sku_master UNION SELECT * FROM users",
        "SELECT * FROM other_schema.sku_master",
    ],
)
def test_sql_guardrail_rejects_unsafe_sql(sql: str):
    with pytest.raises(SQLGuardrailError):
        validate_read_sql(sql)


async def test_nl_query_tool_guardrail_blocks_without_execution(
    monkeypatch: pytest.MonkeyPatch,
):
    class _FakeAIMessage:
        content = "SELECT pg_sleep(10)"

    class _StubModel:
        async def ainvoke(self, messages: object, **kwargs: object) -> _FakeAIMessage:
            return _FakeAIMessage()

    async def fail_execute(query: str):
        raise AssertionError(f"query should not execute: {query}")

    monkeypatch.setattr("packages.tools.nl_query_tool.execute_read_query", fail_execute)
    tool = NlQueryTool(model=_StubModel())
    result = await tool.handle({"question": "wait"}, _ctx())
    assert "error" in result.output
    assert result.output["results"] == []
    assert result.output["count"] == 0
    assert result.output["sql"] == ""


# ===== T-1011: ApprovalTool =====

async def test_approval_tool_returns_pending():
    tool = ApprovalTool()
    result = await tool.handle({"action_summary": "test action"}, _ctx())
    assert result.output["status"] == "pending"
    assert "approval_id" in result.output
    assert "expires_at" in result.output
    assert tool.safety_level == "hitl"


# ===== T-1012: AuditLogTool =====

async def test_audit_tool_returns_hash():
    tool = AuditLogTool()
    result = await tool.handle({"event_type": "test", "payload": {"key": "value"}}, _ctx())
    assert result.output["recorded"] is True
    assert "audit_hash" in result.output
    assert len(result.output["audit_hash"]) == 64  # SHA256 hex


# ===== T-1013: ForecastTool =====

def test_forecast_tool_raises_without_predictor():
    with pytest.raises(RuntimeError, match="requires a predictor"):
        ForecastTool(predictor=None)


async def test_forecast_tool_with_predictor_returns_schema():
    from packages.prediction import LinearRegressionPredictor
    tool = ForecastTool(predictor=LinearRegressionPredictor(db_session=None))
    result = await tool.handle({"sku_id": "SKU001", "horizon_days": 7}, _ctx())
    assert result.output["sku_id"] == "SKU001"
    assert len(result.output["forecast_units"]) == 7
    assert result.output["nulls_skipped"] == 0


# ===== T-1014: SimulationTool =====

async def test_simulation_tool_returns_schema():
    tool = SimulationTool()
    result = await tool.handle({"sku_id": "SKU001", "order_qty": 200.0, "horizon_days": 90}, _ctx())
    assert result.output["sku_id"] == "SKU001"
    assert "ending_on_hand" in result.output
    assert "stockout_days" in result.output
    assert "mean_lead_time_days" in result.output


# ===== T-1015: OptimizerTool =====

async def test_optimizer_tool_returns_3_candidates():
    tool = OptimizerTool()
    result = await tool.handle({"sku_id": "SKU001", "moq": 100.0, "horizon_days": 90}, _ctx())
    candidates = result.output["candidates"]
    assert len(candidates) == 3
    costs = [c["total_supply_chain_cost"] for c in candidates]
    assert costs == sorted(costs)


async def test_optimizer_tool_moq_constraint():
    tool = OptimizerTool()
    result = await tool.handle({"sku_id": "SKU001", "moq": 50.0, "horizon_days": 90}, _ctx())
    for candidate in result.output["candidates"]:
        assert "MOQ" in candidate["constraints_satisfied"]


# ===== T-1016: EvaluatorTool =====

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


async def test_evaluator_no_collapsed_total():
    tool = EvaluatorTool()
    candidates = [{"id": "c1", "order_qty": 100.0}]
    result = await tool.handle({"candidates": candidates}, _ctx())
    ev = result.output["evaluations"][0]
    kpi_names = [s["name"] for s in ev["kpi_scores"]]
    assert "weighted_total" not in kpi_names
    assert len(kpi_names) == 8


# ===== T-1017: Context sanitizer =====

def test_sanitize_sql_results_includes_rows():
    rows = [{"sku": "A", "units": 10}, {"sku": "B", "units": 20}]
    result = sanitize_sql_results(rows)
    assert result["rows"] == rows
    assert result["row_count"] == 2
    assert result["truncated"] is False
    assert result["columns"] == ["sku", "units"]
    assert "sample_aggregates" not in result


def test_sanitize_sql_results_empty():
    result = sanitize_sql_results([])
    assert result["row_count"] == 0
    assert result["rows"] == []
    assert result["truncated"] is False
    assert result["columns"] == []


def test_sanitize_sql_results_truncates_rows():
    rows = [{"id": i, "value": float(i)} for i in range(200)]
    result = sanitize_sql_results(rows, max_rows=100)
    assert len(result["rows"]) == 100
    assert result["row_count"] == 200
    assert result["truncated"] is True
    assert result["columns"] == ["id", "value"]
    assert "sample_aggregates" in result


def test_inject_limit_adds_when_missing():
    from packages.persistence.query_repo import _inject_limit
    result = _inject_limit("SELECT * FROM sku_master", 1000)
    assert result.endswith("LIMIT 1000")


def test_inject_limit_skips_when_present():
    from packages.persistence.query_repo import _inject_limit
    result = _inject_limit("SELECT * FROM sku_master LIMIT 10", 1000)
    assert result.count("LIMIT") == 1
    assert "LIMIT 10" in result


def test_inject_limit_strips_trailing_semicolon():
    from packages.persistence.query_repo import _inject_limit
    result = _inject_limit("SELECT * FROM sku_master;", 1000)
    assert result.endswith("LIMIT 1000")
    assert ";" not in result


def test_inject_limit_cte_without_limit():
    from packages.persistence.query_repo import _inject_limit
    sql = "WITH t AS (SELECT sku_id FROM sku_master) SELECT * FROM t"
    result = _inject_limit(sql, 1000)
    assert result.endswith("LIMIT 1000")


def test_sanitize_for_llm_returns_string():
    data = {"key": "value", "number": 42}
    s = sanitize_for_llm(data)
    assert isinstance(s, str)
    import json
    parsed = json.loads(s)
    assert parsed["key"] == "value"


def test_nl_query_rules_include_limit():
    from packages.tools.nl_query_tool import _SQL_RULES
    assert "LIMIT" in _SQL_RULES


# ===== create_tool_registry =====

def test_create_tool_registry_has_all_tools():
    registry = create_tool_registry()
    expected = [
        "nl_query", "request_approval", "write_audit_log",
        "forecast", "simulate_inventory", "optimize_replenishment",
        "evaluate_candidates",
        "data_catalog_search", "table_schema_reader", "data_quality_checker",
    ]
    for name in expected:
        assert registry.get(name) is not None



def test_list_for_role_simulation_optimizer():
    registry = create_tool_registry()
    tools = registry.list_for_role("simulation_optimizer")
    names = {t.name for t in tools}
    assert "simulate_inventory" in names
    assert "optimize_replenishment" in names
    assert "sql_query" not in names


def test_list_for_role_orchestrator_returns_empty():
    registry = create_tool_registry()
    tools = registry.list_for_role("orchestrator")
    assert [t.name for t in tools] == ["job_dispatch"]


def _make_single_agent_registry() -> MultiRoleModelRegistry:
    """ModelRegistry that routes classify_intent → decision_support, select_mode → single_agent."""
    orchestrator_model = StructuredOutputFakeModel([
        SessionIntent(
            category="decision_support", confidence=0.9,
            rationale="Optimization requested", goal_text="optimize replenishment",
        ),
        # _node_prepare_ask_user fires for "decision_support" — return no-input decision
        AskUserDecision(needs_input=False, question=None, suggestions=None),
        AgentRoute(
            mode="single_agent", agents=["control"],
            requires_planning=False, requires_dag=False, rationale="control-only",
        ),
    ])
    specialist_model = FakeLCModel([
        make_stop_response("Supply chain analysis complete. No critical issues detected."),
        make_stop_response("pass"),
    ])
    return MultiRoleModelRegistry({"orchestrator": orchestrator_model, "default": specialist_model})


# ===== T-1003/T-1040: Orchestrator + MemoryStore =====

async def test_orchestrator_run_returns_session_response():
    client = PlanningStubClaudeClient()
    registry = create_tool_registry()
    memory = StubMemoryStore()
    sse_queue: asyncio.Queue = asyncio.Queue()

    orchestrator = SessionOrchestrator(
        llm_client=client,
        tool_registry=registry,
        memory_store=memory,
        sse_queue=sse_queue,
        model_registry=_make_single_agent_registry(),
    )

    session_id = uuid4()
    query = SessionUserQuery(text="optimize replenishment for SKU001")
    response = await orchestrator.run(session_id, query)

    # P45: single ControlAgent — synthesis path (no decision candidates)
    assert response.mode == "single_agent"
    assert isinstance(response.reply, str)
    assert len(response.reply) > 0


async def test_orchestrator_emits_sse_events():
    client = PlanningStubClaudeClient()
    registry = create_tool_registry()
    memory = StubMemoryStore()
    sse_queue: asyncio.Queue = asyncio.Queue()

    orchestrator = SessionOrchestrator(
        llm_client=client,
        tool_registry=registry,
        memory_store=memory,
        sse_queue=sse_queue,
        model_registry=_make_single_agent_registry(),
    )

    session_id = uuid4()
    query = SessionUserQuery(text="test goal")
    await orchestrator.run(session_id, query)

    events = []
    while not sse_queue.empty():
        events.append(sse_queue.get_nowait())

    event_types = {e["type"] for e in events}
    # P20: query_received/intent_classified/execution_mode_selected replaced by graph_node events
    assert "graph_node" in event_types
    assert "response_ready" in event_types


async def test_orchestrator_session_goal_weight_override():
    client = PlanningStubClaudeClient()
    registry = create_tool_registry()
    memory = StubMemoryStore()

    orchestrator = SessionOrchestrator(
        llm_client=client,
        tool_registry=registry,
        memory_store=memory,
        model_registry=_make_single_agent_registry(),
    )

    session_id = uuid4()
    query = SessionUserQuery(
        text="maximize service level",
        weight_override_json={"service_level": 0.9, "total_supply_chain_cost": 0.1},
    )
    response = await orchestrator.run(session_id, query)
    # P45: single ControlAgent — synthesis path; weight_override still accepted
    assert response.mode == "single_agent"
    assert isinstance(response.reply, str)


# ===== T-1004: Prompt-based execution roles =====

def test_prompt_based_execution_roles_instantiate():
    client = StubClaudeClient()
    registry = create_tool_registry()
    specialists = {
        role: AgentBasedSpecialist(name=role, role=role, llm_client=client, tool_registry=registry)
        for role in ("data_engineer", "simulation_optimizer", "evaluator")
    }
    assert len(specialists) == 3
    for role in ["data_engineer", "simulation_optimizer", "evaluator"]:
        assert role in specialists


async def test_specialist_run_returns_result():
    client = StubClaudeClient()
    registry = create_tool_registry()
    specialist_model = FakeLCModel([
        make_stop_response("analysis complete"),
        make_stop_response("pass"),
    ])
    from tests.unit.helpers import make_model_registry
    specialist = AgentBasedSpecialist(
        name="data_engineer", role="data_engineer",
        llm_client=client, tool_registry=registry,
        model_registry=make_model_registry(specialist_model),
    )

    from packages.agent.orchestrator import SpecialistTask
    task = SpecialistTask(
        task_id=uuid4(),
        instruction="analyze demand",
        context_payload={},
        allowed_tools=["nl_query", "forecast"],
    )

    ctx = ToolContext(
        session_id=uuid4(),
        agent_step_id=task.task_id,
        specialist_role="data_engineer",
        actor="test",
        correlation_id=uuid4(),
    )

    result = await specialist.run(task, ctx)
    assert result.status == "completed"
    assert isinstance(result.output, dict)
