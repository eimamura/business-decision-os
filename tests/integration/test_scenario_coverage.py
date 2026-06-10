from __future__ import annotations

"""Integration tests for tool scenarios not yet covered by test_prompts_mock_llm.py.

Covers Scenarios A–E from T-158:
  A  catalog intent → data_catalog_search tool
  B  schema intent  → table_schema_reader tool
  C  data quality   → data_quality_checker tool
  D  multi-SKU forecast → forecast tool (broad params)
  E  scenario comparison → simulate_inventory tool (called at least once)

All tests use a scripted mock LLM and patch away DB side-effects.
Tests marked @_SKIP_NO_DB require a real DATABASE_URL; the rest run anywhere.
"""

import asyncio
import os
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from packages.agent.llm import LLMMessage, LLMResponse, LLMStreamEvent, LLMUsage
from packages.agent.orchestrator import (
    SessionOrchestrator,
    SessionResponse,
    SessionUserQuery,
)
from packages.agent.orchestrator.models import AgentRoute, SessionIntent
from packages.memory import StubMemoryStore
from packages.tools.base import ToolRegistry, ToolResult

_HAS_DB = bool(os.environ.get("DATABASE_URL"))
_SKIP_NO_DB = pytest.mark.skipif(not _HAS_DB, reason="DATABASE_URL not set")


# ---------------------------------------------------------------------------
# Shared helpers (copied locally — do NOT import from test_prompts_mock_llm.py)
# ---------------------------------------------------------------------------


def _usage() -> LLMUsage:
    return LLMUsage(
        input_tokens=10,
        output_tokens=5,
        cache_read_tokens=0,
        cache_write_tokens=0,
        total_cost_usd=Decimal("0"),
    )


def _stop(text: str = "Done.") -> LLMResponse:
    return LLMResponse(
        text=text,
        tool_calls=[],
        finish_reason="stop",
        usage=_usage(),
        model="mock-model",
        request_id=str(uuid4()),
        latency_ms=0,
    )


def _tool_call_response(tool_name: str, tool_input: dict[str, Any]) -> LLMResponse:
    return LLMResponse(
        text="",
        tool_calls=[{"id": str(uuid4()), "name": tool_name, "input": tool_input}],
        finish_reason="tool_use",
        usage=_usage(),
        model="mock-model",
        request_id=str(uuid4()),
        latency_ms=0,
    )


def _intent_json(
    category: str,
    confidence: float = 0.95,
    goal_text: str | None = "goal",
) -> str:
    gt = f'"{goal_text}"' if goal_text else "null"
    return (
        f'{{"category":"{category}","confidence":{confidence},'
        f'"rationale":"test","goal_text":{gt}}}'
    )


def _route_json(
    mode: str,
    agents: list[str] | None = None,
    requires_planning: bool = False,
    requires_dag: bool = False,
) -> str:
    agents_part = str(agents or []).replace("'", '"')
    return (
        f'{{"mode":"{mode}","agents":{agents_part},'
        f'"requires_planning":{str(requires_planning).lower()},'
        f'"requires_dag":{str(requires_dag).lower()},'
        '"rationale":"mock"}'
    )


# ---------------------------------------------------------------------------
# Mock LLM client — returns scripted responses in queue order
# ---------------------------------------------------------------------------


class _ScriptedLLMClient:
    """Serves synthesis stream responses for the orchestrator's astream() path.

    Since P52, intent classification and routing are handled by model_registry
    (structured output).  _ScriptedLLMClient is now used only for astream() calls
    from _synthesize_response() and run_direct_chat().
    """

    def __init__(self, responses: list[LLMResponse]) -> None:
        self._queue = list(responses)
        self._model = "mock-model"

    async def complete(
        self,
        messages: list[LLMMessage],
        tools: Any = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        prompt_cache: bool = True,
        agent_step_id: Any = None,
        specialist_role: Any = None,
    ) -> LLMResponse:
        if self._queue:
            return self._queue.pop(0)
        return _stop("fallback")

    async def stream(
        self,
        messages: list[LLMMessage],
        tools: Any = None,
        **kwargs: Any,
    ) -> Any:
        response = await self.complete(messages, tools=tools, **kwargs)

        async def _gen() -> Any:
            yield LLMStreamEvent(event="text_delta", data=response.text)

        return _gen()

    async def astream(self, input: Any, config: Any = None, **kwargs: Any) -> Any:
        """LangChain-style astream used by _synthesize_response and run_direct_chat."""
        from types import SimpleNamespace

        yield SimpleNamespace(content="Done.")


# ---------------------------------------------------------------------------
# _ControlFakeModel — LangChain-compatible model for the ControlAgent's _lc_model.
#
# AgentRuntime._call_model_node uses:
#   ai_msg = await bound_model.ainvoke(lc_msgs)
#   tool_calls = [{"name": tc["name"], "id": tc["id"], "input": tc.get("args", {})}
#                 for tc in (ai_msg.tool_calls or [])]
#
# Responses are popped from a queue in order; each _LLMResponseAdapter adapts
# the LLMResponse format to the LangChain AIMessage interface expected by runtime.py.
# ---------------------------------------------------------------------------


class _LLMResponseAdapter:
    """Adapts an LLMResponse to the LangChain AIMessage interface used by AgentRuntime."""

    def __init__(self, llm_response: LLMResponse) -> None:
        self.content = llm_response.text
        # AgentRuntime expects tool_calls as {"name", "id", "args"} (LangChain format)
        self.tool_calls = [
            {"name": tc["name"], "id": tc["id"], "args": tc.get("input", {})}
            for tc in (llm_response.tool_calls or [])
        ]
        self.usage_metadata: dict[str, Any] = {}


class _ControlFakeModel:
    """LangChain-compatible fake model for the ControlAgent role.

    Pops responses from a queue via ainvoke().  bind_tools() returns self.
    """

    model = "fake-control-model"

    def __init__(self, responses: list[LLMResponse]) -> None:
        self._queue = list(responses)

    def bind_tools(self, tools: Any) -> "_ControlFakeModel":
        return self

    def with_structured_output(self, schema: Any) -> Any:  # for groundedness verifier
        return self

    async def ainvoke(self, messages: Any, **kwargs: Any) -> Any:
        if self._queue:
            return _LLMResponseAdapter(self._queue.pop(0))
        return _LLMResponseAdapter(_stop("fallback"))


# ---------------------------------------------------------------------------
# Invocation recorder + recording-tool factory
# ---------------------------------------------------------------------------


class _InvocationRecorder:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def record(self, tool_name: str, tool_input: dict[str, Any]) -> None:
        self.calls.append((tool_name, tool_input))


def _make_recording_tool(
    name: str,
    safety_level: str,
    recorder: _InvocationRecorder,
) -> Any:
    class _RecordingTool:
        async def handle(self, input: dict[str, Any], ctx: Any) -> ToolResult:
            recorder.record(self.name, input)
            return ToolResult(
                output={"tool_name": self.name, "recorded": True},
                audit_payload={"tool_name": self.name},
            )

    tool = _RecordingTool()
    tool.name = name  # type: ignore[attr-defined]
    tool.description = f"Mock {name}"  # type: ignore[attr-defined]
    tool.input_schema = {"type": "object", "properties": {}}  # type: ignore[attr-defined]
    tool.output_schema = {"type": "object", "properties": {}}  # type: ignore[attr-defined]
    tool.safety_level = safety_level  # type: ignore[attr-defined]
    return tool


def _make_registry_with_tool(tool: Any) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(tool)
    return registry


# ---------------------------------------------------------------------------
# Orchestrator factory — patches away all DB side-effects
# ---------------------------------------------------------------------------


def _make_orchestrator(
    llm_client: Any,
    tool_registry: Any,
    model_registry: Any = None,
) -> SessionOrchestrator:
    return SessionOrchestrator(
        llm_client=llm_client,
        tool_registry=tool_registry,
        memory_store=StubMemoryStore(),
        model_registry=model_registry,
    )


_PLAN_TOOLS_INTENTS = frozenset({"domain_analysis", "cross_domain_analysis", "decision_support"})


def _make_full_registry(
    intent: Any,
    agent_route: Any,
    control_responses: list[LLMResponse],
    ask_user_decision: Any = None,
) -> Any:
    """Build a _MultiRoleModelRegistry with separate orchestrator and control models.

    The orchestrator model serves structured-output calls (SessionIntent,
    AskUserDecision, AgentRoute) via type-aware matching.  The control model
    serves the ControlAgent's LangChain ainvoke() calls (tool calls + stops).

    For analytical intents (domain_analysis, cross_domain_analysis, decision_support),
    AgentRuntime._plan_tools_node() calls _lc_model.ainvoke() once before the main
    tool-call loop.  A blank stop response is prepended automatically so the plan node
    fails gracefully and the rest of the queue is consumed correctly.

    Args:
        intent: SessionIntent instance for classify_intent node.
        agent_route: AgentRoute instance for select_mode node.
        control_responses: LLMResponse list for ControlAgent tool execution.
        ask_user_decision: AskUserDecision for prepare_ask_user (analytical intents);
            defaults to AskUserDecision(needs_input=False) when not provided.
    """
    from packages.agent.orchestrator.models import AskUserDecision
    from tests.integration.conftest import _MultiRoleModelRegistry, _StructuredOutputFakeModel

    if ask_user_decision is None:
        ask_user_decision = AskUserDecision(needs_input=False, question=None, suggestions=[])

    orchestrator_model = _StructuredOutputFakeModel([intent, ask_user_decision, agent_route])

    # Prepend an empty plan response for analytical intents so that
    # AgentRuntime._plan_tools_node() consumes one call without disrupting the queue.
    all_control_responses = list(control_responses)
    if intent.category in _PLAN_TOOLS_INTENTS:
        all_control_responses = [_stop("")] + all_control_responses

    control_model = _ControlFakeModel(all_control_responses)
    return _MultiRoleModelRegistry({"orchestrator": orchestrator_model, "control": control_model})


def _mock_session_repo() -> Any:
    repo = MagicMock()
    repo.update_status = AsyncMock()
    return repo


def _mock_agent_steps_repo() -> Any:
    repo = MagicMock()
    repo.create = AsyncMock()
    repo.update_ended = AsyncMock()
    return repo


# ---------------------------------------------------------------------------
# Scenario A: catalog intent → data_catalog_search tool invoked
# ---------------------------------------------------------------------------


@_SKIP_NO_DB
async def test_catalog_intent_invokes_data_catalog_search_tool() -> None:
    """When intent is 'lookup' routed to control and LLM requests
    'data_catalog_search', the DataCatalogSearchTool handle() must be called.

    Prompt: "利用可能なデータテーブル一覧をカタログから検索して"
    """
    recorder = _InvocationRecorder()
    catalog_tool = _make_recording_tool("data_catalog_search", "read_only", recorder)

    # lookup is not analytical — no AskUserDecision call in prepare_ask_user.
    control_responses = [
        _tool_call_response("data_catalog_search", {"keyword": ""}),
        _stop("Catalog search returned available tables."),
    ]
    model_registry = _make_full_registry(
        intent=SessionIntent(
            category="lookup", confidence=0.95, rationale="test",
            goal_text="list available data tables from catalog",
        ),
        agent_route=AgentRoute(
            mode="single_agent", agents=["control"],
            requires_planning=False, requires_dag=False, rationale="mock",
        ),
        control_responses=control_responses,
    )

    llm = _ScriptedLLMClient([])
    registry = _make_registry_with_tool(catalog_tool)
    orchestrator = _make_orchestrator(llm, registry, model_registry=model_registry)
    session_id = uuid4()
    query = SessionUserQuery(text="利用可能なデータテーブル一覧をカタログから検索して")

    mock_repo = _mock_session_repo()
    mock_steps = _mock_agent_steps_repo()

    with (
        patch(
            "packages.agent.orchestrator.session_orchestrator.DecisionSessionRepository",
            return_value=mock_repo,
        ),
        patch(
            "packages.persistence.agent_steps_repo.AgentStepsRepository",
            return_value=mock_steps,
        ),
        patch("packages.persistence.agent_steps_repo.get_pool", new=AsyncMock()),
    ):
        response = await orchestrator.run(session_id, query)
        await asyncio.sleep(0)

    assert recorder.calls, "DataCatalogSearchTool was not invoked"
    invoked_names = [name for name, _ in recorder.calls]
    assert "data_catalog_search" in invoked_names


# ---------------------------------------------------------------------------
# Scenario B: schema intent → table_schema_reader tool invoked
# ---------------------------------------------------------------------------


@_SKIP_NO_DB
async def test_schema_intent_invokes_table_schema_reader_tool() -> None:
    """When intent is 'lookup' routed to control and LLM requests
    'table_schema_reader', the TableSchemaReaderTool handle() must be called.

    Prompt: "inventoryテーブルのスキーマを確認して"
    """
    recorder = _InvocationRecorder()
    schema_tool = _make_recording_tool("table_schema_reader", "read_only", recorder)

    control_responses = [
        _tool_call_response("table_schema_reader", {"table_name": "inventory_items"}),
        _stop("Inventory table has 12 columns."),
    ]
    model_registry = _make_full_registry(
        intent=SessionIntent(
            category="lookup", confidence=0.95, rationale="test",
            goal_text="check schema of inventory table",
        ),
        agent_route=AgentRoute(
            mode="single_agent", agents=["control"],
            requires_planning=False, requires_dag=False, rationale="mock",
        ),
        control_responses=control_responses,
    )

    llm = _ScriptedLLMClient([])
    registry = _make_registry_with_tool(schema_tool)
    orchestrator = _make_orchestrator(llm, registry, model_registry=model_registry)
    session_id = uuid4()
    query = SessionUserQuery(text="inventoryテーブルのスキーマを確認して")

    mock_repo = _mock_session_repo()
    mock_steps = _mock_agent_steps_repo()

    with (
        patch(
            "packages.agent.orchestrator.session_orchestrator.DecisionSessionRepository",
            return_value=mock_repo,
        ),
        patch(
            "packages.persistence.agent_steps_repo.AgentStepsRepository",
            return_value=mock_steps,
        ),
        patch("packages.persistence.agent_steps_repo.get_pool", new=AsyncMock()),
    ):
        response = await orchestrator.run(session_id, query)
        await asyncio.sleep(0)

    assert recorder.calls, "TableSchemaReaderTool was not invoked"
    invoked_names = [name for name, _ in recorder.calls]
    assert "table_schema_reader" in invoked_names


# ---------------------------------------------------------------------------
# Scenario C: data quality intent → data_quality_checker tool invoked
# ---------------------------------------------------------------------------


@_SKIP_NO_DB
async def test_data_quality_intent_invokes_data_quality_checker_tool() -> None:
    """When intent is 'lookup' routed to control and LLM requests
    'data_quality_checker', the DataQualityCheckerTool handle() must be called.

    Prompt: "inventoryテーブルのデータ品質をチェックして問題があれば報告して"
    """
    recorder = _InvocationRecorder()
    quality_tool = _make_recording_tool("data_quality_checker", "read_only", recorder)

    control_responses = [
        _tool_call_response("data_quality_checker", {"table_name": "inventory_items"}),
        _stop("Data quality check completed; no critical issues found."),
    ]
    model_registry = _make_full_registry(
        intent=SessionIntent(
            category="lookup", confidence=0.95, rationale="test",
            goal_text="check data quality of inventory table",
        ),
        agent_route=AgentRoute(
            mode="single_agent", agents=["control"],
            requires_planning=False, requires_dag=False, rationale="mock",
        ),
        control_responses=control_responses,
    )

    llm = _ScriptedLLMClient([])
    registry = _make_registry_with_tool(quality_tool)
    orchestrator = _make_orchestrator(llm, registry, model_registry=model_registry)
    session_id = uuid4()
    query = SessionUserQuery(text="inventoryテーブルのデータ品質をチェックして問題があれば報告して")

    mock_repo = _mock_session_repo()
    mock_steps = _mock_agent_steps_repo()

    with (
        patch(
            "packages.agent.orchestrator.session_orchestrator.DecisionSessionRepository",
            return_value=mock_repo,
        ),
        patch(
            "packages.persistence.agent_steps_repo.AgentStepsRepository",
            return_value=mock_steps,
        ),
        patch("packages.persistence.agent_steps_repo.get_pool", new=AsyncMock()),
    ):
        response = await orchestrator.run(session_id, query)
        await asyncio.sleep(0)

    assert recorder.calls, "DataQualityCheckerTool was not invoked"
    invoked_names = [name for name, _ in recorder.calls]
    assert "data_quality_checker" in invoked_names


# ---------------------------------------------------------------------------
# Scenario D: multi-SKU forecast → forecast tool invoked with broad params
# ---------------------------------------------------------------------------


@_SKIP_NO_DB
async def test_multi_sku_forecast_intent_invokes_forecast_tool_with_broad_params() -> None:
    """When intent is 'domain_analysis' routed to control and LLM requests
    'forecast' without a specific SKU and horizon_days=90, the ForecastTool
    handle() must be called.

    Prompt: "全SKUの今後3ヶ月の需要予測を実行してCSVで出力して"
    """
    recorder = _InvocationRecorder()
    forecast_tool = _make_recording_tool("forecast", "write", recorder)

    # No sku_id (all SKUs), horizon_days=90 (3 months)
    forecast_input: dict[str, Any] = {"horizon_days": 90}

    control_responses = [
        _tool_call_response("forecast", forecast_input),
        _stop("Multi-SKU forecast completed for 90-day horizon."),
    ]
    model_registry = _make_full_registry(
        intent=SessionIntent(
            category="domain_analysis", confidence=0.95, rationale="test",
            goal_text="forecast demand for all SKUs for 3 months",
        ),
        agent_route=AgentRoute(
            mode="single_agent", agents=["control"],
            requires_planning=False, requires_dag=False, rationale="mock",
        ),
        control_responses=control_responses,
    )

    llm = _ScriptedLLMClient([])
    registry = _make_registry_with_tool(forecast_tool)
    orchestrator = _make_orchestrator(llm, registry, model_registry=model_registry)
    session_id = uuid4()
    query = SessionUserQuery(text="全SKUの今後3ヶ月の需要予測を実行してCSVで出力して")

    mock_repo = _mock_session_repo()
    mock_steps = _mock_agent_steps_repo()

    with (
        patch(
            "packages.agent.orchestrator.session_orchestrator.DecisionSessionRepository",
            return_value=mock_repo,
        ),
        patch(
            "packages.persistence.agent_steps_repo.AgentStepsRepository",
            return_value=mock_steps,
        ),
        patch("packages.persistence.agent_steps_repo.get_pool", new=AsyncMock()),
    ):
        response = await orchestrator.run(session_id, query)
        await asyncio.sleep(0)

    assert recorder.calls, "ForecastTool was not invoked"
    invoked_names = [name for name, _ in recorder.calls]
    assert "forecast" in invoked_names

    # Verify the invocation used broad parameters (no specific SKU)
    forecast_calls = [(n, inp) for n, inp in recorder.calls if n == "forecast"]
    assert forecast_calls, "forecast tool call not found in recorder"
    _, call_input = forecast_calls[0]
    assert call_input.get("horizon_days") == 90


# ---------------------------------------------------------------------------
# Scenario E: scenario comparison → simulate_inventory called at least once
# ---------------------------------------------------------------------------


@_SKIP_NO_DB
async def test_scenario_comparison_invokes_simulate_inventory_at_least_once() -> None:
    """When intent is 'domain_analysis' routed to control and LLM requests
    'simulate_inventory' (simulating two patterns for comparison), the
    SimulationTool handle() must be called at least once.

    Prompt: "現在パラメータと最適化パラメータで2パターンのシミュレーションを比較して"
    """
    recorder = _InvocationRecorder()
    sim_tool = _make_recording_tool("simulate_inventory", "write", recorder)

    current_params: dict[str, Any] = {
        "sku_id": "SKU-001",
        "order_qty": 200.0,
        "horizon_days": 90,
    }

    # Script the control model to call simulate_inventory at least once
    control_responses = [
        _tool_call_response("simulate_inventory", current_params),
        _stop("Scenario comparison complete: current vs optimized parameters."),
    ]
    model_registry = _make_full_registry(
        intent=SessionIntent(
            category="domain_analysis", confidence=0.95, rationale="test",
            goal_text="compare current vs optimized simulation parameters",
        ),
        agent_route=AgentRoute(
            mode="single_agent", agents=["control"],
            requires_planning=False, requires_dag=False, rationale="mock",
        ),
        control_responses=control_responses,
    )

    llm = _ScriptedLLMClient([])
    registry = _make_registry_with_tool(sim_tool)
    orchestrator = _make_orchestrator(llm, registry, model_registry=model_registry)
    session_id = uuid4()
    query = SessionUserQuery(
        text="現在パラメータと最適化パラメータで2パターンのシミュレーションを比較して"
    )

    mock_repo = _mock_session_repo()
    mock_steps = _mock_agent_steps_repo()

    with (
        patch(
            "packages.agent.orchestrator.session_orchestrator.DecisionSessionRepository",
            return_value=mock_repo,
        ),
        patch(
            "packages.persistence.agent_steps_repo.AgentStepsRepository",
            return_value=mock_steps,
        ),
        patch("packages.persistence.agent_steps_repo.get_pool", new=AsyncMock()),
    ):
        response = await orchestrator.run(session_id, query)
        await asyncio.sleep(0)

    assert recorder.calls, "SimulationTool was not invoked at all"
    invoked_names = [name for name, _ in recorder.calls]
    assert "simulate_inventory" in invoked_names
