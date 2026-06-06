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
        allowed_agent_roles=["control"],
        max_tool_calls=5,
    ),
    "domain_analysis": IntentConfig(
        description="Single domain needs analysis",
        plan_prompt=(
            "Analyze the requested domain using appropriate analytical tools. "
            "Provide data-backed insights."
        ),
        allowed_agent_roles=["control"],
        max_tool_calls=10,
    ),
    "cross_domain_analysis": IntentConfig(
        description="Multiple domains or anomaly/root-cause analysis",
        plan_prompt=(
            "Coordinate analysis across multiple domains. "
            "Identify anomalies, root causes, and cross-domain effects."
        ),
        allowed_agent_roles=["control"],
        max_tool_calls=15,
    ),
    "supply_chain": IntentConfig(
        description=(
            "Cross-domain supply chain query — stockout risk, exceptions, "
            "shipment delays, supply gaps, inventory positioning, or action priorities"
        ),
        plan_prompt=(
            "Use the ControlAgent with its full cross-domain tool access to analyze "
            "the supply chain situation and produce a decision-ready answer."
        ),
        allowed_agent_roles=["control"],
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
        allowed_agent_roles=["control"],
        max_tool_calls=20,
    ),
}


def get_intent_config(category: str) -> IntentConfig:
    """Return the IntentConfig for the given category.

    Raises KeyError if category is not registered.
    """
    if category not in INTENT_REGISTRY:
        raise KeyError(f"Unknown intent category: {category!r}")
    return INTENT_REGISTRY[category]
