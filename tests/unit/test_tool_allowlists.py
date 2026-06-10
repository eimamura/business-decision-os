from __future__ import annotations

import pytest

from packages.tools.base import _ROLE_TOOL_ALLOWLIST


@pytest.mark.parametrize(
    "role,expected_tools",
    [
        ("demand", ["nl_query", "forecast"]),
        ("inventory", ["nl_query", "simulate_inventory"]),
        (
            "replenishment",
            ["nl_query", "simulate_inventory", "optimize_replenishment"],
        ),
        (
            "data_engineer",
            [
                "nl_query",
                "data_catalog_search",
                "table_schema_reader",
                "data_quality_checker",
            ],
        ),
        ("simulation_optimizer", ["simulate_inventory", "optimize_replenishment"]),
        ("evaluator", ["evaluate_candidates"]),
    ],
)
def test_role_tool_allowlist_contains_expected_tools(
    role: str, expected_tools: list[str]
) -> None:
    actual = set(_ROLE_TOOL_ALLOWLIST[role])
    for tool in expected_tools:
        assert tool in actual, f"Expected tool '{tool}' in allowlist for role '{role}'"
