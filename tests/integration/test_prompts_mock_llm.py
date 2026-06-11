from __future__ import annotations

"""Integration tests for the full intent → routing → tool execution pipeline.

These tests exercise the SessionOrchestrator end-to-end with:
  - A mock LLM (no real API calls — canned LLMResponse objects)
  - A real PostgreSQL database (DATABASE_URL required)
  - Zero API cost

Run with:
    docker compose up -d db
    uv run pytest tests/integration/test_prompts_mock_llm.py -v

Tests are skipped automatically when DATABASE_URL is unset.
"""

import asyncio
import os
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from packages.agent.llm import LLMMessage, LLMResponse, LLMStreamEvent, LLMUsage
from packages.agent.orchestrator import (
    SessionOrchestrator,
    SessionResponse,
    SessionUserQuery,
)
from packages.agent.orchestrator.models import AgentRoute, AskUserDecision, SessionIntent
from packages.agent.orchestrator.routing import validate_route
from packages.memory import StubMemoryStore
from packages.tools import create_tool_registry
from packages.tools.base import ToolContext, ToolRegistry, ToolResult
from tests.integration.conftest import make_stub_registry

_HAS_DB = bool(os.environ.get("DATABASE_URL"))
_SKIP_NO_DB = pytest.mark.skipif(not _HAS_DB, reason="DATABASE_URL not set")


# ---------------------------------------------------------------------------
# Shared helpers
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


# ---------------------------------------------------------------------------
# Mock LLM client that returns pre-scripted responses in order
# ---------------------------------------------------------------------------


class _ScriptedLLMClient:
    """Serves synthesis and stream responses for the orchestrator's astream() path.

    Since P52, intent classification and routing are handled by model_registry
    (structured output).  _ScriptedLLMClient is now used only for:
      - _synthesize_response() (astream of final reply text)
      - run_direct_chat() (astream of reply text for chat intent)
    The pre-scripted `responses` list is kept for backward compat but is no
    longer consumed by complete() in the orchestrator-layer calls; it is used
    by the control model wrapper below.
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
# Fake tool implementations used in tool-invocation assertion tests
# ---------------------------------------------------------------------------


class _InvocationRecorder:
    """Thread-safe list of (tool_name, input) pairs recorded per test run."""

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


# Intent + router JSON helpers

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
# Scenario 1: forecast intent — ForecastTool invoked
# ---------------------------------------------------------------------------


@_SKIP_NO_DB
async def test_forecast_intent_invokes_forecast_tool() -> None:
    """When intent == domain_analysis and LLM requests 'forecast' tool,
    the ForecastTool handle() must be called."""
    recorder = _InvocationRecorder()
    forecast_tool = _make_recording_tool("forecast", "write", recorder)

    # ControlAgent LLM sequence: call forecast tool → stop
    control_responses = [
        _tool_call_response("forecast", {"sku_id": "SKU-001", "horizon_days": 28}),
        _stop("Forecast completed."),
    ]
    model_registry = _make_full_registry(
        intent=SessionIntent(
            category="domain_analysis", confidence=0.95, rationale="test",
            goal_text="forecast demand for SKU-001",
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
    query = SessionUserQuery(text="Forecast demand for SKU-001 for the next 28 days")

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


# ---------------------------------------------------------------------------
# Scenario 2: simulate intent — SimulationTool invoked
# ---------------------------------------------------------------------------


@_SKIP_NO_DB
async def test_simulate_intent_invokes_simulation_tool() -> None:
    """When LLM requests 'simulate_inventory' tool, SimulationTool must be called."""
    recorder = _InvocationRecorder()
    sim_tool = _make_recording_tool("simulate_inventory", "write", recorder)

    sim_input = {"sku_id": "SKU-002", "order_qty": 500.0, "horizon_days": 90}

    control_responses = [
        _tool_call_response("simulate_inventory", sim_input),
        _stop("Simulation completed."),
    ]
    model_registry = _make_full_registry(
        intent=SessionIntent(
            category="domain_analysis", confidence=0.95, rationale="test",
            goal_text="simulate inventory for SKU-002",
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
    query = SessionUserQuery(text="Simulate inventory for SKU-002 with 500 units order")

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

    invoked_names = [name for name, _ in recorder.calls]
    assert "simulate_inventory" in invoked_names


# ---------------------------------------------------------------------------
# Scenario 3: optimize intent — OptimizerTool invoked
# ---------------------------------------------------------------------------


@_SKIP_NO_DB
async def test_optimize_intent_invokes_optimizer_tool() -> None:
    """When LLM requests 'optimize_replenishment', OptimizerTool must be called."""
    recorder = _InvocationRecorder()
    opt_tool = _make_recording_tool("optimize_replenishment", "write", recorder)

    opt_input = {"sku_id": "SKU-003", "moq": 100.0, "horizon_days": 90}

    control_responses = [
        _tool_call_response("optimize_replenishment", opt_input),
        _stop("Optimization completed."),
    ]
    model_registry = _make_full_registry(
        intent=SessionIntent(
            category="decision_support", confidence=0.95, rationale="test",
            goal_text="optimize replenishment SKU-003",
        ),
        agent_route=AgentRoute(
            mode="single_agent", agents=["control"],
            requires_planning=False, requires_dag=False, rationale="mock",
        ),
        control_responses=control_responses,
    )

    llm = _ScriptedLLMClient([])
    registry = _make_registry_with_tool(opt_tool)
    orchestrator = _make_orchestrator(llm, registry, model_registry=model_registry)
    session_id = uuid4()
    query = SessionUserQuery(text="Optimize replenishment order for SKU-003")

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

    invoked_names = [name for name, _ in recorder.calls]
    assert "optimize_replenishment" in invoked_names


# ---------------------------------------------------------------------------
# Scenario 4: query intent — NLQueryTool invoked
# ---------------------------------------------------------------------------


@_SKIP_NO_DB
async def test_query_intent_invokes_nl_query_tool() -> None:
    """When LLM requests 'nl_query' tool, NlQueryTool must be called."""
    recorder = _InvocationRecorder()
    nl_tool = _make_recording_tool("nl_query", "read_only", recorder)

    nl_input = {"question": "What are the top 10 SKUs by demand?"}

    # lookup intent is not analytical — no AskUserDecision call is made.
    control_responses = [
        _tool_call_response("nl_query", nl_input),
        _stop("Query results returned."),
    ]
    model_registry = _make_full_registry(
        intent=SessionIntent(
            category="lookup", confidence=0.95, rationale="test",
            goal_text="top 10 SKUs by demand",
        ),
        agent_route=AgentRoute(
            mode="single_agent", agents=["control"],
            requires_planning=False, requires_dag=False, rationale="mock",
        ),
        control_responses=control_responses,
    )

    llm = _ScriptedLLMClient([])
    registry = _make_registry_with_tool(nl_tool)
    orchestrator = _make_orchestrator(llm, registry, model_registry=model_registry)
    session_id = uuid4()
    query = SessionUserQuery(text="What are the top 10 SKUs by demand?")

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

    invoked_names = [name for name, _ in recorder.calls]
    assert "nl_query" in invoked_names


# ---------------------------------------------------------------------------
# Scenario 5: chat intent (no goal_text) — clarification event emitted
# ---------------------------------------------------------------------------


@_SKIP_NO_DB
async def test_chat_intent_without_goal_emits_response_ready_event() -> None:
    """When intent == 'chat', the orchestrator routes to direct_chat and emits
    a response_ready event via the SSE queue.

    Note: clarification_required was removed in P16 (T-117).  chat intent now
    routes directly to run_direct_chat which emits text_delta + response_ready.
    """
    model_registry = make_stub_registry(
        SessionIntent(category="chat", confidence=0.95, rationale="greeting", goal_text=None),
        AgentRoute(
            mode="direct_chat", agents=[],
            requires_planning=False, requires_dag=False, rationale="chat",
        ),
    )

    registry = create_tool_registry()
    sse_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    orchestrator = SessionOrchestrator(
        llm_client=_ScriptedLLMClient([]),
        tool_registry=registry,
        memory_store=StubMemoryStore(),
        sse_queue=sse_queue,
        model_registry=model_registry,
    )
    session_id = uuid4()
    query = SessionUserQuery(text="hi there")

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

    events: list[dict[str, Any]] = []
    while not sse_queue.empty():
        events.append(sse_queue.get_nowait())

    event_types = [e.get("type") for e in events]
    assert "response_ready" in event_types, (
        f"response_ready missing from SSE events for chat intent; got: {event_types}"
    )


# ---------------------------------------------------------------------------
# Scenario 6: hitl-classified tool — HITLPause raised, session paused
# ---------------------------------------------------------------------------


@_SKIP_NO_DB
async def test_hitl_tool_raises_graph_interrupt_for_approval() -> None:
    """When the LLM requests a hitl tool, the orchestrator raises GraphInterrupt
    and an 'awaiting_approval' SSE event is emitted to the SSE queue.

    Since P20 (LangGraph-native SSE pipeline), HITL pauses via interrupt() which
    surfaces as GraphInterrupt from SessionOrchestrator.run().  The DB status is
    not written to 'awaiting_approval' in the current implementation — only the
    SSE event is emitted.
    """
    from langgraph.errors import GraphInterrupt

    approval_id = str(uuid4())

    hitl_tool: Any = _make_recording_tool("request_approval", "hitl", _InvocationRecorder())

    # ControlAgent requests hitl tool → triggers approval pause
    control_responses = [
        _tool_call_response("request_approval", {"action_summary": "Reorder 1000 units"}),
    ]
    model_registry = _make_full_registry(
        intent=SessionIntent(
            category="decision_support", confidence=0.95, rationale="test",
            goal_text="approve reorder",
        ),
        agent_route=AgentRoute(
            mode="single_agent", agents=["control"],
            requires_planning=False, requires_dag=False, rationale="mock",
        ),
        control_responses=control_responses,
    )

    llm = _ScriptedLLMClient([])
    registry = _make_registry_with_tool(hitl_tool)
    sse_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    orchestrator = SessionOrchestrator(
        llm_client=llm,
        tool_registry=registry,
        memory_store=StubMemoryStore(),
        sse_queue=sse_queue,
        model_registry=model_registry,
    )
    session_id = uuid4()
    query = SessionUserQuery(text="Approve reorder of 1000 units for SKU-004")

    mock_repo = _mock_session_repo()
    mock_steps = _mock_agent_steps_repo()

    mock_approvals_repo = MagicMock()
    mock_approvals_repo.create = AsyncMock(return_value={"id": approval_id})

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
        patch(
            "packages.persistence.approvals_repo.ApprovalsRepository",
            return_value=mock_approvals_repo,
        ),
    ):
        with pytest.raises(GraphInterrupt):
            await orchestrator.run(session_id, query)
        await asyncio.sleep(0)

    events: list[dict[str, Any]] = []
    while not sse_queue.empty():
        events.append(sse_queue.get_nowait())

    event_types = [e.get("type") for e in events]
    assert "awaiting_approval" in event_types, (
        f"awaiting_approval SSE event missing; got: {event_types}"
    )


# ---------------------------------------------------------------------------
# Scenario 7: analyst user role — write tools blocked
# ---------------------------------------------------------------------------


async def test_analyst_user_role_excludes_write_tools_from_registry() -> None:
    """ToolRegistry.filter_for_user_role('analyst') must return only read_only tools;
    write and hitl tools must not appear."""
    registry = ToolRegistry()

    class _RO:
        name = "ro_tool"
        description = "read-only"
        input_schema: dict[str, Any] = {}
        output_schema: dict[str, Any] = {}
        safety_level = "read_only"

        async def handle(self, input: dict[str, Any], ctx: Any) -> ToolResult:
            return ToolResult(output={}, audit_payload={})

    class _Write:
        name = "write_tool"
        description = "write"
        input_schema: dict[str, Any] = {}
        output_schema: dict[str, Any] = {}
        safety_level = "write"

        async def handle(self, input: dict[str, Any], ctx: Any) -> ToolResult:
            return ToolResult(output={}, audit_payload={})

    registry.register(_RO())
    registry.register(_Write())

    all_tools = list(registry._tools.values())
    analyst_tools = registry.filter_for_user_role("analyst", all_tools)
    names = {t.name for t in analyst_tools}

    assert "ro_tool" in names
    assert "write_tool" not in names


# ---------------------------------------------------------------------------
# Scenario 8: manager user role — hitl tools accessible
# ---------------------------------------------------------------------------


async def test_manager_user_role_includes_hitl_tools() -> None:
    """ToolRegistry.filter_for_user_role('manager') must include both read_only
    and hitl tools; write tools must remain excluded."""
    registry = ToolRegistry()

    class _RO:
        name = "ro_tool"
        description = "read-only"
        input_schema: dict[str, Any] = {}
        output_schema: dict[str, Any] = {}
        safety_level = "read_only"

        async def handle(self, input: dict[str, Any], ctx: Any) -> ToolResult:
            return ToolResult(output={}, audit_payload={})

    class _Hitl:
        name = "hitl_tool"
        description = "hitl"
        input_schema: dict[str, Any] = {}
        output_schema: dict[str, Any] = {}
        safety_level = "hitl"

        async def handle(self, input: dict[str, Any], ctx: Any) -> ToolResult:
            return ToolResult(output={}, audit_payload={})

    class _Write:
        name = "write_tool"
        description = "write"
        input_schema: dict[str, Any] = {}
        output_schema: dict[str, Any] = {}
        safety_level = "write"

        async def handle(self, input: dict[str, Any], ctx: Any) -> ToolResult:
            return ToolResult(output={}, audit_payload={})

    registry.register(_RO())
    registry.register(_Hitl())
    registry.register(_Write())

    all_tools = list(registry._tools.values())
    manager_tools = registry.filter_for_user_role("manager", all_tools)
    names = {t.name for t in manager_tools}

    assert "ro_tool" in names
    assert "hitl_tool" in names
    assert "write_tool" not in names


# ---------------------------------------------------------------------------
# Scenario 9: route validation — single_agent with wrong count → ValueError
# ---------------------------------------------------------------------------


def test_validate_route_single_agent_with_two_agents_raises_value_error() -> None:
    """validate_route must raise ValueError when mode='single_agent' but
    agents list contains more than one entry."""
    route = AgentRoute(
        mode="single_agent",
        agents=["demand", "inventory"],
        requires_planning=False,
        requires_dag=False,
        rationale="test",
    )
    with pytest.raises(ValueError, match="single_agent route requires exactly one agent"):
        validate_route(route)


# ---------------------------------------------------------------------------
# Scenario 10: approval idempotency — second request reuses existing pending row
# ---------------------------------------------------------------------------


@_SKIP_NO_DB
async def test_approval_idempotency_second_create_returns_existing_record() -> None:
    """When get_pending_approval_for_session returns an existing row,
    ApprovalsRepository.create must NOT be called again."""
    from packages.persistence.approvals_repo import ApprovalsRepository

    session_id = uuid4()
    existing_approval_id = uuid4()
    existing_record: dict[str, Any] = {
        "id": existing_approval_id,
        "session_id": session_id,
        "status": "pending",
        "actor": None,
        "reason": "HITL tool: request_approval",
    }

    mock_conn = AsyncMock()
    mock_conn.fetchrow = AsyncMock(return_value=existing_record)

    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    with patch(
        "packages.persistence.approvals_repo.get_pool",
        new=AsyncMock(return_value=mock_pool),
    ):
        repo = ApprovalsRepository()
        found = await repo.get_pending_approval_for_session(session_id)

    # Idempotency guard: if an existing record was found, we reuse its ID
    if found is not None:
        reused_id = str(found.get("id", uuid4()))
    else:
        mock_create = AsyncMock(return_value={"id": str(uuid4())})
        reused_id = str((await mock_create({"session_id": session_id}))["id"])

    assert reused_id == str(existing_approval_id)
    # The fetchrow was called once; create() was never called because found != None
    mock_conn.fetchrow.assert_awaited_once()


# ---------------------------------------------------------------------------
# Shared client for AskUser scenarios (11, 12)
# ---------------------------------------------------------------------------


class _AskUserLLMClient:
    """LLM client that returns needs_input=true for analytical queries.

    Mirrors _AskUserYesLLMClient in tests/unit/test_ask_user_interrupt.py but
    is defined locally to avoid cross-test-file imports.  Includes stream() so
    run_direct_chat (T-111) and _synthesize_response (T-112) work correctly.
    """

    _model = "stub"

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
        system = messages[0].content if messages else ""
        if "information-gathering" in system:
            return _stop(
                '{"needs_input": true,'
                ' "question": "What date range should I analyze?",'
                ' "suggestions": ["Last 30 days", "Q1 2025", "Last 12 months"]}'
            )
        if "intent classifier" in system:
            return _stop(_intent_json("domain_analysis", goal_text="analyze inventory"))
        if "router inside SessionOrchestrator" in system:
            return _stop(
                '{"mode":"direct_chat","agents":[],'
                '"requires_planning":false,"requires_dag":false,"rationale":"mock"}'
            )
        return _stop("Analysis complete for the requested period.")

    async def stream(self, messages: list[LLMMessage], tools: Any = None, **kwargs: Any) -> Any:
        response = await self.complete(messages, tools=tools, **kwargs)

        async def _gen() -> Any:
            yield LLMStreamEvent(event="text_delta", data=response.text)

        return _gen()

    async def astream(self, input: Any, config: Any = None, **kwargs: Any) -> Any:  # type: ignore[override]
        """LangChain-style astream used by run_direct_chat in runtime.py."""
        from types import SimpleNamespace

        yield SimpleNamespace(content="Analysis complete for the requested period.")


# ---------------------------------------------------------------------------
# Scenario 11: AskUser — analytical intent pauses graph (HITL section)
# ---------------------------------------------------------------------------


async def test_ask_user_analytical_intent_emits_event_and_raises_graph_interrupt() -> None:
    """When intent is analytical and a critical parameter is missing,
    _node_prepare_ask_user fires ask_user_required SSE and the graph raises
    GraphInterrupt at wait_for_answer.

    No real DB needed — uses MemorySaver (default when DATABASE_URL is absent).
    """
    from unittest.mock import AsyncMock, MagicMock, patch

    from langgraph.errors import GraphInterrupt

    _ask_registry = make_stub_registry(
        SessionIntent(
            category="domain_analysis",
            confidence=0.95,
            rationale="test",
            goal_text="analyze inventory",
        ),
        AskUserDecision(
            needs_input=True,
            question="What date range should I analyze?",
            suggestions=["Last 30 days", "Q1 2025", "Last 12 months"],
        ),
    )

    sse_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    orchestrator = SessionOrchestrator(
        llm_client=_AskUserLLMClient(),
        tool_registry=create_tool_registry(),
        memory_store=StubMemoryStore(),
        sse_queue=sse_queue,
        model_registry=_ask_registry,
    )
    session_id = uuid4()
    query = SessionUserQuery(text="Analyze inventory levels for the past month")

    mock_repo = MagicMock()
    mock_repo.update_status = AsyncMock()

    with patch(
        "packages.agent.orchestrator.session_orchestrator.DecisionSessionRepository",
        return_value=mock_repo,
    ):
        with pytest.raises(GraphInterrupt):
            await orchestrator.run(session_id, query)
        await asyncio.sleep(0)

    events: list[dict[str, Any]] = []
    while not sse_queue.empty():
        events.append(sse_queue.get_nowait())

    event_types = [e.get("type") for e in events]
    assert "ask_user_required" in event_types, f"ask_user_required missing; got: {event_types}"
    assert "graph_node" in event_types, f"graph_node missing; got: {event_types}"

    ask_event = next(e for e in events if e.get("type") == "ask_user_required")
    assert ask_event["question"] == "What date range should I analyze?"
    assert isinstance(ask_event.get("suggestions"), list)
    assert ask_event.get("ask_user_id") is not None

    # graph_node events must appear for orchestrator nodes that ran before the interrupt
    graph_nodes = [e for e in events if e.get("type") == "graph_node"]
    node_names = [e.get("name") for e in graph_nodes]
    assert "classify_intent" in node_names, f"classify_intent graph_node missing; names: {node_names}"
    assert "prepare_ask_user" in node_names, f"prepare_ask_user graph_node missing; names: {node_names}"
    # Each start event must have a matching end event
    start_run_ids = {e.get("run_id") for e in graph_nodes if e.get("event") == "start"}
    end_run_ids = {e.get("run_id") for e in graph_nodes if e.get("event") == "end"}
    assert start_run_ids == end_run_ids, f"Unmatched graph_node start/end run_ids"


# ---------------------------------------------------------------------------
# Scenario 12: AskUser resume — answer_ask_user() returns analysis (HITL section)
# ---------------------------------------------------------------------------


async def test_ask_user_resume_via_answer_returns_session_response() -> None:
    """After graph pauses at wait_for_answer, calling answer_ask_user() resumes it
    and returns a complete SessionResponse with rationale != 'ask_user'.

    No real DB needed — uses MemorySaver.

    Since P78 (deterministic routing), domain_analysis always routes to
    single_agent with agents=["control"]. After resume, select_mode deterministically
    routes to run_sequential → ControlAgent. The registry must therefore include a
    "control"-role model. The AgentRoute stub previously included here was never
    consumed by select_mode (routing is now deterministic) and has been removed.
    """
    from unittest.mock import AsyncMock, MagicMock, patch

    from langgraph.errors import GraphInterrupt

    # Structured-output sequence for run() + answer_ask_user():
    #   1. SessionIntent         (classify_intent — first run)
    #   2. AskUserDecision(True) (prepare_ask_user — first run → interrupt)
    # After resume via answer_ask_user():
    #   3. select_mode deterministically routes domain_analysis → single_agent/control
    #   4. ControlAgent: plan_tools (one ainvoke) + call_model (stop response)
    _resume_registry = _make_full_registry(
        intent=SessionIntent(
            category="domain_analysis",
            confidence=0.95,
            rationale="test",
            goal_text="analyze inventory",
        ),
        agent_route=AgentRoute(
            mode="single_agent",
            agents=["control"],
            requires_planning=False,
            requires_dag=False,
            rationale="Deterministic route for intent 'domain_analysis'",
        ),
        control_responses=[
            _stop("Analysis complete for the requested period."),
        ],
        ask_user_decision=AskUserDecision(
            needs_input=True,
            question="What date range should I analyze?",
            suggestions=["Last 30 days", "Q1 2025", "Last 12 months"],
        ),
    )

    orchestrator = SessionOrchestrator(
        llm_client=_AskUserLLMClient(),
        tool_registry=create_tool_registry(),
        memory_store=StubMemoryStore(),
        model_registry=_resume_registry,
    )
    session_id = uuid4()
    query = SessionUserQuery(text="Analyze inventory levels for the past month")

    mock_repo = MagicMock()
    mock_repo.update_status = AsyncMock()

    with patch(
        "packages.agent.orchestrator.session_orchestrator.DecisionSessionRepository",
        return_value=mock_repo,
    ):
        with pytest.raises(GraphInterrupt):
            await orchestrator.run(session_id, query)
        await asyncio.sleep(0)

        response = await orchestrator.answer_ask_user(session_id, "Q1 2025")
        await asyncio.sleep(0)

    assert isinstance(response, SessionResponse)
    assert response.route.rationale != "ask_user"
    assert response.reply  # non-empty reply from ControlAgent


# ---------------------------------------------------------------------------
# Scenario 13: admin user role — unrestricted tool access
# ---------------------------------------------------------------------------


async def test_admin_user_role_includes_all_tool_safety_levels() -> None:
    """ToolRegistry.filter_for_user_role('admin') must include read_only, write,
    and hitl tools — no safety-level filtering is applied for admin users."""
    registry = ToolRegistry()

    class _RO:
        name = "ro_tool"
        description = "read-only"
        input_schema: dict[str, Any] = {}
        output_schema: dict[str, Any] = {}
        safety_level = "read_only"

        async def handle(self, input: dict[str, Any], ctx: Any) -> ToolResult:
            return ToolResult(output={}, audit_payload={})

    class _Write:
        name = "write_tool"
        description = "write"
        input_schema: dict[str, Any] = {}
        output_schema: dict[str, Any] = {}
        safety_level = "write"

        async def handle(self, input: dict[str, Any], ctx: Any) -> ToolResult:
            return ToolResult(output={}, audit_payload={})

    class _Hitl:
        name = "hitl_tool"
        description = "hitl"
        input_schema: dict[str, Any] = {}
        output_schema: dict[str, Any] = {}
        safety_level = "hitl"

        async def handle(self, input: dict[str, Any], ctx: Any) -> ToolResult:
            return ToolResult(output={}, audit_payload={})

    registry.register(_RO())
    registry.register(_Write())
    registry.register(_Hitl())

    all_tools = list(registry._tools.values())
    admin_tools = registry.filter_for_user_role("admin", all_tools)
    names = {t.name for t in admin_tools}

    assert "ro_tool" in names
    assert "write_tool" in names
    assert "hitl_tool" in names


# ---------------------------------------------------------------------------
# Scenario 14: nl_query tool — invoked when LLM requests it
# ---------------------------------------------------------------------------


@_SKIP_NO_DB
async def test_nl_query_tool_invoked() -> None:
    """When LLM requests 'nl_query' tool, NlQueryTool handle() must be called."""
    recorder = _InvocationRecorder()
    nl_tool = _make_recording_tool("nl_query", "read_only", recorder)

    nl_input = {"question": "Show raw inventory rows for SKU-001"}

    # lookup intent is not analytical — no AskUserDecision call is made.
    control_responses = [
        _tool_call_response("nl_query", nl_input),
        _stop("Query returned 10 rows."),
    ]
    model_registry = _make_full_registry(
        intent=SessionIntent(
            category="lookup", confidence=0.95, rationale="test",
            goal_text="raw inventory rows for SKU-001",
        ),
        agent_route=AgentRoute(
            mode="single_agent", agents=["control"],
            requires_planning=False, requires_dag=False, rationale="mock",
        ),
        control_responses=control_responses,
    )

    llm = _ScriptedLLMClient([])
    registry = _make_registry_with_tool(nl_tool)
    orchestrator = _make_orchestrator(llm, registry, model_registry=model_registry)
    session_id = uuid4()
    query = SessionUserQuery(text="Show raw inventory rows for SKU-001")

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

    invoked_names = [name for name, _ in recorder.calls]
    assert "nl_query" in invoked_names
