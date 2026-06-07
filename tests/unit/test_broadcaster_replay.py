from __future__ import annotations

"""Unit tests for P28-B-03 (T-176, T-177).

T-176: Broadcaster replay buffer delivers buffered events to a late subscriber;
       buffer is cleared after a terminal event.
T-177: _node_run_sequential emits a response_ready SSE event.
"""

import asyncio
from typing import Any
from uuid import uuid4

import pytest

from apps.api.state import Broadcaster


# ---------------------------------------------------------------------------
# T-176 — Broadcaster replay buffer
# ---------------------------------------------------------------------------


async def test_broadcaster_replay_buffer_delivers_to_late_subscriber() -> None:
    """A subscriber that joins after events have already been put must receive
    all buffered events immediately on subscribe()."""
    bc = Broadcaster()

    # Put two events with no subscribers yet
    await bc.put({"type": "graph_node", "event": "start", "name": "classify_intent"})
    await bc.put({"type": "graph_node", "event": "end", "name": "classify_intent"})

    # Late subscriber joins — should get replayed events immediately
    q = bc.subscribe()

    assert not q.empty(), "Late subscriber must receive buffered events synchronously"
    e1 = q.get_nowait()
    assert e1["name"] == "classify_intent"
    assert e1["event"] == "start"
    e2 = q.get_nowait()
    assert e2["name"] == "classify_intent"
    assert e2["event"] == "end"


async def test_broadcaster_replay_buffer_cleared_after_done() -> None:
    """Buffer must be empty after a 'done' terminal event is delivered."""
    bc = Broadcaster()

    await bc.put({"type": "graph_node", "event": "start", "name": "classify_intent"})
    await bc.put({"type": "done", "session_id": "s1", "reply": "ok", "timestamp": "t"})

    # Buffer should be cleared after the terminal event
    assert bc._buffer == [], "Buffer must be cleared after 'done' event"

    # A new late subscriber should receive no replayed events
    q = bc.subscribe()
    assert q.empty(), "Late subscriber after terminal event must receive no replayed events"


async def test_broadcaster_replay_buffer_cleared_after_error() -> None:
    """Buffer must be empty after an 'error' terminal event is delivered."""
    bc = Broadcaster()

    await bc.put({"type": "graph_node", "event": "start", "name": "classify_intent"})
    await bc.put({"type": "error", "code": "oops", "message": "fail", "recoverable": False, "timestamp": "t"})

    assert bc._buffer == [], "Buffer must be cleared after 'error' event"


async def test_broadcaster_replay_buffer_cleared_after_awaiting_input() -> None:
    """Buffer must be empty after an 'awaiting_input' terminal event is delivered."""
    bc = Broadcaster()

    await bc.put({"type": "graph_node", "event": "start", "name": "prepare_ask_user"})
    await bc.put({"type": "awaiting_input", "session_id": "s1", "ask_user_id": "a1", "timestamp": "t"})

    assert bc._buffer == [], "Buffer must be cleared after 'awaiting_input' event"


async def test_broadcaster_replay_buffer_current_subscriber_gets_events_once() -> None:
    """A subscriber registered before any events must NOT receive duplicates
    (once from the live put, not again from the replay buffer)."""
    bc = Broadcaster()

    # Subscribe first, then put events
    q = bc.subscribe()

    await bc.put({"type": "graph_node", "name": "classify_intent"})
    await bc.put({"type": "done", "reply": "ok", "timestamp": "t"})

    # Should receive exactly 2 events, not 4
    events: list[dict[str, Any]] = []
    while not q.empty():
        events.append(q.get_nowait())

    assert len(events) == 2, f"Expected 2 events (no duplicates), got {len(events)}: {events}"


async def test_broadcaster_replay_buffer_multiple_late_subscribers() -> None:
    """Two late subscribers both get the full replay buffer."""
    bc = Broadcaster()

    await bc.put({"type": "graph_node", "name": "node_a"})
    await bc.put({"type": "graph_node", "name": "node_b"})

    q1 = bc.subscribe()
    q2 = bc.subscribe()

    for q in (q1, q2):
        names: list[str] = []
        while not q.empty():
            ev = q.get_nowait()
            names.append(ev["name"])
        assert names == ["node_a", "node_b"], f"Subscriber got unexpected events: {names}"


async def test_broadcaster_replay_buffer_respects_max_size() -> None:
    """Buffer must not grow beyond _BROADCASTER_BUFFER_MAX (1000 by default)."""
    from apps.api.state import _BROADCASTER_BUFFER_MAX

    bc = Broadcaster()
    for i in range(_BROADCASTER_BUFFER_MAX + 50):
        await bc.put({"type": "graph_node", "seq": i})

    assert len(bc._buffer) <= _BROADCASTER_BUFFER_MAX, (
        f"Buffer size {len(bc._buffer)} exceeds max {_BROADCASTER_BUFFER_MAX}"
    )


# ---------------------------------------------------------------------------
# T-177 — _node_run_sequential emits response_ready
# ---------------------------------------------------------------------------


async def test_node_run_sequential_emits_response_ready() -> None:
    """_node_run_sequential must push a response_ready event via orchestrator._push."""
    from typing import AsyncIterator
    from unittest.mock import AsyncMock, MagicMock, patch

    from packages.agent.llm import LLMMessage, LLMResponse, LLMStreamEvent, LLMToolSpec
    from packages.agent.orchestrator import (
        AgentRoute,
        SessionIntent,
        SessionOrchestrator,
        SessionResponse,
        SessionUserQuery,
    )
    from packages.memory import StubMemoryStore
    from packages.tools import create_tool_registry
    from tests.unit.helpers import make_llm_usage

    def _llm_resp(text: str) -> LLMResponse:
        return LLMResponse(
            text=text,
            tool_calls=[],
            finish_reason="stop",
            usage=make_llm_usage(input_tokens=0, output_tokens=0),
            model="stub",
            request_id=str(uuid4()),
            latency_ms=0,
        )

    class _SequentialLLMClient:
        """Routes to single_agent mode and produces a minimal specialist result."""

        def __init__(self) -> None:
            self._model = "stub"

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
            if "intent classifier" in system:
                return _llm_resp(
                    '{"category":"domain_analysis","confidence":0.9,'
                    '"rationale":"replenishment","goal_text":"check replenishment"}'
                )
            if "router inside SessionOrchestrator" in system:
                return _llm_resp(
                    '{"mode":"single_agent","agents":["control"],'
                    '"requires_planning":false,"requires_dag":false,"rationale":"single"}'
                )
            # ControlAgent and synthesis
            return _llm_resp("Supply chain analysis complete.")

        async def stream(
            self,
            messages: list[LLMMessage],
            tools: list[LLMToolSpec] | None = None,
            **kwargs: Any,
        ) -> AsyncIterator[LLMStreamEvent]:
            resp = await self.complete(messages, **kwargs)

            async def _gen() -> AsyncIterator[LLMStreamEvent]:
                yield LLMStreamEvent(event="text_delta", data=resp.text)

            return _gen()

    pushed_events: list[dict[str, Any]] = []

    class _CaptureBroadcaster:
        async def put(self, event: dict[str, Any]) -> None:
            pushed_events.append(event)

    # Patch _run_agents_in_order and _synthesize_response so the test doesn't
    # need a real DB or full agent stack.
    mock_specialist_result = MagicMock()
    mock_specialist_result.output = {"text": "Inventory is healthy."}
    mock_specialist_result.status = "ok"
    mock_specialist_result.usage = {}

    mock_session_response = SessionResponse(
        mode="single_agent",
        reply="Replenishment is healthy.",
        intent=SessionIntent(
            category="domain_analysis",
            confidence=0.9,
            rationale="replenishment",
        ),
        route=AgentRoute(
            mode="single_agent",
            agents=["replenishment"],
            requires_planning=False,
            requires_dag=False,
            rationale="single",
        ),
    )

    from packages.agent.orchestrator.models import AgentRoute, AskUserDecision, SessionIntent
    from tests.unit.helpers import MultiRoleModelRegistry, StructuredOutputFakeModel

    # domain_analysis intent requires AskUserDecision before routing to single_agent
    broadcaster_orchestrator_model = StructuredOutputFakeModel([
        SessionIntent(
            category="domain_analysis", confidence=0.9,
            rationale="replenishment", goal_text="check replenishment",
        ),
        AskUserDecision(needs_input=False, question=None, suggestions=None),
        AgentRoute(
            mode="single_agent", agents=["control"],
            requires_planning=False, requires_dag=False, rationale="single",
        ),
    ])
    broadcaster_registry = MultiRoleModelRegistry({"orchestrator": broadcaster_orchestrator_model})

    orchestrator = SessionOrchestrator(
        llm_client=_SequentialLLMClient(),
        tool_registry=create_tool_registry(),
        memory_store=StubMemoryStore(),
        sse_queue=_CaptureBroadcaster(),
        model_registry=broadcaster_registry,
    )

    with (
        patch(
            "packages.agent.orchestrator.session_orchestrator._run_agents_in_order",
            new=AsyncMock(return_value=[mock_specialist_result]),
        ),
        patch(
            "packages.agent.orchestrator.session_orchestrator._synthesize_response",
            new=AsyncMock(return_value=mock_session_response),
        ),
        patch(
            "packages.agent.orchestrator.session_orchestrator.DecisionSessionRepository",
            return_value=MagicMock(update_status=AsyncMock()),
        ),
    ):
        await orchestrator.run(uuid4(), SessionUserQuery(text="Check inventory status"))
        # Allow fire-and-forget tasks
        await asyncio.sleep(0)

    response_ready_events = [e for e in pushed_events if e.get("type") == "response_ready"]
    assert len(response_ready_events) >= 1, (
        f"Expected at least one response_ready event, got none. "
        f"All events: {[e.get('type') for e in pushed_events]}"
    )
    assert response_ready_events[0].get("mode") == "single_agent", (
        f"response_ready event must carry the execution mode, "
        f"got: {response_ready_events[0]}"
    )
