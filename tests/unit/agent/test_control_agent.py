from __future__ import annotations

from unittest.mock import MagicMock

from packages.agent.control.control_agent import ControlAgent, _SYSTEM_PROMPT
from packages.agent.orchestrator.intent_registry import INTENT_REGISTRY
from packages.tools.base import _ROLE_TOOL_ALLOWLIST


# ---------------------------------------------------------------------------
# T-278 — ControlAgent instantiation and _SYSTEM_PROMPT content
# ---------------------------------------------------------------------------


def test_control_agent_instantiates_with_correct_role() -> None:
    agent = ControlAgent(
        llm_client=MagicMock(),
        tool_registry=MagicMock(),
    )
    assert agent.role == "control"


def test_control_agent_instantiates_with_correct_name() -> None:
    agent = ControlAgent(
        llm_client=MagicMock(),
        tool_registry=MagicMock(),
    )
    assert agent.name == "ControlAgent"


def test_control_agent_system_prompt_references_demand() -> None:
    assert "demand" in _SYSTEM_PROMPT.lower()


def test_control_agent_system_prompt_references_inventory() -> None:
    assert "inventory" in _SYSTEM_PROMPT.lower()


def test_control_agent_system_prompt_references_supply() -> None:
    assert "supply" in _SYSTEM_PROMPT.lower()


def test_control_agent_system_prompt_references_logistics() -> None:
    assert "logistics" in _SYSTEM_PROMPT.lower()


def test_control_agent_system_prompt_references_finance() -> None:
    assert "finance" in _SYSTEM_PROMPT.lower()


# ---------------------------------------------------------------------------
# T-279 — supply_chain routing and tool allowlist
# ---------------------------------------------------------------------------


def test_intent_registry_contains_supply_chain() -> None:
    assert "supply_chain" in INTENT_REGISTRY


def test_supply_chain_intent_routes_to_control_agent() -> None:
    assert INTENT_REGISTRY["supply_chain"].allowed_agent_roles == ["control"]


def test_control_role_present_in_tool_allowlist() -> None:
    assert "control" in _ROLE_TOOL_ALLOWLIST


def test_control_tool_allowlist_contains_sql_query() -> None:
    assert "sql_query" in _ROLE_TOOL_ALLOWLIST["control"]


def test_control_tool_allowlist_contains_calculate_days_of_inventory() -> None:
    assert "calculate_days_of_inventory" in _ROLE_TOOL_ALLOWLIST["control"]


def test_control_tool_allowlist_contains_calculate_supply_gap() -> None:
    assert "calculate_supply_gap" in _ROLE_TOOL_ALLOWLIST["control"]
