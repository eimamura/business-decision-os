from __future__ import annotations

"""Unit tests for packages.agent.chart_extractor.extract_chart_specs.

No DB, no network, no mocks — pure function tests.
"""

import pytest

from packages.agent.chart_extractor import extract_chart_specs


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_agent_results(tool_name: str, tool_output: dict) -> dict:
    """Build a minimal agent_results dict with a single specialist output."""
    return {
        "control": {
            "output": {
                "text": "Analysis complete.",
                "specialist": "control",
                "tool_results": {
                    tool_name: tool_output,
                },
            }
        }
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_extract_chart_specs_list_stockout_risk_with_items_returns_bar_spec():
    agent_results = _make_agent_results(
        "list_stockout_risk",
        {
            "items": [{"sku_code": "SKU-001", "days_of_cover": 2.1}],
            "count": 1,
            "missing_data": [],
        },
    )

    result = extract_chart_specs(agent_results)

    assert len(result) == 1


def test_extract_chart_specs_list_stockout_risk_bar_spec_type():
    agent_results = _make_agent_results(
        "list_stockout_risk",
        {
            "items": [{"sku_code": "SKU-001", "days_of_cover": 2.1}],
            "count": 1,
            "missing_data": [],
        },
    )

    result = extract_chart_specs(agent_results)

    assert result[0]["type"] == "bar"


def test_extract_chart_specs_list_stockout_risk_bar_spec_xkey():
    agent_results = _make_agent_results(
        "list_stockout_risk",
        {
            "items": [{"sku_code": "SKU-001", "days_of_cover": 2.1}],
            "count": 1,
            "missing_data": [],
        },
    )

    result = extract_chart_specs(agent_results)

    assert result[0]["xKey"] == "sku_code"


def test_extract_chart_specs_list_stockout_risk_bar_spec_data():
    items = [{"sku_code": "SKU-001", "days_of_cover": 2.1}]
    agent_results = _make_agent_results(
        "list_stockout_risk",
        {
            "items": items,
            "count": 1,
            "missing_data": [],
        },
    )

    result = extract_chart_specs(agent_results)

    assert result[0]["data"] == items


def test_extract_chart_specs_unknown_tool_returns_empty_list():
    agent_results = _make_agent_results(
        "unknown_tool_xyz",
        {"items": [{"foo": 1}], "count": 1},
    )

    result = extract_chart_specs(agent_results)

    assert result == []


def test_extract_chart_specs_empty_agent_results_returns_empty_list():
    result = extract_chart_specs({})

    assert result == []


def test_extract_chart_specs_empty_items_list_returns_empty_list():
    agent_results = _make_agent_results(
        "list_stockout_risk",
        {"items": [], "count": 0, "missing_data": []},
    )

    result = extract_chart_specs(agent_results)

    assert result == []


def test_extract_chart_specs_analyze_demand_trend_with_two_items_returns_line_spec():
    agent_results = _make_agent_results(
        "analyze_demand_trend",
        {
            "trend_direction": "up",
            "trend_slope": 0.5,
            "items": [
                {"period": "2026-05", "quantity": 100.0},
                {"period": "2026-06", "quantity": 110.0},
            ],
            "missing_data": [],
        },
    )

    result = extract_chart_specs(agent_results)

    assert result[0]["type"] == "line"


def test_extract_chart_specs_analyze_demand_trend_xkey_is_period():
    agent_results = _make_agent_results(
        "analyze_demand_trend",
        {
            "trend_direction": "up",
            "trend_slope": 0.5,
            "items": [
                {"period": "2026-05", "quantity": 100.0},
                {"period": "2026-06", "quantity": 110.0},
            ],
            "missing_data": [],
        },
    )

    result = extract_chart_specs(agent_results)

    assert result[0]["xKey"] == "period"


def test_extract_chart_specs_demand_trend_with_one_item_returns_empty_list():
    agent_results = _make_agent_results(
        "analyze_demand_trend",
        {
            "trend_direction": "up",
            "trend_slope": 0.5,
            "items": [{"period": "2026-05", "quantity": 100.0}],
            "missing_data": [],
        },
    )

    result = extract_chart_specs(agent_results)

    assert result == []
