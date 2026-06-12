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
    """The supply_chain subset must exactly match its specification (updated in P94-T-578)."""
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
        "analyze_forecast_deviation",
        "identify_binding_constraint",
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


def test_analyze_production_plan_gap_in_domain_analysis() -> None:
    """analyze_production_plan_gap must be present in domain_analysis subset (P89-T-559)."""
    assert "analyze_production_plan_gap" in _INTENT_TOOL_SUBSET["domain_analysis"], (
        "analyze_production_plan_gap must be in domain_analysis for SPEC Q7 questions"
    )


def test_analyze_production_plan_gap_in_cross_domain_analysis() -> None:
    """analyze_production_plan_gap must be present in cross_domain_analysis subset (P89-T-559)."""
    assert "analyze_production_plan_gap" in _INTENT_TOOL_SUBSET["cross_domain_analysis"], (
        "analyze_production_plan_gap must be in cross_domain_analysis for SPEC Q7 questions"
    )


def test_analyze_production_plan_gap_in_decision_support() -> None:
    """analyze_production_plan_gap must be present in decision_support subset (P89-T-559)."""
    assert "analyze_production_plan_gap" in _INTENT_TOOL_SUBSET["decision_support"], (
        "analyze_production_plan_gap must be in decision_support for SPEC Q7 questions"
    )


def test_identify_binding_constraint_in_domain_analysis() -> None:
    """identify_binding_constraint must be present in domain_analysis subset (P89-T-559)."""
    assert "identify_binding_constraint" in _INTENT_TOOL_SUBSET["domain_analysis"], (
        "identify_binding_constraint must be in domain_analysis for SPEC Q10 questions"
    )


def test_identify_binding_constraint_in_cross_domain_analysis() -> None:
    """identify_binding_constraint must be present in cross_domain_analysis subset (P89-T-559)."""
    assert "identify_binding_constraint" in _INTENT_TOOL_SUBSET["cross_domain_analysis"], (
        "identify_binding_constraint must be in cross_domain_analysis for SPEC Q10 questions"
    )


def test_identify_binding_constraint_in_decision_support() -> None:
    """identify_binding_constraint must be present in decision_support subset (P89-T-559)."""
    assert "identify_binding_constraint" in _INTENT_TOOL_SUBSET["decision_support"], (
        "identify_binding_constraint must be in decision_support for SPEC Q10 questions"
    )


def test_identify_binding_constraint_in_supply_chain() -> None:
    """identify_binding_constraint must be present in supply_chain subset (P89-T-559)."""
    assert "identify_binding_constraint" in _INTENT_TOOL_SUBSET["supply_chain"], (
        "identify_binding_constraint must be in supply_chain for constraint-impact questions"
    )


def test_analyze_forecast_deviation_in_supply_chain() -> None:
    """analyze_forecast_deviation must be present in supply_chain subset (P94-T-578)."""
    assert "analyze_forecast_deviation" in _INTENT_TOOL_SUBSET["supply_chain"], (
        "analyze_forecast_deviation must be in supply_chain for SPEC Q5 gap questions"
    )


def test_analyze_forecast_deviation_in_domain_analysis() -> None:
    """analyze_forecast_deviation must be present in domain_analysis subset (P94-T-578)."""
    assert "analyze_forecast_deviation" in _INTENT_TOOL_SUBSET["domain_analysis"], (
        "analyze_forecast_deviation must be in domain_analysis for SPEC Q5 questions"
    )


def test_analyze_forecast_deviation_in_cross_domain_analysis() -> None:
    """analyze_forecast_deviation must be present in cross_domain_analysis subset (P94-T-578)."""
    assert "analyze_forecast_deviation" in _INTENT_TOOL_SUBSET["cross_domain_analysis"], (
        "analyze_forecast_deviation must be in cross_domain_analysis for SPEC Q5 questions"
    )


def test_analyze_forecast_deviation_in_decision_support() -> None:
    """analyze_forecast_deviation must be present in decision_support subset (P94-T-578)."""
    assert "analyze_forecast_deviation" in _INTENT_TOOL_SUBSET["decision_support"], (
        "analyze_forecast_deviation must be in decision_support for SPEC Q5 questions"
    )
