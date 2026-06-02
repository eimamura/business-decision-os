from __future__ import annotations

from uuid import UUID

from packages.agent.orchestrator.clarification import (
    build_clarification_event,
    clarification_exhausted,
    needs_clarification,
)

_SESSION_ID = UUID("12345678-1234-5678-1234-567812345678")


def test_needs_clarification_chat_no_goal() -> None:
    assert needs_clarification("chat", None) is True


def test_needs_clarification_chat_with_goal() -> None:
    assert needs_clarification("chat", "reduce inventory costs") is False


def test_needs_clarification_non_chat() -> None:
    for category in ("lookup", "domain_analysis", "cross_domain_analysis", "decision_support"):
        assert needs_clarification(category, None) is False, f"expected False for {category!r}"


def test_clarification_exhausted_at_round_3() -> None:
    assert clarification_exhausted(3) is True


def test_clarification_not_exhausted_at_round_2() -> None:
    assert clarification_exhausted(2) is False


def test_build_clarification_event_type() -> None:
    event = build_clarification_event(_SESSION_ID, 1)
    assert event["type"] == "clarification_required"


def test_build_clarification_event_session_id() -> None:
    event = build_clarification_event(_SESSION_ID, 1)
    assert event["session_id"] == str(_SESSION_ID)


def test_build_clarification_event_round() -> None:
    event = build_clarification_event(_SESSION_ID, 2)
    assert event["round"] == 2


def test_build_clarification_event_message_present() -> None:
    event = build_clarification_event(_SESSION_ID, 1)
    assert isinstance(event["message"], str)
    assert len(event["message"]) > 0
