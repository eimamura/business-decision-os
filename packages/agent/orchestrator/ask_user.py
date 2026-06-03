from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

_ANALYTICAL_INTENTS = frozenset({
    "domain_analysis",
    "cross_domain_analysis",
    "decision_support",
})


def is_analytical_intent(category: str) -> bool:
    return category in _ANALYTICAL_INTENTS


def build_ask_user_event(
    session_id: UUID,
    question: str,
    ask_user_id: str,
    suggestions: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "type": "ask_user_required",
        "session_id": str(session_id),
        "ask_user_id": ask_user_id,
        "question": question,
        "suggestions": suggestions or [],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
