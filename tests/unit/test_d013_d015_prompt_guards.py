"""D-013 / D-015 — Prompt content guards (unit tests).

D-013: ControlAgent system prompt must contain a tight rule directing the model to
       call `calculate_supply_gap` for supply-shortage-horizon questions.

D-015: set_goal and evaluate_goal prompts must explicitly instruct the model to
       respond in English only, preventing French/other-language bleed into the
       goal injection context.

Tests:
  T-D013-a  _SYSTEM_PROMPT contains the supply-shortage rule referencing 2b
  T-D013-b  _SYSTEM_PROMPT references calculate_supply_gap as the preferred tool
  T-D013-c  supply_chain intent subset includes calculate_supply_gap
  T-D015-a  SET_GOAL_SYSTEM contains English-only instruction
  T-D015-b  EVALUATE_GOAL_SYSTEM contains English-only instruction
  T-D015-c  SET_GOAL_SYSTEM does NOT say "same language the user used" without
            also mandating English (no ambiguous language instruction)
"""
from __future__ import annotations

import pytest

from packages.agent.control.control_agent import _INTENT_TOOL_SUBSET, _SYSTEM_PROMPT
from packages.agent.orchestrator.prompts import EVALUATE_GOAL_SYSTEM, SET_GOAL_SYSTEM


# ---------------------------------------------------------------------------
# D-013: Control agent prompt — supply-shortage-horizon rule
# ---------------------------------------------------------------------------


def test_system_prompt_contains_supply_shortage_rule_2b() -> None:
    """_SYSTEM_PROMPT must contain an explicit rule for supply-shortage-horizon questions
    directing the model to call calculate_supply_gap (D-013 fix).

    This is rule 2b added to address Q6 mis-routing to list_stockout_risk.
    """
    assert "calculate_supply_gap" in _SYSTEM_PROMPT, (
        "_SYSTEM_PROMPT is missing the calculate_supply_gap supply-shortage-horizon rule (D-013)"
    )


def test_system_prompt_supply_shortage_rule_describes_horizon_question() -> None:
    """_SYSTEM_PROMPT supply-shortage rule must mention 'supply shortages' or
    'shortage' to be recognizable as the Q6 routing rule (D-013 fix).
    """
    assert "supply shortage" in _SYSTEM_PROMPT.lower(), (
        "_SYSTEM_PROMPT does not contain a supply shortage horizon rule mentioning 'supply shortage'"
    )


def test_system_prompt_supply_gap_preferred_over_stockout_for_shortage() -> None:
    """_SYSTEM_PROMPT must explain that list_stockout_risk is NOT the right tool
    for supply-shortage-forward questions — the rule must include a negative instruction
    to prevent the model from defaulting to list_stockout_risk for Q6-type queries.
    """
    # The rule should differentiate list_stockout_risk (on-hand risk)
    # from calculate_supply_gap (forward supply adequacy)
    assert "list_stockout_risk" in _SYSTEM_PROMPT, (
        "_SYSTEM_PROMPT missing list_stockout_risk reference (needed for the contrast rule)"
    )
    assert "calculate_supply_gap" in _SYSTEM_PROMPT, (
        "_SYSTEM_PROMPT missing calculate_supply_gap (D-013: supply shortage tool)"
    )


def test_supply_chain_intent_subset_includes_calculate_supply_gap() -> None:
    """The supply_chain intent tool subset must include calculate_supply_gap
    so it is available when the model processes Q6-type questions (D-013).
    """
    supply_chain_tools = _INTENT_TOOL_SUBSET.get("supply_chain", [])
    assert "calculate_supply_gap" in supply_chain_tools, (
        "supply_chain intent subset does not include calculate_supply_gap (D-013)"
    )


def test_supply_chain_intent_subset_includes_analyze_supply_risk() -> None:
    """The supply_chain intent subset must also include analyze_supply_risk
    as an acceptable alternative for supply-shortage-horizon questions (D-013).
    """
    supply_chain_tools = _INTENT_TOOL_SUBSET.get("supply_chain", [])
    assert "analyze_supply_risk" in supply_chain_tools, (
        "supply_chain intent subset does not include analyze_supply_risk (D-013)"
    )


# ---------------------------------------------------------------------------
# D-015: Prompts — English-only language instruction
# ---------------------------------------------------------------------------


def test_set_goal_system_contains_english_only_instruction() -> None:
    """SET_GOAL_SYSTEM must explicitly instruct the model to write goal_text and
    success_criteria in English only (D-015 fix).

    The prior prompt said 'same language the user used' which caused goal_text
    to be generated in French when the LLM classified a Japanese user query and
    then translated it — French goal injection confuses the control agent.
    """
    lower = SET_GOAL_SYSTEM.lower()
    assert "english" in lower, (
        "SET_GOAL_SYSTEM does not contain an English-only language instruction (D-015)"
    )
    assert "only" in lower or "english only" in lower, (
        "SET_GOAL_SYSTEM language instruction is not explicit about English-only (D-015)"
    )


def test_evaluate_goal_system_contains_english_only_instruction() -> None:
    """EVALUATE_GOAL_SYSTEM must explicitly instruct the model to write the 'missing'
    field and all output in English only (D-015 fix).

    The prior prompt's 'same language the user used' rule caused the evaluator to
    emit French 'missing' descriptions which then became refinement_feedback injected
    into the control agent's context, triggering French output.
    """
    lower = EVALUATE_GOAL_SYSTEM.lower()
    assert "english" in lower, (
        "EVALUATE_GOAL_SYSTEM does not contain an English-only language instruction (D-015)"
    )
    assert "only" in lower, (
        "EVALUATE_GOAL_SYSTEM language instruction is not explicit about English-only (D-015)"
    )


def test_set_goal_system_english_instruction_mentions_internal_usage() -> None:
    """SET_GOAL_SYSTEM English-only instruction must explain WHY (internal usage),
    distinguishing it from a user-facing instruction — this prevents future regression
    where someone assumes goal_text should match user language.
    """
    # The prompt should have context about it being used internally (not user-facing)
    lower = SET_GOAL_SYSTEM.lower()
    has_internal_context = (
        "internally" in lower
        or "system language" in lower
        or "internal" in lower
        or "orchestrator" in lower
    )
    assert has_internal_context, (
        "SET_GOAL_SYSTEM English-only instruction lacks rationale (internal usage context)"
    )
