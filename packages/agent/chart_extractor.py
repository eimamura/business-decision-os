from __future__ import annotations

import logging
from typing import Any

_log = logging.getLogger(__name__)

# Registry mapping tool name → builder function.
# Each builder receives the raw tool output dict and returns a ChartSpec dict or None.
_BUILDERS: dict[str, Any] = {}


def extract_chart_specs(agent_results: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert chartable tool outputs found in agent results into ChartSpec dicts.

    Iterates over all SpecialistResult-like values in *agent_results*, inspects
    ``output["tool_results"]`` for known chartable tools, and builds one ChartSpec
    dict per tool.  Duplicate tool names across multiple specialist results are
    deduplicated (first occurrence wins).

    Returns an empty list on any error — chart extraction is non-fatal.

    Args:
        agent_results: Mapping of specialist name → SpecialistResult (Pydantic model)
            or plain dict with an ``"output"`` key.

    Returns:
        A list of ChartSpec dicts, possibly empty.
    """
    try:
        specs: list[dict[str, Any]] = []
        seen_tools: set[str] = set()

        for result in agent_results.values():
            # Support both Pydantic model (.output attribute) and plain dict.
            output: dict[str, Any] | None = getattr(result, "output", None)
            if output is None:
                if isinstance(result, dict):
                    output = result.get("output", {})
                else:
                    continue
            if not isinstance(output, dict):
                continue

            tool_results: dict[str, Any] = output.get("tool_results", {})
            if not isinstance(tool_results, dict):
                continue

            for tool_name, tool_output in tool_results.items():
                if tool_name in seen_tools:
                    continue
                if not isinstance(tool_output, dict):
                    continue

                builder = _BUILDERS.get(tool_name)
                if builder is None:
                    continue

                spec = builder(tool_output)
                if spec is not None:
                    specs.append(spec)
                    seen_tools.add(tool_name)

        return specs
    except Exception:
        _log.warning("chart_extractor: unexpected error; returning empty list", exc_info=True)
        return []


def _spec_for_list_stockout_risk(tool_output: dict[str, Any]) -> dict[str, Any] | None:
    """Build a bar ChartSpec from list_stockout_risk output.

    Returns None when the items list is empty (nothing to render).
    """
    items = tool_output.get("items")
    if not items or not isinstance(items, list):
        return None

    return {
        "type": "bar",
        "title": "Stockout Risk — Days of Cover by SKU",
        "xKey": "sku_code",
        "series": [
            {"dataKey": "days_of_cover", "name": "Days of Cover", "color": "#ef4444"},
        ],
        "data": items,
    }


def _spec_for_analyze_demand_trend(tool_output: dict[str, Any]) -> dict[str, Any] | None:
    """Build a line ChartSpec from analyze_demand_trend output.

    Returns None when the items list has fewer than 2 entries (not enough to show a trend).
    """
    items = tool_output.get("items")
    if not items or not isinstance(items, list) or len(items) < 2:
        return None

    return {
        "type": "line",
        "title": "Demand Trend",
        "xKey": "period",
        "series": [
            {"dataKey": "quantity", "name": "Demand (units)", "color": "#3b82f6"},
        ],
        "data": items,
    }


# Register builders after they are defined.
_BUILDERS["list_stockout_risk"] = _spec_for_list_stockout_risk
_BUILDERS["analyze_demand_trend"] = _spec_for_analyze_demand_trend
