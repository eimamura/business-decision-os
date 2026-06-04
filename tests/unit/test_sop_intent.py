from __future__ import annotations

from packages.agent.orchestrator.intent_registry import INTENT_REGISTRY, get_intent_config


def test_sop_intent_registered() -> None:
    assert "sop" in INTENT_REGISTRY


def test_sop_intent_allowed_roles_contains_all_five() -> None:
    config = get_intent_config("sop")
    expected_roles = ["demand", "inventory", "supply_planning", "finance_impact", "sop"]
    for role in expected_roles:
        assert role in config.allowed_agent_roles, (
            f"Expected role '{role}' in sop intent allowed_agent_roles"
        )


def test_sop_intent_max_tool_calls_is_sufficient() -> None:
    config = get_intent_config("sop")
    assert config.max_tool_calls >= 25
