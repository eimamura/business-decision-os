"""T-417: Assert _ROLE_TOOL_ALLOWLIST["control"] equals the sorted union of all
values in _INTENT_TOOL_SUBSET (Gap 4 — P64 B-03, T-411).

This test acts as a regression guard: if someone hand-edits the "control" entry
in base.py instead of using the auto-derive helper, this test will catch the
divergence.
"""
from __future__ import annotations

from packages.agent.control.control_agent import _INTENT_TOOL_SUBSET
from packages.tools.base import _ROLE_TOOL_ALLOWLIST


def test_control_allowlist_equals_union_of_intent_tool_subset() -> None:
    """_ROLE_TOOL_ALLOWLIST["control"] must be the sorted union of _INTENT_TOOL_SUBSET."""
    expected: set[str] = set()
    for tool_list in _INTENT_TOOL_SUBSET.values():
        expected.update(tool_list)
    expected_sorted = sorted(expected)

    actual = _ROLE_TOOL_ALLOWLIST["control"]

    assert actual == expected_sorted, (
        f"_ROLE_TOOL_ALLOWLIST['control'] diverges from _INTENT_TOOL_SUBSET union.\n"
        f"Expected: {expected_sorted}\n"
        f"Actual:   {actual}"
    )


def test_control_allowlist_is_not_empty() -> None:
    """_ROLE_TOOL_ALLOWLIST["control"] must be non-empty (auto-derived)."""
    assert len(_ROLE_TOOL_ALLOWLIST["control"]) > 0, (
        "_ROLE_TOOL_ALLOWLIST['control'] is empty — _build_control_allowlist() may have failed"
    )


def test_control_allowlist_is_sorted() -> None:
    """_ROLE_TOOL_ALLOWLIST["control"] must be lexicographically sorted."""
    actual = _ROLE_TOOL_ALLOWLIST["control"]
    assert actual == sorted(actual), (
        f"_ROLE_TOOL_ALLOWLIST['control'] is not sorted: {actual}"
    )
