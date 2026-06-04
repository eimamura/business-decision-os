from __future__ import annotations

"""T-115: Unit tests for run_direct_chat() streaming path."""

from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from packages.agent.llm import LLMStreamEvent
from packages.agent.orchestrator.models import AgentRoute, SessionIntent, SessionUserQuery


def _make_intent() -> SessionIntent:
    return SessionIntent(category="direct_chat", confidence=1.0, rationale="test", goal_text=None)


def _make_route() -> AgentRoute:
    return AgentRoute(mode="direct_chat", rationale="test")


def _make_query(text: str = "hello") -> SessionUserQuery:
    return SessionUserQuery(text=text)


class _MockOrchestrator:
    def __init__(self, stream_events: list[LLMStreamEvent]) -> None:
        self._pushed: list[dict[str, Any]] = []

        class _LLM:
            def __init__(self, events: list[LLMStreamEvent]) -> None:
                self._events = events

            async def stream(self, **kwargs: Any) -> Any:
                async def _gen() -> Any:
                    for e in self._events:
                        yield e

                return _gen()

        self._llm_client = _LLM(stream_events)

    async def _push(self, event: dict[str, Any]) -> None:
        self._pushed.append(event)

    def _query_text(self, query: Any) -> str:
        return query.text


def _patch_make_step() -> Any:
    return patch(
        "packages.persistence.agent_steps_repo.make_step",
        new=AsyncMock(return_value=uuid4()),
    )


async def _run(orchestrator: _MockOrchestrator, session_id: Any) -> Any:
    from packages.agent.orchestrator.runtime import run_direct_chat

    with _patch_make_step():
        return await run_direct_chat(
            orchestrator=orchestrator,
            session_id=session_id,
            query=_make_query(),
            intent=_make_intent(),
            route=_make_route(),
        )


async def test_run_direct_chat_streams_tokens_and_builds_reply() -> None:
    """Pushes one text_delta per token in order; reply is the concatenation."""
    tokens = ["tok1", "tok2", "tok3"]
    orch = _MockOrchestrator([LLMStreamEvent(event="text_delta", data=t) for t in tokens])

    response = await _run(orch, uuid4())

    deltas = [e for e in orch._pushed if e.get("type") == "text_delta"]
    assert len(deltas) == 3
    assert [e["delta"] for e in deltas] == tokens
    assert response.reply == "tok1tok2tok3"


async def test_run_direct_chat_empty_stream() -> None:
    """Empty stream: no text_delta pushes, empty reply, response_ready still emitted."""
    orch = _MockOrchestrator([])

    response = await _run(orch, uuid4())

    assert [e for e in orch._pushed if e.get("type") == "text_delta"] == []
    assert response.reply == ""
    assert len([e for e in orch._pushed if e.get("type") == "response_ready"]) == 1


async def test_run_direct_chat_text_delta_carries_session_id() -> None:
    """Each pushed text_delta event includes the session_id field."""
    session_id = uuid4()
    orch = _MockOrchestrator([LLMStreamEvent(event="text_delta", data="hello")])

    await _run(orch, session_id)

    deltas = [e for e in orch._pushed if e.get("type") == "text_delta"]
    assert deltas[0]["session_id"] == str(session_id)
