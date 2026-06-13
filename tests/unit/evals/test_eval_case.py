from __future__ import annotations

from pathlib import Path

import pytest

from packages.agent.evals.eval_case import EvalCase, FailureMode, load_eval_cases

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_VALID_FAILURE_MODE_TYPES = {"retrieval", "selection", "pollution", "routing", "reasoning", "output"}


@pytest.fixture(scope="session")
def cases_path() -> Path:
    return Path("data/evals/spec10_golden_cases.yaml")


@pytest.fixture(scope="session")
def all_cases(cases_path: Path) -> list[EvalCase]:
    return load_eval_cases(cases_path)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def case_by_id(all_cases: list[EvalCase], qid: str) -> EvalCase:
    """Return the EvalCase whose id matches *qid*, or raise KeyError."""
    for case in all_cases:
        if case.id == qid:
            return case
    raise KeyError(f"No eval case with id={qid!r}")


# ---------------------------------------------------------------------------
# (a) Count
# ---------------------------------------------------------------------------


def test_load_eval_cases_returns_10_cases(all_cases: list[EvalCase]) -> None:
    assert len(all_cases) == 10


# ---------------------------------------------------------------------------
# (b) required_tools — parametrized over all 10 cases
# ---------------------------------------------------------------------------


def _case_ids(all_cases_fixture: list[EvalCase]) -> list[str]:
    return [c.id for c in all_cases_fixture]


# pytest parametrize cannot reference session-scoped fixtures directly, so we
# collect the cases lazily at module level after the fixture runs.  Instead we
# use an indirect parametrize pattern via a module-level helper list.

@pytest.fixture(
    scope="session",
    params=["Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7", "Q8", "Q9", "Q10"],
)
def single_case(request: pytest.FixtureRequest, all_cases: list[EvalCase]) -> EvalCase:
    return case_by_id(all_cases, request.param)


def test_each_case_has_at_least_one_required_tool(single_case: EvalCase) -> None:
    assert len(single_case.required_tools) >= 1


def test_each_case_has_at_least_one_must_contain_assertion(single_case: EvalCase) -> None:
    assert len(single_case.response_assertions.must_contain) >= 1


def test_each_case_has_at_least_one_failure_mode(single_case: EvalCase) -> None:
    assert len(single_case.failure_modes) >= 1


# ---------------------------------------------------------------------------
# (e) All failure-mode types are valid — parametrize over every FailureMode
#     across every case
# ---------------------------------------------------------------------------


def _all_failure_modes(all_cases: list[EvalCase]) -> list[tuple[str, FailureMode]]:
    """Return (case_id, fm) pairs for every failure mode across all cases."""
    pairs: list[tuple[str, FailureMode]] = []
    for case in all_cases:
        for fm in case.failure_modes:
            pairs.append((case.id, fm))
    return pairs


# Collect once at import time; the YAML path is deterministic.
_GOLDEN_CASES_PATH = Path("data/evals/spec10_golden_cases.yaml")
_ALL_CASES_EAGER = load_eval_cases(_GOLDEN_CASES_PATH)
_ALL_FM_PAIRS = _all_failure_modes(_ALL_CASES_EAGER)


@pytest.mark.parametrize(
    "case_id,fm",
    _ALL_FM_PAIRS,
    ids=[f"{case_id}-{fm.type}-{i}" for i, (case_id, fm) in enumerate(_ALL_FM_PAIRS)],
)
def test_all_failure_mode_types_are_valid(case_id: str, fm: FailureMode) -> None:
    assert fm.type in _VALID_FAILURE_MODE_TYPES, (
        f"Case {case_id}: unexpected failure mode type {fm.type!r}"
    )


# ---------------------------------------------------------------------------
# (f) Q1 must require list_stockout_risk
# ---------------------------------------------------------------------------


def test_q1_requires_list_stockout_risk(all_cases: list[EvalCase]) -> None:
    case = case_by_id(all_cases, "Q1")
    assert "list_stockout_risk" in case.required_tools


# ---------------------------------------------------------------------------
# (g) Q3 must require list_today_exceptions
# ---------------------------------------------------------------------------


def test_q3_requires_list_today_exceptions(all_cases: list[EvalCase]) -> None:
    case = case_by_id(all_cases, "Q3")
    assert "list_today_exceptions" in case.required_tools


# ---------------------------------------------------------------------------
# (h) Q4 must require analyze_shipment_delay_causes
# ---------------------------------------------------------------------------


def test_q4_requires_analyze_shipment_delay_causes(all_cases: list[EvalCase]) -> None:
    case = case_by_id(all_cases, "Q4")
    assert "analyze_shipment_delay_causes" in case.required_tools


# ---------------------------------------------------------------------------
# (i) Q1 must_not_contain includes degenerate response phrases
# ---------------------------------------------------------------------------


_DEGENERATE_PHRASES = {"I don't have", "I'm sorry", "je", "Désolé"}


def test_q1_must_not_contain_degenerate_response(all_cases: list[EvalCase]) -> None:
    case = case_by_id(all_cases, "Q1")
    must_not = set(case.response_assertions.must_not_contain)
    assert _DEGENERATE_PHRASES & must_not, (
        f"Q1 must_not_contain {must_not!r} does not include any degenerate-response phrase "
        f"from {_DEGENERATE_PHRASES!r}"
    )


# ---------------------------------------------------------------------------
# (j) Q6 uses nl_query and must_not_use list_stockout_risk
# ---------------------------------------------------------------------------


def test_q6_requires_nl_query_not_list_stockout_risk(all_cases: list[EvalCase]) -> None:
    case = case_by_id(all_cases, "Q6")
    assert "nl_query" in case.required_tools
    assert "list_stockout_risk" in case.must_not_use_tools


# ---------------------------------------------------------------------------
# (k) Q9 must_not_use segment_demand
# ---------------------------------------------------------------------------


def test_q9_must_not_use_segment_demand(all_cases: list[EvalCase]) -> None:
    case = case_by_id(all_cases, "Q9")
    assert "segment_demand" in case.must_not_use_tools
