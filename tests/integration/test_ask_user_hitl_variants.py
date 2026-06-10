from __future__ import annotations

"""Integration tests for the 6 Ask User HITL modal variants (T-159).

Covers all scenarios from the Ask User (HITL) category in ToolScenarioModal.tsx:
  1  Vague Inventory Request          → AskUser triggered
  2  Forecast Without Target           → AskUser triggered
  3  Warehouse Specified, SKU Missing  → AskUser triggered
  4  SKU Known, Period Missing         → AskUser triggered
  5  Mostly Specified                  → AskUser or direct execution (either valid)
  6  Fully Specified (No AskUser)      → direct execution, no GraphInterrupt

No real DB is required — tests use MemorySaver (StubMemoryStore).
"""

import asyncio
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from langgraph.errors import GraphInterrupt

from packages.agent.llm import LLMMessage, LLMResponse, LLMStreamEvent, LLMUsage
from packages.agent.orchestrator import (
    SessionOrchestrator,
    SessionResponse,
    SessionUserQuery,
)
from packages.agent.orchestrator.models import AgentRoute, AskUserDecision, SessionIntent
from packages.memory import StubMemoryStore
from packages.tools import create_tool_registry
from tests.integration.conftest import make_stub_registry


# ---------------------------------------------------------------------------
# Shared helpers (copied locally — cross-test-file imports are forbidden)
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


# ---------------------------------------------------------------------------
# _AskUserLLMClient: returns needs_input=true for analytical queries
# (mirrors the one in test_prompts_mock_llm.py; defined locally per project rules)
# ---------------------------------------------------------------------------


class _AskUserLLMClient:
    """LLM client that always signals needs_input=true for analytical intent."""

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
                ' "question": "What date range and SKU should I analyze?",'
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
# _DirectLLMClient: always returns needs_input=false (direct execution path)
# ---------------------------------------------------------------------------


class _DirectLLMClient:
    """LLM client that never requests more information (needs_input=false)."""

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
                '{"needs_input": false,'
                ' "question": null,'
                ' "suggestions": []}'
            )
        if "intent classifier" in system:
            return _stop(
                _intent_json("domain_analysis", goal_text="analyze inventory for SKU-001")
            )
        if "router inside SessionOrchestrator" in system:
            return _stop(
                '{"mode":"direct_chat","agents":[],'
                '"requires_planning":false,"requires_dag":false,"rationale":"mock"}'
            )
        return _stop(
            "Inventory analysis for SKU-001 at DC West: stock levels are healthy. "
            "Comparison with previous month shows a 5% increase in demand."
        )

    async def stream(self, messages: list[LLMMessage], tools: Any = None, **kwargs: Any) -> Any:
        response = await self.complete(messages, tools=tools, **kwargs)

        async def _gen() -> Any:
            yield LLMStreamEvent(event="text_delta", data=response.text)

        return _gen()

    async def astream(self, input: Any, config: Any = None, **kwargs: Any) -> Any:  # type: ignore[override]
        """LangChain-style astream used by run_direct_chat in runtime.py.

        Must be an async generator so that `async for chunk in client.astream(...)` works.
        """
        from types import SimpleNamespace

        yield SimpleNamespace(
            content=(
                "Inventory analysis for SKU-001 at DC West: stock levels are healthy. "
                "Comparison with previous month shows a 5% increase in demand."
            )
        )


# ---------------------------------------------------------------------------
# Helper to build a no-DB orchestrator + mock session repo
# ---------------------------------------------------------------------------


def _ask_user_registry() -> Any:
    """ModelRegistry for tests that expect AskUser (GraphInterrupt) path.

    Structured-output call order for domain_analysis + needs_input=True:
      1. SessionIntent  (classify_intent node)
      2. AskUserDecision(needs_input=True)  (prepare_ask_user node)
    The graph pauses at wait_for_answer before select_mode is reached.
    """
    return make_stub_registry(
        SessionIntent(
            category="domain_analysis",
            confidence=0.95,
            rationale="test",
            goal_text="analyze inventory",
        ),
        AskUserDecision(
            needs_input=True,
            question="What date range and SKU should I analyze?",
            suggestions=["Last 30 days", "Q1 2025", "Last 12 months"],
        ),
    )


def _direct_registry() -> Any:
    """ModelRegistry for tests that expect direct execution (no AskUser interrupt).

    Structured-output call order for domain_analysis + needs_input=False:
      1. SessionIntent  (classify_intent node)
      2. AskUserDecision(needs_input=False)  (prepare_ask_user node)
      3. AgentRoute(direct_chat)  (select_mode node)
    """
    return make_stub_registry(
        SessionIntent(
            category="domain_analysis",
            confidence=0.95,
            rationale="test",
            goal_text="analyze inventory for SKU-001",
        ),
        AskUserDecision(needs_input=False, question=None, suggestions=[]),
        AgentRoute(
            mode="direct_chat",
            agents=[],
            requires_planning=False,
            requires_dag=False,
            rationale="mock",
        ),
    )


def _make_ask_user_orchestrator(
    llm_client: Any,
    sse_queue: asyncio.Queue[dict[str, Any]] | None = None,
    model_registry: Any = None,
) -> SessionOrchestrator:
    return SessionOrchestrator(
        llm_client=llm_client,
        tool_registry=create_tool_registry(),
        memory_store=StubMemoryStore(),
        sse_queue=sse_queue,
        model_registry=model_registry,
    )


def _mock_session_repo() -> Any:
    repo = MagicMock()
    repo.update_status = AsyncMock()
    return repo


# ---------------------------------------------------------------------------
# Variant 1: Vague Inventory Request — expects AskUser (GraphInterrupt)
# ---------------------------------------------------------------------------


async def test_vague_inventory_request_triggers_ask_user_interrupt() -> None:
    """Maximally underspecified prompt triggers the AskUser HITL flow.

    Prompt: "Analyze inventory"
    Expected: GraphInterrupt is raised and ask_user_required SSE event is emitted.
    """
    sse_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    orchestrator = _make_ask_user_orchestrator(
        _AskUserLLMClient(), sse_queue, model_registry=_ask_user_registry()
    )
    session_id = uuid4()
    query = SessionUserQuery(text="Analyze inventory")

    mock_repo = _mock_session_repo()

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
    assert "ask_user_required" in event_types, (
        f"ask_user_required missing from SSE events; got: {event_types}"
    )


# ---------------------------------------------------------------------------
# Variant 2: Forecast Without Target — expects AskUser (GraphInterrupt)
# ---------------------------------------------------------------------------


async def test_forecast_without_target_triggers_ask_user_interrupt() -> None:
    """Intent is clear but product and horizon are both missing — AskUser expected.

    Prompt: "Run a demand forecast"
    Expected: GraphInterrupt raised, ask_user_required event in SSE queue.
    """
    sse_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    orchestrator = _make_ask_user_orchestrator(
        _AskUserLLMClient(), sse_queue, model_registry=_ask_user_registry()
    )
    session_id = uuid4()
    query = SessionUserQuery(text="Run a demand forecast")

    mock_repo = _mock_session_repo()

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
    assert "ask_user_required" in event_types, (
        f"ask_user_required missing from SSE events; got: {event_types}"
    )


# ---------------------------------------------------------------------------
# Variant 3: Warehouse Specified, SKU Missing — expects AskUser (GraphInterrupt)
# ---------------------------------------------------------------------------


async def test_warehouse_specified_sku_missing_triggers_ask_user_interrupt() -> None:
    """Location provided but SKU is absent — one focused question expected.

    Prompt: "Forecast demand for DC West next quarter"
    Expected: GraphInterrupt raised, ask_user_required event in SSE queue.
    """
    sse_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    orchestrator = _make_ask_user_orchestrator(
        _AskUserLLMClient(), sse_queue, model_registry=_ask_user_registry()
    )
    session_id = uuid4()
    query = SessionUserQuery(text="Forecast demand for DC West next quarter")

    mock_repo = _mock_session_repo()

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
    assert "ask_user_required" in event_types, (
        f"ask_user_required missing from SSE events; got: {event_types}"
    )

    ask_event = next(e for e in events if e.get("type") == "ask_user_required")
    assert ask_event.get("question"), "ask_user_required event must contain a non-empty question"
    assert ask_event.get("ask_user_id") is not None, "ask_user_id must be set"


# ---------------------------------------------------------------------------
# Variant 4: SKU Known, Period Missing — expects AskUser (GraphInterrupt)
# ---------------------------------------------------------------------------


async def test_sku_known_period_missing_triggers_ask_user_interrupt() -> None:
    """Product is identified but analysis window is open — agent asks for date range.

    Prompt: "Check stockout risk for SKU-001"
    Expected: GraphInterrupt raised, ask_user_required event in SSE queue.
    """
    sse_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    orchestrator = _make_ask_user_orchestrator(
        _AskUserLLMClient(), sse_queue, model_registry=_ask_user_registry()
    )
    session_id = uuid4()
    query = SessionUserQuery(text="Check stockout risk for SKU-001")

    mock_repo = _mock_session_repo()

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
    assert "ask_user_required" in event_types, (
        f"ask_user_required missing from SSE events; got: {event_types}"
    )

    ask_event = next(e for e in events if e.get("type") == "ask_user_required")
    suggestions = ask_event.get("suggestions")
    assert isinstance(suggestions, list), "suggestions must be a list"


# ---------------------------------------------------------------------------
# Variant 5: Mostly Specified — AskUser or direct execution (both valid)
# ---------------------------------------------------------------------------


async def test_mostly_specified_request_does_not_crash_orchestrator() -> None:
    """SKU and quarter are provided — agent may proceed or ask for a service-level threshold.

    Prompt: "Optimize replenishment for SKU-001 for Q3 2025"
    Expected: orchestrator returns a SessionResponse OR raises GraphInterrupt —
              either outcome is acceptable; the key invariant is no unhandled exception.
    """
    orchestrator = _make_ask_user_orchestrator(
        _AskUserLLMClient(), model_registry=_ask_user_registry()
    )
    session_id = uuid4()
    query = SessionUserQuery(text="Optimize replenishment for SKU-001 for Q3 2025")

    mock_repo = _mock_session_repo()

    outcome_is_valid = False
    with patch(
        "packages.agent.orchestrator.session_orchestrator.DecisionSessionRepository",
        return_value=mock_repo,
    ):
        try:
            response = await orchestrator.run(session_id, query)
            await asyncio.sleep(0)
            # Direct-execution path: a SessionResponse must be returned
            assert isinstance(response, SessionResponse), (
                f"Expected SessionResponse on direct-execution path; got {type(response)}"
            )
            outcome_is_valid = True
        except GraphInterrupt:
            # AskUser path: GraphInterrupt is also acceptable
            outcome_is_valid = True

    assert outcome_is_valid, "Orchestrator produced neither SessionResponse nor GraphInterrupt"


# ---------------------------------------------------------------------------
# Variant 6: Fully Specified — NO AskUser expected (direct execution)
# ---------------------------------------------------------------------------


async def test_fully_specified_request_does_not_raise_graph_interrupt() -> None:
    """All critical parameters included — agent skips AskUser and executes directly.

    Prompt: "Analyze inventory for SKU-001 at DC West for the past 30 days
             and compare with the previous month"
    Expected: NO GraphInterrupt; response.reply is non-empty.
    """
    orchestrator = _make_ask_user_orchestrator(
        _DirectLLMClient(), model_registry=_direct_registry()
    )
    session_id = uuid4()
    query = SessionUserQuery(
        text=(
            "Analyze inventory for SKU-001 at DC West for the past 30 days "
            "and compare with the previous month"
        )
    )

    mock_repo = _mock_session_repo()

    with patch(
        "packages.agent.orchestrator.session_orchestrator.DecisionSessionRepository",
        return_value=mock_repo,
    ):
        # Must NOT raise GraphInterrupt
        response = await orchestrator.run(session_id, query)
        await asyncio.sleep(0)

    assert isinstance(response, SessionResponse), (
        f"Expected SessionResponse; got {type(response)}"
    )
    assert response.reply, "reply must be non-empty for a fully-specified request"
