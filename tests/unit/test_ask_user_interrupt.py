from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest

from typing import AsyncIterator

from packages.agent.llm import LLMMessage, LLMResponse, LLMStreamEvent, LLMToolSpec, LLMUsage
from packages.agent.orchestrator.models import AgentRoute, AskUserDecision, SessionIntent
from tests.unit.helpers import MultiRoleModelRegistry, StructuredOutputFakeModel


def _make_llm_response(text: str) -> LLMResponse:
    return LLMResponse(
        text=text,
        tool_calls=[],
        finish_reason="stop",
        usage=LLMUsage(
            input_tokens=0,
            output_tokens=0,
            total_cost_usd=Decimal("0"),
        ),
        model="stub",
        request_id=str(uuid4()),
        latency_ms=0,
    )


class _AskUserYesLLMClient:
    """Returns needs_input=true with a question and 3 suggestions."""

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
            return _make_llm_response(
                '{"needs_input": true, "question": "What date range should I analyze?",'
                ' "suggestions": ["Last 30 days", "Q1 2025", "Last 12 months"]}'
            )
        if "intent classifier" in system:
            return _make_llm_response(
                '{"category":"domain_analysis","confidence":0.9,'
                '"rationale":"needs date range","goal_text":"analyze inventory"}'
            )
        if "router inside SessionOrchestrator" in system:
            return _make_llm_response(
                '{"mode":"direct_chat","agents":[],'
                '"requires_planning":false,"requires_dag":false,"rationale":"resumed"}'
            )
        return _make_llm_response("Analysis complete for the requested date range.")

    async def stream(
        self,
        messages: list[LLMMessage],
        tools: list[LLMToolSpec] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[LLMStreamEvent]:
        llm_response = await self.complete(messages, tools=tools, **kwargs)

        async def _gen() -> AsyncIterator[LLMStreamEvent]:
            yield LLMStreamEvent(event="text_delta", data=llm_response.text)

        return _gen()

    async def astream(self, input: Any, config: Any = None, **kwargs: Any) -> AsyncIterator[Any]:
        from types import SimpleNamespace
        msgs = [
            LLMMessage(
                role="system" if getattr(m, "type", "") == "system" else (
                    "assistant" if getattr(m, "type", "") == "ai" else "user"
                ),
                content=getattr(m, "content", ""),
            )
            for m in (input if isinstance(input, list) else [])
        ]
        resp = await self.complete(msgs)
        yield SimpleNamespace(content=resp.text)


def _make_orchestrator(llm_client: Any, needs_input: bool = True) -> Any:
    """Build a SessionOrchestrator with a model_registry that returns domain_analysis intent.

    When needs_input=True, AskUserDecision triggers a GraphInterrupt.
    When needs_input=False, the graph flows through to routing.
    """
    from packages.agent.orchestrator import SessionOrchestrator
    from packages.memory import StubMemoryStore
    from packages.tools import create_tool_registry

    # domain_analysis is an analytical intent — _node_prepare_ask_user fires
    ask_decision = AskUserDecision(
        needs_input=needs_input,
        question="What date range should I analyze?" if needs_input else None,
        suggestions=["Last 30 days", "Q1 2025", "Last 12 months"] if needs_input else None,
    )
    orchestrator_model = StructuredOutputFakeModel([
        SessionIntent(
            category="domain_analysis", confidence=0.9,
            rationale="needs date range", goal_text="analyze inventory",
        ),
        ask_decision,
        AgentRoute(
            mode="direct_chat", agents=[],
            requires_planning=False, requires_dag=False, rationale="resumed",
        ),
    ])
    registry = MultiRoleModelRegistry({"orchestrator": orchestrator_model})

    return SessionOrchestrator(
        llm_client=llm_client,
        tool_registry=create_tool_registry(),
        memory_store=StubMemoryStore(),
        model_registry=registry,
    )


async def test_prepare_ask_user_clamps_suggestions_to_three() -> None:
    """_node_prepare_ask_user must clamp suggestions to at most 3 items."""
    from unittest.mock import AsyncMock, MagicMock, patch

    from langgraph.errors import GraphInterrupt

    from packages.agent.orchestrator import SessionOrchestrator, SessionUserQuery
    from packages.memory import StubMemoryStore
    from packages.tools import create_tool_registry

    # AskUserDecision with 5 suggestions — must be clamped to 3 by the node
    orchestrator_model = StructuredOutputFakeModel([
        SessionIntent(
            category="domain_analysis", confidence=0.9,
            rationale="needs sku", goal_text="analyze sku",
        ),
        AskUserDecision(
            needs_input=True,
            question="Which SKU?",
            suggestions=["A", "B", "C", "D", "E"],
        ),
        AgentRoute(
            mode="direct_chat", agents=[],
            requires_planning=False, requires_dag=False, rationale="resumed",
        ),
    ])
    registry = MultiRoleModelRegistry({"orchestrator": orchestrator_model})

    captured_event: dict[str, Any] = {}

    class _CapturingSseQueue:
        async def put(self, event: dict[str, Any]) -> None:
            if event.get("type") == "ask_user_required":
                captured_event.update(event)

    orchestrator = SessionOrchestrator(
        llm_client=_AskUserYesLLMClient(),
        tool_registry=create_tool_registry(),
        memory_store=StubMemoryStore(),
        model_registry=registry,
    )
    orchestrator._sse_queue = _CapturingSseQueue()  # type: ignore[assignment]
    session_id = uuid4()
    query = SessionUserQuery(text="Analyze SKU data")

    mock_repo = MagicMock()
    mock_repo.update_status = AsyncMock()

    with patch(
        "packages.agent.orchestrator.session_orchestrator.DecisionSessionRepository",
        return_value=mock_repo,
    ):
        with pytest.raises(GraphInterrupt):
            await orchestrator.run(session_id, query)
        await asyncio.sleep(0)

    assert len(captured_event.get("suggestions", [])) <= 3


async def test_ask_user_graph_pauses_at_wait_for_answer() -> None:
    """Graph pauses at wait_for_answer when LLM returns needs_input=true."""
    from unittest.mock import AsyncMock, MagicMock, patch

    from langgraph.errors import GraphInterrupt

    from packages.agent.orchestrator import SessionUserQuery

    orchestrator = _make_orchestrator(_AskUserYesLLMClient())
    session_id = uuid4()
    query = SessionUserQuery(text="Show me inventory analysis")

    mock_repo = MagicMock()
    mock_repo.update_status = AsyncMock()

    with patch(
        "packages.agent.orchestrator.session_orchestrator.DecisionSessionRepository",
        return_value=mock_repo,
    ):
        with pytest.raises(GraphInterrupt):
            await orchestrator.run(session_id, query)
        await asyncio.sleep(0)

    graph = await orchestrator._get_graph()
    config = {"configurable": {"thread_id": str(session_id)}}
    state = await graph.aget_state(config)
    assert state.values.get("ask_user_id") is not None
    assert state.values.get("ask_user_question") == "What date range should I analyze?"


async def test_ask_user_resume_reaches_select_mode() -> None:
    """Resuming via answer_ask_user() completes and returns a SessionResponse."""
    from unittest.mock import AsyncMock, MagicMock, patch

    from langgraph.errors import GraphInterrupt

    from packages.agent.orchestrator import SessionResponse, SessionUserQuery

    orchestrator = _make_orchestrator(_AskUserYesLLMClient())
    session_id = uuid4()
    query = SessionUserQuery(text="Show me inventory analysis")

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


async def test_ask_user_non_analytical_passes_through() -> None:
    """Chat intent skips ask_user; graph completes normally with no GraphInterrupt."""
    from unittest.mock import AsyncMock, MagicMock, patch

    from packages.agent.orchestrator import SessionResponse, SessionUserQuery

    class _ChatLLMClient:
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
                return _make_llm_response('{"needs_input": false, "question": null, "suggestions": null}')
            if "intent classifier" in system:
                return _make_llm_response(
                    '{"category":"chat","confidence":0.95,'
                    '"rationale":"greeting","goal_text":null}'
                )
            if "router inside SessionOrchestrator" in system:
                return _make_llm_response(
                    '{"mode":"direct_chat","agents":[],'
                    '"requires_planning":false,"requires_dag":false,"rationale":"chat"}'
                )
            return _make_llm_response("Hello! How can I help?")

        async def stream(
            self,
            messages: list[LLMMessage],
            tools: list[LLMToolSpec] | None = None,
            **kwargs: Any,
        ) -> AsyncIterator[LLMStreamEvent]:
            llm_response = await self.complete(messages, tools=tools, **kwargs)

            async def _gen() -> AsyncIterator[LLMStreamEvent]:
                yield LLMStreamEvent(event="text_delta", data=llm_response.text)

            return _gen()

        async def astream(self, input: Any, config: Any = None, **kwargs: Any) -> AsyncIterator[Any]:
            from types import SimpleNamespace
            msgs = [
                LLMMessage(
                    role="system" if getattr(m, "type", "") == "system" else (
                        "assistant" if getattr(m, "type", "") == "ai" else "user"
                    ),
                    content=getattr(m, "content", ""),
                )
                for m in (input if isinstance(input, list) else [])
            ]
            resp = await self.complete(msgs)
            yield SimpleNamespace(content=resp.text)

    from packages.agent.orchestrator import SessionOrchestrator
    from packages.memory import StubMemoryStore
    from packages.tools import create_tool_registry

    # chat intent — ask_user node is skipped
    chat_orchestrator_model = StructuredOutputFakeModel([
        SessionIntent(
            category="chat", confidence=0.95,
            rationale="greeting", goal_text=None,
        ),
        AgentRoute(
            mode="direct_chat", agents=[],
            requires_planning=False, requires_dag=False, rationale="chat",
        ),
    ])
    chat_registry = MultiRoleModelRegistry({"orchestrator": chat_orchestrator_model})

    orchestrator = SessionOrchestrator(
        llm_client=_ChatLLMClient(),
        tool_registry=create_tool_registry(),
        memory_store=StubMemoryStore(),
        model_registry=chat_registry,
    )
    session_id = uuid4()
    query = SessionUserQuery(text="Hello!")

    mock_repo = MagicMock()
    mock_repo.update_status = AsyncMock()

    with patch(
        "packages.agent.orchestrator.session_orchestrator.DecisionSessionRepository",
        return_value=mock_repo,
    ):
        result = await orchestrator.run(session_id, query)
        await asyncio.sleep(0)

    assert isinstance(result, SessionResponse)
