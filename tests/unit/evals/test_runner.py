from __future__ import annotations

from pathlib import Path

import pytest

from packages.agent.evals.eval_case import EvalCase
from packages.agent.evals.runner import EvalResult, EvalRunner, check_assertions, classify_failure

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MINIMAL_EVAL_CASE_DICT = {
    "id": "Q1",
    "spec_question": "Which products are at risk of stockout?",
    "intent": "supply_chain",
    "required_tools": ["list_stockout_risk"],
    "must_not_use_tools": ["list_today_exceptions", "calculate_supply_gap"],
    "response_assertions": {
        "must_contain": ["stockout", "SKU"],
        "must_not_contain": ["I don't have", "I'm sorry", "je"],
    },
    "expected_behavior": ["Names specific SKUs with risk levels"],
    "failure_modes": [
        {
            "type": "routing",
            "description": "Calls wrong tool",
        }
    ],
}


def _make_case(**overrides: object) -> EvalCase:
    """Return an EvalCase with optional field overrides applied to the base dict."""
    data = dict(_MINIMAL_EVAL_CASE_DICT)
    # Deep-merge response_assertions if overridden
    if "response_assertions" in overrides:
        data["response_assertions"] = overrides.pop("response_assertions")
    data.update(overrides)
    return EvalCase.model_validate(data)


def _make_result(**overrides: object) -> EvalResult:
    """Return an EvalResult with a valid baseline; caller overrides as needed."""
    defaults: dict[str, object] = {
        "case_id": "Q1",
        "passed": False,
        "tools_called": [],
        "missing_required_tools": [],
        "prohibited_tools_called": [],
        "response_text": "",
        "assertion_hits": [],
        "assertion_misses": [],
        "must_not_contain_violations": [],
        "failure_type": None,
    }
    defaults.update(overrides)
    return EvalResult(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# (a) EvalResult schema validates
# ---------------------------------------------------------------------------


def test_eval_result_schema_validates() -> None:
    result = EvalResult(
        case_id="Q1",
        passed=True,
        tools_called=["list_stockout_risk"],
        missing_required_tools=[],
        prohibited_tools_called=[],
        response_text="SKU-001 is at critical stockout risk",
        assertion_hits=["stockout", "SKU"],
        assertion_misses=[],
        must_not_contain_violations=[],
        failure_type=None,
    )

    assert result.case_id == "Q1"
    assert result.passed is True
    assert result.tools_called == ["list_stockout_risk"]
    assert result.missing_required_tools == []
    assert result.prohibited_tools_called == []
    assert result.response_text == "SKU-001 is at critical stockout risk"
    assert result.assertion_hits == ["stockout", "SKU"]
    assert result.assertion_misses == []
    assert result.must_not_contain_violations == []
    assert result.failure_type is None


# ---------------------------------------------------------------------------
# (b) classify_failure returns None when passed
# ---------------------------------------------------------------------------


def test_classify_failure_returns_none_when_passed() -> None:
    result = EvalResult(
        case_id="Q1",
        passed=True,
        tools_called=["list_stockout_risk"],
        missing_required_tools=[],
        prohibited_tools_called=[],
        response_text="SKU-001 is at critical risk",
        assertion_hits=["stockout", "SKU"],
        assertion_misses=[],
        must_not_contain_violations=[],
        failure_type=None,
    )
    assert classify_failure(result) is None


# ---------------------------------------------------------------------------
# (c) classify_failure → "routing" when required missing AND prohibited called
# ---------------------------------------------------------------------------


def test_classify_failure_routing_when_required_missing_and_prohibited_called() -> None:
    result = _make_result(
        passed=False,
        missing_required_tools=["list_stockout_risk"],
        prohibited_tools_called=["list_today_exceptions"],
    )
    assert classify_failure(result) == "routing"


# ---------------------------------------------------------------------------
# (d) classify_failure → "pollution" when prohibited called but required present
# ---------------------------------------------------------------------------


def test_classify_failure_pollution_when_prohibited_called_but_required_present() -> None:
    result = _make_result(
        passed=False,
        missing_required_tools=[],
        prohibited_tools_called=["list_today_exceptions"],
    )
    assert classify_failure(result) == "pollution"


# ---------------------------------------------------------------------------
# (e) classify_failure → "retrieval" when required tool absent
# ---------------------------------------------------------------------------


def test_classify_failure_retrieval_when_required_tool_absent() -> None:
    result = _make_result(
        passed=False,
        missing_required_tools=["list_stockout_risk"],
        prohibited_tools_called=[],
    )
    assert classify_failure(result) == "retrieval"


# ---------------------------------------------------------------------------
# (f) classify_failure → "reasoning" when must_not_contain violated
# ---------------------------------------------------------------------------


def test_classify_failure_reasoning_when_must_not_contain_violated() -> None:
    result = _make_result(
        passed=False,
        missing_required_tools=[],
        prohibited_tools_called=[],
        must_not_contain_violations=["I don't have"],
    )
    assert classify_failure(result) == "reasoning"


# ---------------------------------------------------------------------------
# (g) classify_failure → "output" when assertions miss
# ---------------------------------------------------------------------------


def test_classify_failure_output_when_assertions_miss() -> None:
    result = _make_result(
        passed=False,
        missing_required_tools=[],
        prohibited_tools_called=[],
        must_not_contain_violations=[],
        assertion_misses=["SKU"],
    )
    assert classify_failure(result) == "output"


# ---------------------------------------------------------------------------
# (h) check_assertions returns hits and misses for a matching response
# ---------------------------------------------------------------------------


def test_check_assertions_returns_hits_and_misses() -> None:
    case = _make_case(
        response_assertions={
            "must_contain": ["stockout", "SKU"],
            "must_not_contain": ["I don't have", "je"],
        }
    )
    response = "SKU-001 is at critical stockout risk"

    assertion_hits, assertion_misses, must_not_contain_violations = check_assertions(response, case)

    assert "stockout" in assertion_hits
    assert "SKU" in assertion_hits
    assert assertion_misses == []
    assert must_not_contain_violations == []


# ---------------------------------------------------------------------------
# (i) check_assertions detects must_not_contain violation (French phrase)
# ---------------------------------------------------------------------------


def test_check_assertions_detects_must_not_contain_violation() -> None:
    case = _make_case(
        response_assertions={
            "must_contain": ["stockout"],
            "must_not_contain": ["I don't have", "je"],
        }
    )
    response = "Je suis désolé, je ne dispose pas des informations"

    _hits, _misses, violations = check_assertions(response, case)

    assert "je" in violations


# ---------------------------------------------------------------------------
# (j) EvalRunner.load_cases returns 10 EvalCase instances
# ---------------------------------------------------------------------------


def test_eval_runner_load_cases_returns_10() -> None:
    runner = EvalRunner()
    cases = runner.load_cases(Path("data/evals/spec10_golden_cases.yaml"))
    assert len(cases) == 10
    assert all(isinstance(c, EvalCase) for c in cases)
