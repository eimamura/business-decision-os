from __future__ import annotations

from packages.agent.control.control_agent import _INTENT_TOOL_SUBSET
from packages.agent.orchestrator.intent_registry import INTENT_REGISTRY
from packages.tools import create_tool_registry


def test_intent_tool_subset_keys_all_in_intent_registry() -> None:
    """Every key in _INTENT_TOOL_SUBSET must be a registered intent category."""
    unknown_keys = set(_INTENT_TOOL_SUBSET.keys()) - set(INTENT_REGISTRY.keys())
    assert unknown_keys == set(), (
        f"_INTENT_TOOL_SUBSET contains keys not in INTENT_REGISTRY: {unknown_keys}"
    )


def test_intent_tool_subset_tool_names_all_registered() -> None:
    """Every tool name in every subset list must exist in the tool registry."""
    registered_names = set(create_tool_registry()._tools.keys())
    unknown_tools: dict[str, list[str]] = {}
    for intent, tools in _INTENT_TOOL_SUBSET.items():
        missing = [t for t in tools if t not in registered_names]
        if missing:
            unknown_tools[intent] = missing
    assert unknown_tools == {}, (
        f"_INTENT_TOOL_SUBSET references unregistered tool names: {unknown_tools}"
    )


def test_intent_tool_subset_supply_chain_list_is_unchanged() -> None:
    """The supply_chain subset must exactly match its specification (updated in P87-T-545)."""
    expected = [
        "nl_query",
        "list_today_exceptions",
        "list_stockout_risk",
        "list_unshipped_orders",
        "analyze_shipment_delay_causes",
        "get_delayed_supply_orders",
        "get_open_supply_orders",
        "calculate_supply_gap",
        "analyze_supply_lead_time",
        "calculate_days_of_inventory",
        "analyze_supply_risk",
        "calculate_stockout_risk",
        "calculate_stockout_cost_impact",
        "calculate_expedite_cost",
    ]
    assert _INTENT_TOOL_SUBSET["supply_chain"] == expected


def test_detect_demand_shift_in_domain_analysis() -> None:
    """detect_demand_shift must be present in the domain_analysis intent subset (P88-T-550)."""
    assert "detect_demand_shift" in _INTENT_TOOL_SUBSET["domain_analysis"], (
        "detect_demand_shift must be in domain_analysis for customer/region Q9 questions"
    )


def test_detect_demand_shift_in_cross_domain_analysis() -> None:
    """detect_demand_shift must be present in the cross_domain_analysis intent subset (P88-T-550)."""
    assert "detect_demand_shift" in _INTENT_TOOL_SUBSET["cross_domain_analysis"], (
        "detect_demand_shift must be in cross_domain_analysis for customer/region Q9 questions"
    )


def test_detect_demand_shift_in_decision_support() -> None:
    """detect_demand_shift must be present in the decision_support intent subset (P88-T-550)."""
    assert "detect_demand_shift" in _INTENT_TOOL_SUBSET["decision_support"], (
        "detect_demand_shift must be in decision_support for customer/region Q9 questions"
    )


def test_detect_demand_shift_not_in_supply_chain() -> None:
    """detect_demand_shift should not be in supply_chain subset (P88-T-550 scope)."""
    assert "detect_demand_shift" not in _INTENT_TOOL_SUBSET["supply_chain"], (
        "detect_demand_shift is not a supply-chain execution tool; keep supply_chain focused"
    )
