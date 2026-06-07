from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest


def _make_orchestrator(model_registry=None):
    from packages.agent.orchestrator.session_orchestrator import SessionOrchestrator

    return SessionOrchestrator(
        llm_client=MagicMock(),
        tool_registry=MagicMock(),
        memory_store=MagicMock(),
        model_registry=model_registry,
    )


def _make_registry_with_model(model_mock):
    from packages.agent.model_registry import ModelRegistry

    registry = MagicMock(spec=ModelRegistry)
    registry.get.return_value = model_mock
    return registry


async def test_classify_intent_uses_structured_output_when_registry_provided():
    from packages.agent.orchestrator.models import SessionIntent, SessionUserQuery
    from packages.persistence.agent_steps_repo import make_step

    intent = SessionIntent(category="analysis", confidence=0.9, rationale="test")

    model_mock = MagicMock()
    structured = MagicMock()
    structured.ainvoke = AsyncMock(return_value=intent)
    model_mock.with_structured_output.return_value = structured

    registry = _make_registry_with_model(model_mock)
    orchestrator = _make_orchestrator(model_registry=registry)

    query = SessionUserQuery(text="What is inventory level?")
    result = await orchestrator.classify_intent(query, uuid4())

    model_mock.with_structured_output.assert_called_once_with(SessionIntent)
    structured.ainvoke.assert_called_once()
    assert result is intent


async def test_select_execution_mode_uses_structured_output_when_registry_provided():
    from packages.agent.orchestrator.models import AgentRoute, SessionIntent, SessionUserQuery

    route = AgentRoute(mode="direct_chat", rationale="simple query")
    intent = SessionIntent(category="analysis", confidence=0.9, rationale="test")

    model_mock = MagicMock()
    structured = MagicMock()
    structured.ainvoke = AsyncMock(return_value=route)
    model_mock.with_structured_output.return_value = structured

    registry = _make_registry_with_model(model_mock)
    orchestrator = _make_orchestrator(model_registry=registry)

    query = SessionUserQuery(text="What is inventory level?")
    result = await orchestrator.select_execution_mode(query, intent, uuid4())

    model_mock.with_structured_output.assert_called_once_with(AgentRoute)
    structured.ainvoke.assert_called_once()
    assert result.mode == "direct_chat"


async def test_classify_intent_falls_back_to_llm_client_when_no_registry():
    from packages.agent.orchestrator.models import SessionUserQuery

    response_text = '{"category": "analysis", "confidence": 0.8, "rationale": "x"}'
    llm_response = MagicMock()
    llm_response.text = response_text
    llm_client = MagicMock()
    llm_client.complete = AsyncMock(return_value=llm_response)

    orchestrator = _make_orchestrator(model_registry=None)
    orchestrator._llm_client = llm_client

    query = SessionUserQuery(text="fallback test")
    result = await orchestrator.classify_intent(query, uuid4())

    llm_client.complete.assert_called_once()
    assert result.category == "analysis"
