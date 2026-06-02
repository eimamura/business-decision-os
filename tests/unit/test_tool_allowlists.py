from __future__ import annotations

import pytest

from packages.tools.base import _ROLE_TOOL_ALLOWLIST


@pytest.mark.parametrize(
    "role,expected_tools",
    [
        ("demand", ["sql_query", "nl_query", "forecast", "train_forecast"]),
        ("inventory", ["sql_query", "nl_query", "simulate_inventory"]),
        (
            "replenishment",
            ["sql_query", "nl_query", "simulate_inventory", "optimize_replenishment"],
        ),
        (
            "data_engineer",
            [
                "sql_query",
                "nl_query",
                "data_catalog_search",
                "table_schema_reader",
                "data_quality_checker",
            ],
        ),
        ("simulation_optimizer", ["simulate_inventory", "optimize_replenishment"]),
        ("evaluator", ["evaluate_candidates", "write_audit_log"]),
    ],
)
def test_role_tool_allowlist_contains_expected_tools(
    role: str, expected_tools: list[str]
) -> None:
    actual = set(_ROLE_TOOL_ALLOWLIST[role])
    for tool in expected_tools:
        assert tool in actual, f"Expected tool '{tool}' in allowlist for role '{role}'"
