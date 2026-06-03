from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

_MAX_CLARIFICATION_ROUNDS = 2


def needs_clarification(intent_category: str, goal_text: str | None) -> bool:
    """True when the intent is 'chat' with no discernible goal."""
    return intent_category == "chat" and not goal_text


def build_clarification_event(session_id: UUID, round_number: int) -> dict[str, Any]:
    """Build the SSE event payload for clarification_required."""
    return {
        "type": "clarification_required",
        "session_id": str(session_id),
        "round": round_number,
        "message": (
            "Could you clarify your goal? "
            "For example: what supply chain area are you asking about, "
            "and what decision or analysis do you need?"
        ),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def clarification_exhausted(round_number: int) -> bool:
    """True when we've used all clarification rounds — fall back to direct_chat."""
    return round_number > _MAX_CLARIFICATION_ROUNDS
