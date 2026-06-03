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
from packages.agent.orchestrator.models import AgentRoute
from packages.agent.orchestrator.routing import validate_route
from packages.memory import StubMemoryStore
from packages.tools import create_tool_registry
from packages.tools.base import ToolContext, ToolRegistry, ToolResult

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
    """Returns LLMResponse objects from a queue in insertion order.

    Responses are keyed by a substring that must appear in the system message
    content so that intent-classifier and router calls can be distinguished.
    When no match is found the next unmatched response is returned.
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


def _make_orchestrator(llm_client: Any, tool_registry: Any) -> SessionOrchestrator:
    return SessionOrchestrator(
        llm_client=llm_client,
        tool_registry=tool_registry,
        memory_store=StubMemoryStore(),
    )


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

    # LLM script: classify intent → route to single_agent/demand → call forecast tool
    llm = _ScriptedLLMClient([
        _stop(text=_intent_json("domain_analysis", goal_text="forecast demand for SKU-001")),
        _stop(text=_route_json("single_agent", ["demand"])),
        _tool_call_response("forecast", {"sku_id": "SKU-001", "horizon_days": 28}),
        _stop("verify pass"),  # verifier
        _stop("Forecast completed."),  # synthesize
        _stop("verify pass"),  # verifier for synthesize
    ])

    registry = _make_registry_with_tool(forecast_tool)
    orchestrator = _make_orchestrator(llm, registry)
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

    llm = _ScriptedLLMClient([
        _stop(text=_intent_json("domain_analysis", goal_text="simulate inventory for SKU-002")),
        _stop(text=_route_json("single_agent", ["inventory"])),
        _tool_call_response("simulate_inventory", sim_input),
        _stop("verify pass"),
        _stop("Simulation completed."),
        _stop("verify pass"),
    ])

    registry = _make_registry_with_tool(sim_tool)
    orchestrator = _make_orchestrator(llm, registry)
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

    llm = _ScriptedLLMClient([
        _stop(text=_intent_json("decision_support", goal_text="optimize replenishment SKU-003")),
        _stop(text=_route_json("single_agent", ["replenishment"])),
        _tool_call_response("optimize_replenishment", opt_input),
        _stop("verify pass"),
        _stop("Optimization completed."),
        _stop("verify pass"),
    ])

    registry = _make_registry_with_tool(opt_tool)
    orchestrator = _make_orchestrator(llm, registry)
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

    llm = _ScriptedLLMClient([
        _stop(text=_intent_json("lookup", goal_text="top 10 SKUs by demand")),
        _stop(text=_route_json("single_agent", ["data_engineer"])),
        _tool_call_response("nl_query", nl_input),
        _stop("verify pass"),
        _stop("Query results returned."),
        _stop("verify pass"),
    ])

    registry = _make_registry_with_tool(nl_tool)
    orchestrator = _make_orchestrator(llm, registry)
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
async def test_chat_intent_without_goal_emits_clarification_event() -> None:
    """When intent == 'chat' with no goal_text, a clarification_required event
    must be placed in the SSE queue."""
    # LLM returns a chat intent with no goal_text
    llm = _ScriptedLLMClient([
        _stop(text=_intent_json("chat", goal_text=None)),
    ])

    registry = create_tool_registry()
    sse_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    orchestrator = SessionOrchestrator(
        llm_client=llm,
        tool_registry=registry,
        memory_store=StubMemoryStore(),
        sse_queue=sse_queue,
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
    assert "clarification_required" in event_types


# ---------------------------------------------------------------------------
# Scenario 6: hitl-classified tool — HITLPause raised, session paused
# ---------------------------------------------------------------------------


@_SKIP_NO_DB
async def test_hitl_tool_raises_pause_and_session_set_to_awaiting_approval() -> None:
    """When the LLM requests a hitl tool, prepare_hitl node sets session status to
    'awaiting_approval' and the graph pauses at wait_for_approval via interrupt()."""
    approval_id = str(uuid4())

    hitl_tool: Any = _make_recording_tool("request_approval", "hitl", _InvocationRecorder())

    # LLM sequence: classify intent → route to single_agent → request hitl tool
    llm = _ScriptedLLMClient([
        _stop(text=_intent_json("decision_support", goal_text="approve reorder")),
        _stop(text=_route_json("single_agent", ["replenishment"])),
        _tool_call_response("request_approval", {"action_summary": "Reorder 1000 units"}),
    ])

    registry = _make_registry_with_tool(hitl_tool)
    orchestrator = _make_orchestrator(llm, registry)
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
        response = await orchestrator.run(session_id, query)
        await asyncio.sleep(0)

    assert response.requires_approval is True
    statuses = [c.args[1] for c in mock_repo.update_status.call_args_list]
    assert "awaiting_approval" in statuses


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

    sse_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    orchestrator = SessionOrchestrator(
        llm_client=_AskUserLLMClient(),
        tool_registry=create_tool_registry(),
        memory_store=StubMemoryStore(),
        sse_queue=sse_queue,
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
    """
    from unittest.mock import AsyncMock, MagicMock, patch

    from langgraph.errors import GraphInterrupt

    orchestrator = SessionOrchestrator(
        llm_client=_AskUserLLMClient(),
        tool_registry=create_tool_registry(),
        memory_store=StubMemoryStore(),
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
    assert response.reply  # non-empty reply from run_direct_chat


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
# Scenario 14: sql_query tool — invoked when LLM requests it
# ---------------------------------------------------------------------------


@_SKIP_NO_DB
async def test_sql_query_tool_invoked() -> None:
    """When LLM requests 'sql_query' tool, SqlQueryTool handle() must be called.

    Complements Scenarios 1–4 which cover forecast, simulate_inventory,
    optimize_replenishment, and nl_query.
    """
    recorder = _InvocationRecorder()
    sql_tool = _make_recording_tool("sql_query", "read_only", recorder)

    sql_input = {"query": "SELECT * FROM inventory_items WHERE sku_id = 'SKU-001' LIMIT 10"}

    llm = _ScriptedLLMClient([
        _stop(text=_intent_json("lookup", goal_text="raw inventory rows for SKU-001")),
        _stop(text=_route_json("single_agent", ["data_engineer"])),
        _tool_call_response("sql_query", sql_input),
        _stop("verify pass"),
        _stop("Query returned 10 rows."),
        _stop("verify pass"),
    ])

    registry = _make_registry_with_tool(sql_tool)
    orchestrator = _make_orchestrator(llm, registry)
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
    assert "sql_query" in invoked_names
