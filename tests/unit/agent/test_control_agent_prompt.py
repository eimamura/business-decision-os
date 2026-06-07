"""T-392: Unit tests for _SYSTEM_PROMPT content in ControlAgent.

Asserts that the two behavioural guard phrases added in P60 B-01 are present
in the prompt so that regressions to the text are caught immediately.
"""
from __future__ import annotations

from packages.agent.control.control_agent import _SYSTEM_PROMPT


def test_system_prompt_contains_never_call_same_tool_twice() -> None:
    """_SYSTEM_PROMPT must include the duplicate-tool hard-stop instruction."""
    assert "Never call the same tool twice" in _SYSTEM_PROMPT, (
        "_SYSTEM_PROMPT is missing the 'Never call the same tool twice' guard phrase"
    )


def test_system_prompt_contains_get_delayed_supply_orders() -> None:
    """_SYSTEM_PROMPT must reference get_delayed_supply_orders for exception/delay questions."""
    assert "get_delayed_supply_orders" in _SYSTEM_PROMPT, (
        "_SYSTEM_PROMPT is missing the 'get_delayed_supply_orders' tool reference"
    )
