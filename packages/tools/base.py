from __future__ import annotations

from typing import Any, Literal, Protocol
from uuid import UUID

from pydantic import BaseModel

_ROLE_TOOL_ALLOWLIST: dict[str, list[str]] = {
    "orchestrator": ["job_dispatch"],
    "data_engineer": [
        "nl_query", "data_catalog_search",
        "table_schema_reader", "data_quality_checker",
    ],
    "simulation_optimizer": ["simulate_inventory", "optimize_replenishment", "job_dispatch"],
    "evaluator": ["evaluate_candidates", "write_audit_log"],
    "anomaly_detector": [
        "nl_query", "data_catalog_search",
        "table_schema_reader", "data_quality_checker",
    ],
    "demand": [
        "nl_query", "forecast", "train_forecast",
        "profile_demand_data", "analyze_demand_trend",
        "evaluate_forecast_accuracy", "detect_demand_anomalies",
        "analyze_seasonality", "analyze_demand_drivers",
        "segment_demand", "compare_demand_periods",
    ],
    "supply_planning": [
        "nl_query",
        "get_open_supply_orders", "calculate_supply_gap",
        "analyze_supply_lead_time", "calculate_days_of_supply",
        "analyze_supply_risk",
    ],
    "finance_impact": [
        "nl_query",
        "calculate_holding_cost_impact", "calculate_stockout_cost_impact",
        "calculate_expedite_cost", "compare_cost_scenarios",
    ],
    "inventory": [
        "nl_query", "simulate_inventory",
        "calculate_days_of_inventory", "calculate_stockout_risk",
        "list_stockout_risk",
        "calculate_excess_inventory_risk", "get_available_to_promise",
    ],
    "replenishment": ["nl_query", "simulate_inventory", "optimize_replenishment"],
    "procurement": ["nl_query"],
    "supplier": ["nl_query"],
    "production": ["nl_query"],
    "logistics": ["nl_query"],
    "sop": ["nl_query"],
    "control": [
        "nl_query",
        "profile_demand_data", "analyze_demand_trend",
        "evaluate_forecast_accuracy", "detect_demand_anomalies",
        "analyze_seasonality", "analyze_demand_drivers",
        "segment_demand", "compare_demand_periods",
        "get_delayed_supply_orders", "calculate_supply_gap", "get_open_supply_orders",
        "analyze_supply_lead_time", "calculate_days_of_supply",
        "analyze_supply_risk",
        "calculate_holding_cost_impact", "calculate_stockout_cost_impact",
        "calculate_expedite_cost", "compare_cost_scenarios",
        "calculate_days_of_inventory", "calculate_stockout_risk",
        "list_stockout_risk",
        "calculate_excess_inventory_risk", "get_available_to_promise",
    ],
}


class ToolContext(BaseModel):
    session_id: UUID
    agent_step_id: UUID
    specialist_role: str  # broad str; SpecialistRole Literal trimmed to ["orchestrator", "control"]
    actor: str
    correlation_id: UUID
    user_role: str = "analyst"


class ToolResult(BaseModel):
    output: dict[str, Any]
    audit_payload: dict[str, Any]


class Tool(Protocol):
    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    safety_level: Literal["read_only", "write", "hitl"]

    async def handle(self, input: dict[str, Any], ctx: ToolContext) -> ToolResult: ...


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list_for_role(self, role: str) -> list[Tool]:
        allowed = _ROLE_TOOL_ALLOWLIST.get(role)
        if allowed is None:
            return list(self._tools.values())
        if not allowed:
            return []
        return [t for name, t in self._tools.items() if name in allowed]

    def filter_for_user_role(self, user_role: str, tools: list[Tool]) -> list[Tool]:
        """Layer 1: filter tools by the human user's role.

        - ``"analyst"``  → read_only only
        - ``"manager"``  → read_only + hitl
        - ``"admin"``    → all tools (no filter)
        - anything else  → same as ``"analyst"`` (safe default)
        """
        if user_role == "admin":
            return list(tools)
        if user_role == "manager":
            return [t for t in tools if t.safety_level in ("read_only", "hitl")]
        # "analyst" and any unknown role
        return [t for t in tools if t.safety_level == "read_only"]

    def list_read_only(self) -> list[Tool]:
        return [t for t in self._tools.values() if t.safety_level == "read_only"]

    def list_hitl_tools(self) -> list[Tool]:
        return [t for t in self._tools.values() if t.safety_level == "hitl"]
