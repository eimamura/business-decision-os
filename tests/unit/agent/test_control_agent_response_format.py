"""T-415: Assert _SYSTEM_PROMPT contains the required response-format markers.

Added in P64 B-01 (T-407): ControlAgent._SYSTEM_PROMPT must include all four
structured-output anchors so that regressions to the prompt text are caught
immediately.
"""
from __future__ import annotations

from packages.agent.control.control_agent import _SYSTEM_PROMPT


def test_system_prompt_contains_situation_marker() -> None:
    """_SYSTEM_PROMPT must include the Situation anchor."""
    assert "**Situation:**" in _SYSTEM_PROMPT, (
        "_SYSTEM_PROMPT is missing the '**Situation:**' response-format marker"
    )


def test_system_prompt_contains_root_cause_marker() -> None:
    """_SYSTEM_PROMPT must include the Root Cause anchor."""
    assert "**Root Cause:**" in _SYSTEM_PROMPT, (
        "_SYSTEM_PROMPT is missing the '**Root Cause:**' response-format marker"
    )


def test_system_prompt_contains_recommended_actions_marker() -> None:
    """_SYSTEM_PROMPT must include the Recommended Actions anchor."""
    assert "**Recommended Actions:**" in _SYSTEM_PROMPT, (
        "_SYSTEM_PROMPT is missing the '**Recommended Actions:**' response-format marker"
    )


def test_system_prompt_contains_confidence_level_marker() -> None:
    """_SYSTEM_PROMPT must include the Confidence Level anchor."""
    assert "**Confidence Level:**" in _SYSTEM_PROMPT, (
        "_SYSTEM_PROMPT is missing the '**Confidence Level:**' response-format marker"
    )
