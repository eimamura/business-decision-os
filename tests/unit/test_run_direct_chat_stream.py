from __future__ import annotations

"""T-115: Unit tests for run_direct_chat() streaming path.

Verifies that run_direct_chat():
- Iterates LLMStreamEvent objects from orchestrator._llm_client.stream()
- Pushes one text_delta event per token via orchestrator._push()
- Returns a SessionResponse whose reply is the concatenation of all tokens
"""

from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from packages.agent.llm import LLMStreamEvent
from packages.agent.orchestrator.models import (
    AgentRoute,
    SessionIntent,
    SessionUserQuery,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_intent() -> SessionIntent:
    return SessionIntent(
        category="direct_chat",
        confidence=1.0,
        rationale="test",
        goal_text=None,
    )


def _make_route() -> AgentRoute:
    return AgentRoute(
        mode="direct_chat",
        rationale="test",
    )


def _make_query(text: str = "hello") -> SessionUserQuery:
    return SessionUserQuery(text=text)


def _make_async_iter(events: list[LLMStreamEvent]) -> Any:
    """Return an async iterator that yields the given LLMStreamEvent objects."""

    async def _gen() -> Any:
        for evt in events:
            yield evt

    return _gen()


class _MockOrchestrator:
    """Minimal orchestrator double for run_direct_chat()."""

    def __init__(self, stream_events: list[LLMStreamEvent]) -> None:
        self._stream_events = stream_events
        self._pushed: list[dict[str, Any]] = []

        # _llm_client.stream is called with kwargs; returns an async iterator
        class _LLMClient:
            def __init__(self, events: list[LLMStreamEvent]) -> None:
                self._events = events

            async def stream(self, **kwargs: Any) -> Any:
                return _make_async_iter(self._events)

        self._llm_client = _LLMClient(stream_events)

    async def _push(self, event: dict[str, Any]) -> None:
        self._pushed.append(event)

    def _query_text(self, query: Any) -> str:
        return query.text


# make_step is imported inside run_direct_chat() with a local import; patch it
# at the source module so every call inside the function body gets the mock.
_MAKE_STEP_PATCH = patch(
    "packages.persistence.agent_steps_repo.make_step",
    new_callable=lambda: lambda: AsyncMock(return_value=uuid4()),
)


# ---------------------------------------------------------------------------
# T-115 scenario 1: stream with three tokens
# ---------------------------------------------------------------------------


async def test_run_direct_chat_pushes_one_text_delta_per_token() -> None:
    """_push is called exactly once per text_delta event."""
    from packages.agent.orchestrator.runtime import run_direct_chat

    tokens = ["tok1", "tok2", "tok3"]
    events = [LLMStreamEvent(event="text_delta", data=t) for t in tokens]
    orchestrator = _MockOrchestrator(events)
    session_id = uuid4()

    with patch(
        "packages.persistence.agent_steps_repo.make_step",
        new=AsyncMock(return_value=uuid4()),
    ):
        await run_direct_chat(
            orchestrator=orchestrator,
            session_id=session_id,
            query=_make_query(),
            intent=_make_intent(),
            route=_make_route(),
        )

    text_delta_pushes = [e for e in orchestrator._pushed if e.get("type") == "text_delta"]
    assert len(text_delta_pushes) == 3


async def test_run_direct_chat_pushed_deltas_match_tokens_in_order() -> None:
    """Each pushed text_delta event carries the correct delta string."""
    from packages.agent.orchestrator.runtime import run_direct_chat

    tokens = ["tok1", "tok2", "tok3"]
    events = [LLMStreamEvent(event="text_delta", data=t) for t in tokens]
    orchestrator = _MockOrchestrator(events)
    session_id = uuid4()

    with patch(
        "packages.persistence.agent_steps_repo.make_step",
        new=AsyncMock(return_value=uuid4()),
    ):
        await run_direct_chat(
            orchestrator=orchestrator,
            session_id=session_id,
            query=_make_query(),
            intent=_make_intent(),
            route=_make_route(),
        )

    text_delta_pushes = [e for e in orchestrator._pushed if e.get("type") == "text_delta"]
    deltas = [e["delta"] for e in text_delta_pushes]
    assert deltas == tokens


async def test_run_direct_chat_reply_is_concatenation_of_tokens() -> None:
    """SessionResponse.reply is the concatenation of all token strings."""
    from packages.agent.orchestrator.runtime import run_direct_chat

    tokens = ["tok1", "tok2", "tok3"]
    events = [LLMStreamEvent(event="text_delta", data=t) for t in tokens]
    orchestrator = _MockOrchestrator(events)
    session_id = uuid4()

    with patch(
        "packages.persistence.agent_steps_repo.make_step",
        new=AsyncMock(return_value=uuid4()),
    ):
        response = await run_direct_chat(
            orchestrator=orchestrator,
            session_id=session_id,
            query=_make_query(),
            intent=_make_intent(),
            route=_make_route(),
        )

    assert response.reply == "tok1tok2tok3"


# ---------------------------------------------------------------------------
# T-115 scenario 2: empty stream
# ---------------------------------------------------------------------------


async def test_run_direct_chat_empty_stream_pushes_no_text_delta() -> None:
    """When stream() yields no events, _push is never called with type=text_delta."""
    from packages.agent.orchestrator.runtime import run_direct_chat

    orchestrator = _MockOrchestrator([])
    session_id = uuid4()

    with patch(
        "packages.persistence.agent_steps_repo.make_step",
        new=AsyncMock(return_value=uuid4()),
    ):
        await run_direct_chat(
            orchestrator=orchestrator,
            session_id=session_id,
            query=_make_query(),
            intent=_make_intent(),
            route=_make_route(),
        )

    text_delta_pushes = [e for e in orchestrator._pushed if e.get("type") == "text_delta"]
    assert text_delta_pushes == []


async def test_run_direct_chat_empty_stream_returns_empty_reply() -> None:
    """When stream() yields no events, SessionResponse.reply is an empty string."""
    from packages.agent.orchestrator.runtime import run_direct_chat

    orchestrator = _MockOrchestrator([])
    session_id = uuid4()

    with patch(
        "packages.persistence.agent_steps_repo.make_step",
        new=AsyncMock(return_value=uuid4()),
    ):
        response = await run_direct_chat(
            orchestrator=orchestrator,
            session_id=session_id,
            query=_make_query(),
            intent=_make_intent(),
            route=_make_route(),
        )

    assert response.reply == ""


# ---------------------------------------------------------------------------
# Additional: response_ready is always pushed
# ---------------------------------------------------------------------------


async def test_run_direct_chat_always_pushes_response_ready() -> None:
    """After streaming completes, _push must be called with type=response_ready."""
    from packages.agent.orchestrator.runtime import run_direct_chat

    orchestrator = _MockOrchestrator([])
    session_id = uuid4()

    with patch(
        "packages.persistence.agent_steps_repo.make_step",
        new=AsyncMock(return_value=uuid4()),
    ):
        await run_direct_chat(
            orchestrator=orchestrator,
            session_id=session_id,
            query=_make_query(),
            intent=_make_intent(),
            route=_make_route(),
        )

    response_ready_pushes = [e for e in orchestrator._pushed if e.get("type") == "response_ready"]
    assert len(response_ready_pushes) == 1


async def test_run_direct_chat_text_delta_events_carry_session_id() -> None:
    """Each pushed text_delta event must include the session_id field."""
    from packages.agent.orchestrator.runtime import run_direct_chat

    events = [LLMStreamEvent(event="text_delta", data="hello")]
    orchestrator = _MockOrchestrator(events)
    session_id = uuid4()

    with patch(
        "packages.persistence.agent_steps_repo.make_step",
        new=AsyncMock(return_value=uuid4()),
    ):
        await run_direct_chat(
            orchestrator=orchestrator,
            session_id=session_id,
            query=_make_query(),
            intent=_make_intent(),
            route=_make_route(),
        )

    text_delta_pushes = [e for e in orchestrator._pushed if e.get("type") == "text_delta"]
    assert text_delta_pushes[0]["session_id"] == str(session_id)
