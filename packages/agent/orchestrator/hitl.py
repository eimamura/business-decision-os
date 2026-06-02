from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class HITLPause(Exception):
    """Raised by AgentRuntime when a hitl tool is about to execute.

    Carries enough information for the orchestrator to emit a ``session_paused``
    event and return a structured ``SessionResponse`` without executing the tool.
    """

    approval_id: str
    tool_name: str
    tool_input: dict[str, Any]
