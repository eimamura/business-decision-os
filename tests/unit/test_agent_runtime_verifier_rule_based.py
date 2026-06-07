"""T-399 / T-402: Unit tests for the rule-based verify_findings in AgentRuntime.

_rule_based_verify() applies four deterministic rules:
  Rule 1:  No tool calls AND conclusion contains digit or "no"/"none"/"なし" → "blocked"
  Rule 1b: Tool calls present AND result has data (count>0 or non-empty items)
           AND conclusion matches nil-claim pattern → "blocked"
  Rule 2:  Tool calls present AND conclusion shorter than _DEGENERATE_RESPONSE_MIN_LEN → "blocked"
  Rule 3:  Everything else → "pass"
"""
from __future__ import annotations

from packages.agent.runtime import _DEGENERATE_RESPONSE_MIN_LEN, _rule_based_verify


# ---------------------------------------------------------------------------
# Rule 1 — no tool calls + fabricated numeric/no-data conclusion
# ---------------------------------------------------------------------------


def test_rule1_no_tools_with_number_in_conclusion_returns_blocked() -> None:
    """No tool calls + conclusion with a digit → blocked (fabricated data)."""
    result = _rule_based_verify(
        tool_results=[],
        conclusion="There are 5 stockout SKUs in the warehouse.",
    )
    assert result == "blocked", f"Expected 'blocked', got {result!r}"


def test_rule1_no_tools_with_no_in_conclusion_returns_blocked() -> None:
    """No tool calls + conclusion contains 'no' → blocked."""
    result = _rule_based_verify(
        tool_results=[],
        conclusion="There are no stockouts currently.",
    )
    assert result == "blocked", f"Expected 'blocked', got {result!r}"


def test_rule1_no_tools_with_none_in_conclusion_returns_blocked() -> None:
    """No tool calls + conclusion contains 'none' → blocked."""
    result = _rule_based_verify(
        tool_results=[],
        conclusion="None of the SKUs are at risk.",
    )
    assert result == "blocked", f"Expected 'blocked', got {result!r}"


def test_rule1_no_tools_with_japanese_nashi_returns_blocked() -> None:
    """No tool calls + conclusion contains 'なし' → blocked."""
    result = _rule_based_verify(
        tool_results=[],
        conclusion="在庫リスクなし。",
    )
    assert result == "blocked", f"Expected 'blocked', got {result!r}"


def test_rule1_no_tools_neutral_conclusion_returns_pass() -> None:
    """No tool calls + conclusion without fabrication markers → pass.

    A conclusion that is purely descriptive and lacks numbers or negation
    should not be blocked by Rule 1.
    """
    result = _rule_based_verify(
        tool_results=[],
        conclusion="Analyzing the supply chain situation.",
    )
    assert result == "pass", f"Expected 'pass', got {result!r}"


# ---------------------------------------------------------------------------
# Rule 2 — tool calls present + too-short conclusion
# ---------------------------------------------------------------------------


def test_rule2_tool_calls_present_short_conclusion_returns_blocked() -> None:
    """Tool calls made + conclusion shorter than _DEGENERATE_RESPONSE_MIN_LEN → blocked."""
    short_conclusion = "X" * (_DEGENERATE_RESPONSE_MIN_LEN - 1)
    result = _rule_based_verify(
        tool_results=[{"list_stockout_risk": {"items": []}}],
        conclusion=short_conclusion,
    )
    assert result == "blocked", f"Expected 'blocked', got {result!r}"


def test_rule2_tool_calls_present_exactly_min_len_returns_pass() -> None:
    """Tool calls made + conclusion exactly _DEGENERATE_RESPONSE_MIN_LEN → pass."""
    exact_conclusion = "A" * _DEGENERATE_RESPONSE_MIN_LEN
    result = _rule_based_verify(
        tool_results=[{"list_stockout_risk": {"items": []}}],
        conclusion=exact_conclusion,
    )
    assert result == "pass", f"Expected 'pass', got {result!r}"


# ---------------------------------------------------------------------------
# Rule 3 — normal happy path
# ---------------------------------------------------------------------------


def test_rule3_tool_calls_present_long_conclusion_returns_pass() -> None:
    """Tool calls made + adequate conclusion → pass."""
    long_conclusion = (
        "Based on the tool results, SKU-A001 has a days-of-supply of 3 days, "
        "which is below the 7-day reorder threshold. Immediate replenishment is advised."
    )
    result = _rule_based_verify(
        tool_results=[{"list_stockout_risk": {"items": [{"sku": "A001", "risk": "critical"}]}}],
        conclusion=long_conclusion,
    )
    assert result == "pass", f"Expected 'pass', got {result!r}"


def test_rule3_no_tools_and_no_fabrication_markers_returns_pass() -> None:
    """No tool calls + conclusion with no digit or negation markers → pass.

    This exercises the case where the agent generates an intro question rather
    than a data claim — the verifier should not block it.
    """
    result = _rule_based_verify(
        tool_results=[],
        conclusion="What specific warehouse region would you like me to analyze?",
    )
    assert result == "pass", f"Expected 'pass', got {result!r}"


# ---------------------------------------------------------------------------
# Rule 1b — tool results contain data but conclusion claims nil
# ---------------------------------------------------------------------------


def test_rule1b_count_gt0_with_nil_claim_returns_blocked() -> None:
    """T-402a: list_stockout_risk returns count=3 but conclusion claims no exceptions → blocked."""
    result = _rule_based_verify(
        tool_results=[
            {
                "list_stockout_risk": {
                    "count": 3,
                    "items": [
                        {"sku_id": "SKU-001", "days_of_supply": 1},
                        {"sku_id": "SKU-002", "days_of_supply": 2},
                        {"sku_id": "SKU-003", "days_of_supply": 0},
                    ],
                }
            }
        ],
        conclusion="There are no stockout exceptions today.",
    )
    assert result == "blocked", f"Expected 'blocked', got {result!r}"


def test_rule1b_count_zero_with_nil_claim_returns_pass() -> None:
    """T-402b: list_stockout_risk returns count=0 — nil claim is correct → pass."""
    result = _rule_based_verify(
        tool_results=[
            {
                "list_stockout_risk": {
                    "count": 0,
                    "items": [],
                }
            }
        ],
        conclusion="There are no stockout risks.",
    )
    assert result == "pass", f"Expected 'pass', got {result!r}"


def test_rule1b_count_gt0_without_nil_claim_returns_pass() -> None:
    """T-402c: list_stockout_risk returns count=3 and conclusion names the SKUs → pass."""
    result = _rule_based_verify(
        tool_results=[
            {
                "list_stockout_risk": {
                    "count": 3,
                    "items": [
                        {"sku_id": "SKU-001", "days_of_supply": 1},
                        {"sku_id": "SKU-002", "days_of_supply": 2},
                        {"sku_id": "SKU-003", "days_of_supply": 0},
                    ],
                }
            }
        ],
        conclusion="Three SKUs are at risk: SKU-001, SKU-002, SKU-003.",
    )
    assert result == "pass", f"Expected 'pass', got {result!r}"
