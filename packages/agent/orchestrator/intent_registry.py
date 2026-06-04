from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class IntentConfig:
    description: str
    plan_prompt: str
    allowed_agent_roles: list[str] = field(default_factory=list)
    max_tool_calls: int = 10
    skip_tool_loop: bool = False


INTENT_REGISTRY: dict[str, IntentConfig] = {
    "chat": IntentConfig(
        description="Greeting, chitchat, or off-topic",
        plan_prompt="",
        allowed_agent_roles=[],
        max_tool_calls=0,
        skip_tool_loop=True,
    ),
    "lookup": IntentConfig(
        description="Factual supply-chain question or data lookup",
        plan_prompt="Answer the user's factual question using available data tools.",
        allowed_agent_roles=[
            "data_engineer",
            "demand",
            "finance_impact",
            "inventory",
            "replenishment",
            "procurement",
            "supplier",
            "production",
            "logistics",
            "supply_planning",
        ],
        max_tool_calls=5,
    ),
    "domain_analysis": IntentConfig(
        description="Single domain needs analysis",
        plan_prompt=(
            "Analyze the requested domain using appropriate analytical tools. "
            "Provide data-backed insights."
        ),
        allowed_agent_roles=[
            "demand",
            "finance_impact",
            "inventory",
            "replenishment",
            "procurement",
            "supplier",
            "production",
            "logistics",
            "supply_planning",
        ],
        max_tool_calls=10,
    ),
    "cross_domain_analysis": IntentConfig(
        description="Multiple domains or anomaly/root-cause analysis",
        plan_prompt=(
            "Coordinate analysis across multiple domains. "
            "Identify anomalies, root causes, and cross-domain effects."
        ),
        allowed_agent_roles=[
            "data_engineer",
            "demand",
            "finance_impact",
            "inventory",
            "replenishment",
            "procurement",
            "supplier",
            "production",
            "logistics",
            "supply_planning",
            "anomaly_detector",
        ],
        max_tool_calls=15,
    ),
    "decision_support": IntentConfig(
        description=(
            "Explicit recommendation, optimization, scenario comparison, "
            "or approval-oriented decision"
        ),
        plan_prompt=(
            "Generate ranked decision candidates with KPI scores, "
            "risk assessment, and tradeoff explanation."
        ),
        allowed_agent_roles=[
            "demand",
            "finance_impact",
            "inventory",
            "replenishment",
            "simulation_optimizer",
            "evaluator",
            "data_engineer",
        ],
        max_tool_calls=20,
    ),
    "sop": IntentConfig(
        description=(
            "Full S&OP cycle: demand forecast → inventory position → supply feasibility "
            "→ financial impact → integrated recommendation"
        ),
        plan_prompt=(
            "Run a full S&OP analysis in sequential order:\n"
            "1. demand agent — confirm demand forecast, trend, and anomalies\n"
            "2. inventory agent — assess current inventory position, stockout risk, "
            "days of inventory, and available-to-promise\n"
            "3. supply_planning agent — evaluate supply gap, open orders, lead time risk, "
            "and supplier concentration\n"
            "4. finance_impact agent — compare cost scenarios "
            "(do_nothing, full_expedite, partial_fulfill) and identify lowest-cost option\n"
            "5. sop agent — synthesize all specialist outputs into a final S&OP "
            "recommendation with decision, risk, and next actions\n\n"
            "Each agent must complete before the next runs. "
            "The sop agent runs last and owns the final integrated recommendation."
        ),
        allowed_agent_roles=[
            "demand",
            "inventory",
            "supply_planning",
            "finance_impact",
            "sop",
        ],
        max_tool_calls=30,
    ),
}


def get_intent_config(category: str) -> IntentConfig:
    """Return the IntentConfig for the given category.

    Raises KeyError if category is not registered.
    """
    if category not in INTENT_REGISTRY:
        raise KeyError(f"Unknown intent category: {category!r}")
    return INTENT_REGISTRY[category]
