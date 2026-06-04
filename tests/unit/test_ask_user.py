from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest

from packages.agent.llm import LLMMessage, LLMResponse, LLMStreamEvent, LLMToolSpec, LLMUsage
from packages.agent.orchestrator.ask_user import build_ask_user_event, is_analytical_intent

_SESSION_ID = UUID("12345678-1234-5678-1234-567812345678")


# ---------------------------------------------------------------------------
# is_analytical_intent
# ---------------------------------------------------------------------------


def test_is_analytical_intent_domain_analysis() -> None:
    assert is_analytical_intent("domain_analysis") is True


def test_is_analytical_intent_cross_domain() -> None:
    assert is_analytical_intent("cross_domain_analysis") is True


def test_is_analytical_intent_decision_support() -> None:
    assert is_analytical_intent("decision_support") is True


def test_is_analytical_intent_chat() -> None:
    assert is_analytical_intent("chat") is False


def test_is_analytical_intent_lookup() -> None:
    assert is_analytical_intent("lookup") is False


# ---------------------------------------------------------------------------
# build_ask_user_event
# ---------------------------------------------------------------------------


def test_build_ask_user_event_type() -> None:
    event = build_ask_user_event(_SESSION_ID, "What is the date range?", "ask-id-1")
    assert event["type"] == "ask_user_required"


def test_build_ask_user_event_session_id_matches() -> None:
    event = build_ask_user_event(_SESSION_ID, "What is the date range?", "ask-id-2")
    assert event["session_id"] == str(_SESSION_ID)


def test_build_ask_user_event_ask_user_id_present() -> None:
    event = build_ask_user_event(_SESSION_ID, "What is the date range?", "ask-id-3")
    assert event["ask_user_id"] == "ask-id-3"


def test_build_ask_user_event_question_present() -> None:
    question = "Which warehouse location should I focus on?"
    event = build_ask_user_event(_SESSION_ID, question, "ask-id-4")
    assert event["question"] == question


def test_build_ask_user_event_has_timestamp() -> None:
    event = build_ask_user_event(_SESSION_ID, "What SKU?", "ask-id-5")
    assert "timestamp" in event
    assert isinstance(event["timestamp"], str)
    assert len(event["timestamp"]) > 0


def test_build_ask_user_event_with_suggestions() -> None:
    suggestions = ["Last 30 days", "Q1 2025", "Last 12 months"]
    event = build_ask_user_event(_SESSION_ID, "What date range?", "ask-id-6", suggestions)
    assert event["suggestions"] == ["Last 30 days", "Q1 2025", "Last 12 months"]


def test_build_ask_user_event_without_suggestions_defaults_empty() -> None:
    event = build_ask_user_event(_SESSION_ID, "What date range?", "ask-id-7", None)
    assert event["suggestions"] == []


# ---------------------------------------------------------------------------
# Orchestrator _node_ask_user — mock LLM tests
# ---------------------------------------------------------------------------


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


class _AskUserNoLLMClient:
    """Returns needs_input=false — ask_user node passes through."""

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
            return _make_llm_response('{"needs_input": false, "question": null}')
        if "intent classifier" in system:
            return _make_llm_response(
                '{"category":"domain_analysis","confidence":0.9,'
                '"rationale":"sufficient context","goal_text":"analyze inventory"}'
            )
        if "router inside SessionOrchestrator" in system:
            return _make_llm_response(
                '{"mode":"direct_chat","agents":[],'
                '"requires_planning":false,"requires_dag":false,"rationale":"chat"}'
            )
        return _make_llm_response("Analysis complete.")

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


def _make_orchestrator(llm_client: Any) -> Any:
    from packages.agent.orchestrator import SessionOrchestrator
    from packages.memory import StubMemoryStore
    from packages.tools import create_tool_registry

    return SessionOrchestrator(
        llm_client=llm_client,
        tool_registry=create_tool_registry(),
        memory_store=StubMemoryStore(),
    )


@pytest.mark.asyncio
async def test_ask_user_node_passes_through_when_no_input_needed() -> None:
    """When the LLM returns needs_input=false, the node passes through to select_mode."""
    from unittest.mock import AsyncMock, MagicMock, patch

    from packages.agent.orchestrator import SessionUserQuery

    orchestrator = _make_orchestrator(_AskUserNoLLMClient())
    session_id = uuid4()
    query = SessionUserQuery(text="Analyze inventory levels for SKU-001 in Q1 2025")

    mock_repo = MagicMock()
    mock_repo.update_status = AsyncMock()

    with patch(
        "packages.agent.orchestrator.session_orchestrator.DecisionSessionRepository",
        return_value=mock_repo,
    ):
        result = await orchestrator.run(session_id, query)
        await asyncio.sleep(0)

    assert result is not None
    # route rationale should NOT be ask_user since node passed through
    assert result.route.rationale != "ask_user"


