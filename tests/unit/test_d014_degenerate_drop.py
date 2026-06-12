"""D-014 — Drop degenerate first-invocation segment in goal-refinement (unit tests).

When goal-refinement runs a second agent invocation that produces a non-degenerate
reply, the response assembly must discard the degenerate first-segment text.

Tests:
  T-D014-a  _is_degenerate_reply returns True for known apology/refusal patterns
  T-D014-b  _is_degenerate_reply returns True for very short replies
  T-D014-c  _is_degenerate_reply returns False for a grounded answer
  T-D014-d  _node_run_sequential emits a text_reset SSE event on refinement pass
            when the previous result was degenerate
  T-D014-e  _node_run_sequential does NOT emit text_reset when the previous result
            was grounded (non-degenerate)
  T-D014-f  _node_run_sequential does NOT emit text_reset on the first pass
            (refine_count == 0 regardless of result content)
"""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from packages.agent.orchestrator.models import (
    AgentRoute,
    SessionIntent,
    SessionResponse,
    SessionUserQuery,
)
from packages.agent.orchestrator.session_orchestrator import SessionOrchestrator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_orchestrator(sse_queue: asyncio.Queue | None = None) -> SessionOrchestrator:
    """Create a minimal SessionOrchestrator with mocked dependencies."""
    orchestrator = SessionOrchestrator(
        llm_client=MagicMock(),
        tool_registry=MagicMock(),
        memory_store=MagicMock(),
        sse_queue=sse_queue,
    )
    return orchestrator


def _make_intent(category: str = "supply_chain") -> SessionIntent:
    return SessionIntent(
        category=category,
        confidence=0.9,
        rationale="test",
        goal_text="test goal",
    )


def _make_route() -> AgentRoute:
    return AgentRoute(
        mode="single_agent",
        agents=["control"],
        rationale="test",
    )


def _make_session_response(reply: str) -> SessionResponse:
    return SessionResponse(
        mode="single_agent",
        reply=reply,
        intent=_make_intent(),
        route=_make_route(),
    )


def _make_orchestrator_state(
    refine_count: int,
    prev_reply: str | None = None,
) -> dict[str, Any]:
    from packages.agent.orchestrator.models import SessionUserQuery

    prev_result = _make_session_response(prev_reply) if prev_reply is not None else None
    return {
        "session_id": str(uuid4()),
        "query": SessionUserQuery(text="test query").model_dump(),
        "intent": _make_intent(),
        "route": _make_route(),
        "result": prev_result,
        "error": None,
        "ask_user_id": None,
        "ask_user_question": None,
        "ask_user_answer": None,
        "goal": {"goal_text": "test", "success_criteria": []},
        "goal_eval": None,
        "refine_count": refine_count,
        "refinement_feedback": None,
    }


# ---------------------------------------------------------------------------
# T-D014-a: _is_degenerate_reply detects known apology/refusal patterns
# ---------------------------------------------------------------------------


def test_is_degenerate_reply_apology_patterns() -> None:
    """_is_degenerate_reply must return True for common degenerate patterns."""
    orch = _make_orchestrator()
    degenerate_replies = [
        "I'm sorry, but I don't have that information.",
        "I am sorry, I cannot provide this.",
        "I don't have access to your specific inventory data.",
        "Cannot provide information regarding specific product shortages.",
        "Data is currently unavailable. Please try again.",
        "Please rephrase your question.",
        "Désolé, je ne dispose pas des informations.",
    ]
    for reply in degenerate_replies:
        assert orch._is_degenerate_reply(reply), (
            f"_is_degenerate_reply returned False for degenerate reply: {reply!r}"
        )


# ---------------------------------------------------------------------------
# T-D014-b: _is_degenerate_reply detects very short replies
# ---------------------------------------------------------------------------


def test_is_degenerate_reply_short_text() -> None:
    """_is_degenerate_reply must return True when the reply is shorter than
    _DEGENERATE_REPLY_MIN_LEN characters."""
    orch = _make_orchestrator()
    # Below the min length
    assert orch._is_degenerate_reply(""), "empty string should be degenerate"
    assert orch._is_degenerate_reply("Based"), "5-char reply should be degenerate"
    assert orch._is_degenerate_reply("OK."), "3-char reply should be degenerate"


# ---------------------------------------------------------------------------
# T-D014-c: _is_degenerate_reply passes grounded answers
# ---------------------------------------------------------------------------


def test_is_degenerate_reply_grounded_answer() -> None:
    """_is_degenerate_reply must return False for a well-formed grounded reply."""
    orch = _make_orchestrator()
    grounded = (
        "Based on current stock levels, SKU-001 (Industrial Bearing A) is at critical "
        "stockout risk with only 19 units on hand and a projected stockout date of "
        "2026-06-13. SKU-002 is also critical. Recommended action: expedite supply orders."
    )
    assert not orch._is_degenerate_reply(grounded), (
        f"_is_degenerate_reply incorrectly flagged a grounded reply as degenerate: {grounded!r}"
    )


# ---------------------------------------------------------------------------
# T-D014-d: text_reset emitted when refinement pass has degenerate previous result
# ---------------------------------------------------------------------------


async def test_node_run_sequential_emits_text_reset_for_degenerate_first_result() -> None:
    """On a refinement pass (refine_count > 0) where the previous result is degenerate,
    _node_run_sequential must push a text_reset SSE event to the queue BEFORE synthesis.
    """
    sse_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    orch = _make_orchestrator(sse_queue=sse_queue)

    degenerate_reply = "I'm sorry, but I don't have that information. Please try again."
    state = _make_orchestrator_state(refine_count=1, prev_reply=degenerate_reply)

    grounded_reply = "SKU-001 is at critical risk. Recommend expediting supply orders."
    grounded_response = _make_session_response(grounded_reply)

    with (
        patch(
            "packages.agent.orchestrator.session_orchestrator._run_agents_in_order",
            new=AsyncMock(return_value={}),
        ),
        patch(
            "packages.agent.orchestrator.session_orchestrator._synthesize_response",
            new=AsyncMock(return_value=grounded_response),
        ),
    ):
        await orch._node_run_sequential(state, {})  # type: ignore[arg-type]

    # Collect all events emitted to the queue
    emitted: list[dict[str, Any]] = []
    while not sse_queue.empty():
        emitted.append(sse_queue.get_nowait())

    reset_events = [e for e in emitted if e.get("type") == "text_reset"]
    assert reset_events, (
        f"Expected a text_reset SSE event on refinement pass with degenerate first reply, "
        f"but got events: {[e.get('type') for e in emitted]}"
    )
    assert reset_events[0]["reason"] == "degenerate_first_invocation", (
        f"text_reset event has unexpected reason: {reset_events[0]}"
    )


# ---------------------------------------------------------------------------
# T-D014-e: NO text_reset when previous result was grounded
# ---------------------------------------------------------------------------


async def test_node_run_sequential_no_text_reset_for_grounded_first_result() -> None:
    """On a refinement pass where the previous result was grounded (non-degenerate),
    _node_run_sequential must NOT emit a text_reset SSE event.
    """
    sse_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    orch = _make_orchestrator(sse_queue=sse_queue)

    grounded_first_reply = (
        "Based on data, SKU-001 is at critical stockout risk with projected stockout "
        "on 2026-06-13. Recommend expediting supply orders from SUP-002 immediately."
    )
    state = _make_orchestrator_state(refine_count=1, prev_reply=grounded_first_reply)

    second_response = _make_session_response("Additional detail: SKU-002 also critical.")

    with (
        patch(
            "packages.agent.orchestrator.session_orchestrator._run_agents_in_order",
            new=AsyncMock(return_value={}),
        ),
        patch(
            "packages.agent.orchestrator.session_orchestrator._synthesize_response",
            new=AsyncMock(return_value=second_response),
        ),
    ):
        await orch._node_run_sequential(state, {})  # type: ignore[arg-type]

    emitted: list[dict[str, Any]] = []
    while not sse_queue.empty():
        emitted.append(sse_queue.get_nowait())

    reset_events = [e for e in emitted if e.get("type") == "text_reset"]
    assert not reset_events, (
        f"Expected no text_reset event for grounded first reply, but got: {reset_events}"
    )


# ---------------------------------------------------------------------------
# T-D014-f: NO text_reset on first pass (refine_count == 0)
# ---------------------------------------------------------------------------


async def test_node_run_sequential_no_text_reset_on_first_pass() -> None:
    """_node_run_sequential must NOT emit text_reset when refine_count == 0
    (i.e., this is the first invocation, not a refinement pass).
    """
    sse_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    orch = _make_orchestrator(sse_queue=sse_queue)

    # refine_count=0 — first pass, no previous result
    state = _make_orchestrator_state(refine_count=0, prev_reply=None)

    response = _make_session_response("SKU-001 critical; recommend expedite.")

    with (
        patch(
            "packages.agent.orchestrator.session_orchestrator._run_agents_in_order",
            new=AsyncMock(return_value={}),
        ),
        patch(
            "packages.agent.orchestrator.session_orchestrator._synthesize_response",
            new=AsyncMock(return_value=response),
        ),
    ):
        await orch._node_run_sequential(state, {})  # type: ignore[arg-type]

    emitted: list[dict[str, Any]] = []
    while not sse_queue.empty():
        emitted.append(sse_queue.get_nowait())

    reset_events = [e for e in emitted if e.get("type") == "text_reset"]
    assert not reset_events, (
        f"Expected no text_reset on first pass (refine_count=0), got: {reset_events}"
    )
