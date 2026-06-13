from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ContextPack(BaseModel):
    """Typed data structure specifying the minimal context for a specific SPEC use case.

    Each pack declares which tools are required, preferred, or prohibited for a
    given use-case question type (Q1–Q10), plus which skill files to load and a
    one-line routing hint injected at the top of the routing policy.

    Attributes:
        use_case_id:       "Q1"–"Q10" or "GENERIC" (fallback).
        intent:            Intent category matching _INTENT_TOOL_SUBSET keys.
        required_tools:    Tools that MUST be called — tool-routing assertion.
        preferred_tools:   Tools that SHOULD be called when relevant (not mandatory).
        prohibited_tools:  Tools that MUST NOT be called for this use case.
        skill_keys:        Skill file stems (without .md) from packages/knowledge/skills/.
        routing_hint:      One-line hint injected at the top of the routing policy.
    """

    model_config = ConfigDict(frozen=True)

    use_case_id: str
    intent: str
    required_tools: list[str]
    preferred_tools: list[str]
    prohibited_tools: list[str]
    skill_keys: list[str]
    routing_hint: str


# ---------------------------------------------------------------------------
# Per-use-case packs (Q1–Q10)
# ---------------------------------------------------------------------------
# Sources:
#   - required_tools / prohibited_tools: data/evals/spec10_golden_cases.yaml
#   - tool names validated against _INTENT_TOOL_SUBSET in
#     packages/agent/control/control_agent.py
#   - skill_keys: stem names (without .md) from packages/knowledge/skills/
# ---------------------------------------------------------------------------

USE_CASE_PACKS: dict[str, ContextPack] = {
    # ------------------------------------------------------------------
    # Q1 — Stockout risk enumeration
    # "Which products are at risk of stockout?"
    # ------------------------------------------------------------------
    "Q1": ContextPack(
        use_case_id="Q1",
        intent="supply_chain",
        required_tools=["list_stockout_risk"],
        preferred_tools=["calculate_stockout_risk"],
        prohibited_tools=["list_today_exceptions", "calculate_supply_gap"],
        skill_keys=["stockout_risk_analysis"],
        routing_hint=(
            "Call list_stockout_risk ONCE to enumerate at-risk SKUs across all products."
        ),
    ),
    # ------------------------------------------------------------------
    # Q2 — Excess inventory detection
    # "Which products have excess inventory?"
    # ------------------------------------------------------------------
    "Q2": ContextPack(
        use_case_id="Q2",
        intent="supply_chain",
        required_tools=["nl_query"],
        preferred_tools=["calculate_days_of_inventory"],
        prohibited_tools=["list_today_exceptions", "list_stockout_risk"],
        skill_keys=[],
        routing_hint=(
            "Use nl_query for bulk excess inventory detection; "
            "calculate_days_of_inventory for single-SKU."
        ),
    ),
    # ------------------------------------------------------------------
    # Q3 — Today's exceptions
    # "What exceptions require human judgment today?"
    # ------------------------------------------------------------------
    "Q3": ContextPack(
        use_case_id="Q3",
        intent="supply_chain",
        required_tools=["list_today_exceptions"],
        preferred_tools=[],
        prohibited_tools=[
            "list_stockout_risk",
            "get_delayed_supply_orders",
            "analyze_shipment_delay_causes",
        ],
        skill_keys=["exception_detection"],
        routing_hint=(
            "Call list_today_exceptions ONCE for the full daily exception picture."
        ),
    ),
    # ------------------------------------------------------------------
    # Q4 — Shipment delays / unshipped orders root-cause
    # "What is causing shipment delays or unshipped orders?"
    # ------------------------------------------------------------------
    "Q4": ContextPack(
        use_case_id="Q4",
        intent="supply_chain",
        required_tools=["analyze_shipment_delay_causes"],
        preferred_tools=["list_unshipped_orders"],
        prohibited_tools=["list_today_exceptions"],
        skill_keys=["shipment_delay_root_cause"],
        routing_hint=(
            "Call analyze_shipment_delay_causes ONCE for root-cause diagnosis."
        ),
    ),
    # ------------------------------------------------------------------
    # Q5 — Forecast gap analysis
    # "Why is there a gap between demand forecast and actual demand?"
    # ------------------------------------------------------------------
    "Q5": ContextPack(
        use_case_id="Q5",
        intent="domain_analysis",
        required_tools=["analyze_forecast_deviation"],
        preferred_tools=["evaluate_forecast_accuracy", "detect_demand_shift"],
        prohibited_tools=["list_stockout_risk", "list_today_exceptions"],
        skill_keys=[],
        routing_hint=(
            "Call analyze_forecast_deviation ONCE; "
            "pair with detect_demand_shift for customer/region attribution."
        ),
    ),
    # ------------------------------------------------------------------
    # Q6 — Forward supply shortage (next week / next month)
    # "Which products may face supply shortages next week or next month?"
    # ------------------------------------------------------------------
    "Q6": ContextPack(
        use_case_id="Q6",
        intent="supply_chain",
        required_tools=["nl_query"],
        preferred_tools=[],
        prohibited_tools=["list_stockout_risk", "calculate_supply_gap"],
        skill_keys=[],
        routing_hint=(
            "Use nl_query with CORRELATED SUBQUERIES for forward supply adequacy "
            "— NOT list_stockout_risk (on-hand only)."
        ),
    ),
    # ------------------------------------------------------------------
    # Q7 — Production plan adjustment
    # "Which products require production plan adjustments?"
    # ------------------------------------------------------------------
    "Q7": ContextPack(
        use_case_id="Q7",
        intent="domain_analysis",
        required_tools=["analyze_production_plan_gap"],
        preferred_tools=[],
        prohibited_tools=["list_today_exceptions", "list_stockout_risk"],
        skill_keys=[],
        routing_hint=(
            "Call analyze_production_plan_gap ONCE for plan adjustment analysis."
        ),
    ),
    # ------------------------------------------------------------------
    # Q8 — Purchase / order timing optimization
    # "Which materials or items should be purchased earlier or later?"
    # ------------------------------------------------------------------
    "Q8": ContextPack(
        use_case_id="Q8",
        intent="domain_analysis",
        required_tools=["analyze_supply_order_timing"],
        preferred_tools=[],
        prohibited_tools=["get_delayed_supply_orders"],
        skill_keys=[],
        routing_hint=(
            "Call analyze_supply_order_timing ONCE — "
            "get_delayed_supply_orders answers 'what is late by status', "
            "not 'what should arrive sooner/later'."
        ),
    ),
    # ------------------------------------------------------------------
    # Q9 — Demand shift by customer / region
    # "Are there demand changes by customer or region?"
    # ------------------------------------------------------------------
    "Q9": ContextPack(
        use_case_id="Q9",
        intent="domain_analysis",
        required_tools=["detect_demand_shift"],
        preferred_tools=[],
        prohibited_tools=["segment_demand", "compare_demand_periods"],
        skill_keys=[],
        routing_hint=(
            "Call detect_demand_shift ONCE for customer/region demand changes "
            "— segment_demand and compare_demand_periods are SKU-axis only."
        ),
    ),
    # ------------------------------------------------------------------
    # Q10 — Binding constraint / bottleneck impact
    # "Which constraint is having the biggest negative impact on sales or profit?"
    # ------------------------------------------------------------------
    "Q10": ContextPack(
        use_case_id="Q10",
        intent="domain_analysis",
        required_tools=["identify_binding_constraint"],
        preferred_tools=[],
        prohibited_tools=[],
        skill_keys=[],
        routing_hint=(
            "Call identify_binding_constraint ONCE for bottleneck impact analysis."
        ),
    ),
}

# ---------------------------------------------------------------------------
# Fallback pack — used when no specific use case is matched
# ---------------------------------------------------------------------------

GENERIC_PACK: ContextPack = ContextPack(
    use_case_id="GENERIC",
    intent="supply_chain",
    required_tools=[],
    preferred_tools=[],
    prohibited_tools=[],
    skill_keys=[],
    routing_hint="",
)
