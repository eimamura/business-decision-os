from __future__ import annotations

import logging
from typing import Any, Literal, Protocol
from uuid import UUID

from pydantic import BaseModel

_log = logging.getLogger(__name__)

_CONTROL_ALLOWLIST_READY = False


def _get_control_allowlist() -> list[str]:
    """Derive the control-role tool allowlist from _INTENT_TOOL_SUBSET (Layer 3).

    Lazy evaluation avoids a circular import: control_agent imports base.py,
    so base.py must not import control_agent at module load time.

    On first call the result is stored back into _ROLE_TOOL_ALLOWLIST["control"]
    so that callers that access the dict directly (e.g. tests) also see the
    live value after the first call.

    Uses dict.__getitem__ on the return path to avoid re-entering this function
    through _RoleToolAllowlist.__getitem__.
    """
    global _CONTROL_ALLOWLIST_READY
    if _CONTROL_ALLOWLIST_READY:
        # Bypass _RoleToolAllowlist.__getitem__ to prevent infinite recursion.
        return dict.__getitem__(_ROLE_TOOL_ALLOWLIST, "control")
    try:
        from packages.agent.control.control_agent import _INTENT_TOOL_SUBSET  # noqa: PLC0415
        all_tools: set[str] = set()
        for tool_list in _INTENT_TOOL_SUBSET.values():
            all_tools.update(tool_list)
        dict.__setitem__(_ROLE_TOOL_ALLOWLIST, "control", sorted(all_tools))
    except Exception as exc:
        _log.warning("_get_control_allowlist failed: %s", exc)
        dict.__setitem__(_ROLE_TOOL_ALLOWLIST, "control", [])
    _CONTROL_ALLOWLIST_READY = True
    return dict.__getitem__(_ROLE_TOOL_ALLOWLIST, "control")


class _RoleToolAllowlist(dict):  # type: ignore[type-arg]
    """dict subclass that lazily resolves the 'control' entry on first access."""

    def __getitem__(self, key: str) -> list[str]:
        if key == "control":
            _get_control_allowlist()
        return super().__getitem__(key)

    def get(self, key: str, default: Any = None) -> Any:  # type: ignore[override]
        if key == "control":
            _get_control_allowlist()
        return super().get(key, default)


_ROLE_TOOL_ALLOWLIST: _RoleToolAllowlist = _RoleToolAllowlist({
    "orchestrator": [],
    "data_engineer": [
        "nl_query", "data_catalog_search",
        "table_schema_reader", "data_quality_checker",
    ],
    "simulation_optimizer": ["simulate_inventory", "optimize_replenishment"],
    "evaluator": ["evaluate_candidates"],
    "anomaly_detector": [
        "nl_query", "data_catalog_search",
        "table_schema_reader", "data_quality_checker",
    ],
    "demand": [
        "nl_query", "forecast",
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
    # "control" starts empty; _get_control_allowlist() populates it on first access
    # via the _RoleToolAllowlist.__getitem__ / .get overrides above.
    "control": [],
})


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
        # _ROLE_TOOL_ALLOWLIST.__getitem__ triggers lazy resolution for "control".
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
