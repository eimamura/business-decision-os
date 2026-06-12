"""Unit tests for _slim_agent_output in packages/agent/orchestrator/decision.py.

T-592: Bounded fix for P97 context saturation mitigation.
Tests are deterministic and network-free — no LLM calls.
"""
from __future__ import annotations

import json

import pytest

from packages.agent.orchestrator.decision import (
    _SYNTHESIZE_AGENT_OUTPUT_MAX_CHARS,
    _slim_agent_output,
)


# ---------------------------------------------------------------------------
# _slim_agent_output — field stripping
# ---------------------------------------------------------------------------


def test_slim_strips_tool_results():
    """tool_results must be stripped — it was the dominant P94 contributor (~86% of num_ctx)."""
    output = {
        "text": "Situation: ...",
        "specialist": "ControlAgent",
        "tool_results": {"analyze_forecast_deviation": {"skus": [{"sku_id": "SKU-001"}] * 30}},
        "verification": {"grounded": True, "revised": False},
    }
    slim = _slim_agent_output(output)
    assert "tool_results" not in slim


def test_slim_keeps_text():
    output = {"text": "Agent conclusion text.", "tool_results": {"t": {}}}
    slim = _slim_agent_output(output)
    assert slim.get("text") == "Agent conclusion text."


def test_slim_keeps_specialist():
    output = {"text": "ok", "specialist": "ControlAgent", "tool_results": {}}
    slim = _slim_agent_output(output)
    assert slim.get("specialist") == "ControlAgent"


def test_slim_keeps_verification():
    output = {
        "text": "ok",
        "verification": {"grounded": True, "revised": False},
        "tool_results": {},
    }
    slim = _slim_agent_output(output)
    assert slim.get("verification") == {"grounded": True, "revised": False}


def test_slim_ignores_unknown_keys():
    """Arbitrary extra keys (e.g. future output fields) must be silently stripped."""
    output = {"text": "ok", "future_field": "value", "tool_results": {}}
    slim = _slim_agent_output(output)
    assert "future_field" not in slim


def test_slim_none_returns_empty_dict():
    assert _slim_agent_output(None) == {}


def test_slim_empty_output_returns_empty_dict():
    assert _slim_agent_output({}) == {}


# ---------------------------------------------------------------------------
# _slim_agent_output — text truncation cap
# ---------------------------------------------------------------------------


def test_slim_truncates_oversized_text():
    """Text exceeding _SYNTHESIZE_AGENT_OUTPUT_MAX_CHARS must be hard-truncated."""
    long_text = "A" * (_SYNTHESIZE_AGENT_OUTPUT_MAX_CHARS + 1000)
    output = {"text": long_text}
    slim = _slim_agent_output(output)
    assert len(slim["text"]) <= _SYNTHESIZE_AGENT_OUTPUT_MAX_CHARS + len(" ...[truncated]")
    assert slim["text"].endswith(" ...[truncated]")


def test_slim_does_not_truncate_short_text():
    """Text within the cap must be passed through verbatim."""
    short_text = "Situation: normal. Root Cause: none."
    output = {"text": short_text}
    slim = _slim_agent_output(output)
    assert slim["text"] == short_text


def test_slim_truncated_text_has_marker():
    """Truncated text must include the '...[truncated]' marker for LLM context."""
    long_text = "X" * (_SYNTHESIZE_AGENT_OUTPUT_MAX_CHARS + 500)
    output = {"text": long_text}
    slim = _slim_agent_output(output)
    assert "[truncated]" in slim["text"]


# ---------------------------------------------------------------------------
# Token budget: slimmed output must be within ≤70% of num_ctx
# ---------------------------------------------------------------------------


def test_slim_output_within_token_budget():
    """Slimmed P94-replica output must be well within the 70% budget.

    P94 session: 14080 tokens (86% of 16384). After stripping tool_results the
    synthesize payload should be < 11469 tokens (70% of 16384).
    Estimate: chars / 4 (conservative).
    """
    NUM_CTX = 16384
    BUDGET_RATIO = 0.70
    budget_tokens = int(NUM_CTX * BUDGET_RATIO)

    # Simulate the P94 agent output including the large tool_results blob
    sku_entry = {
        "sku_id": "SKU-001",
        "bias_direction": "under_forecast",
        "total_forecast_qty": 0.0,
        "total_actual_qty": 5510.0,
        "total_gap_qty": -5510.0,
        "total_abs_gap_qty": 5510.0,
        "aggregate_abs_deviation_pct": 100.0,
        "weekly_breakdown": [
            {"iso_week": "2026-W20", "week_start": "2026-05-11",
             "forecast_qty": 0.0, "actual_qty": 1351.0, "gap_qty": -1351.0, "gap_pct": -100.0},
            {"iso_week": "2026-W21", "week_start": "2026-05-18",
             "forecast_qty": 0.0, "actual_qty": 1543.0, "gap_qty": -1543.0, "gap_pct": -100.0},
            {"iso_week": "2026-W22", "week_start": "2026-05-25",
             "forecast_qty": 0.0, "actual_qty": 1176.0, "gap_qty": -1176.0, "gap_pct": -100.0},
            {"iso_week": "2026-W23", "week_start": "2026-06-01",
             "forecast_qty": 0.0, "actual_qty": 1440.0, "gap_qty": -1440.0, "gap_pct": -100.0},
        ],
    }
    p94_output = {
        "text": "Could not verify findings. Please rephrase your question or try again.",
        "specialist": "ControlAgent",
        "tool_results": {
            "analyze_forecast_deviation": {
                "weeks_analysed": 4,
                "skus": [sku_entry] * 30,  # 30 SKUs as in P94
                "count": 30,
                "truncated": False,
                "missing_data": [
                    f"SKU-{i:03d}: no forecast rows in window (2026-W20–2026-W23)"
                    for i in range(1, 44)
                ],
            }
        },
        "verification": {
            "grounded": True,
            "revised": False,
            "blocked_reason": "findings verifier: response not grounded in tool results",
        },
    }

    slim = _slim_agent_output(p94_output)
    slim_json = json.dumps(slim)
    estimated_tokens = len(slim_json) // 4

    assert estimated_tokens < budget_tokens, (
        f"Slimmed output estimated {estimated_tokens} tokens exceeds "
        f"70% budget of {budget_tokens} tokens "
        f"(num_ctx={NUM_CTX}). len={len(slim_json)} chars."
    )


# ---------------------------------------------------------------------------
# Constant guard: _SYNTHESIZE_AGENT_OUTPUT_MAX_CHARS must be documented value
# ---------------------------------------------------------------------------


def test_synthesize_agent_output_max_chars_value():
    """_SYNTHESIZE_AGENT_OUTPUT_MAX_CHARS must be the documented 8000 chars."""
    assert _SYNTHESIZE_AGENT_OUTPUT_MAX_CHARS == 8_000
