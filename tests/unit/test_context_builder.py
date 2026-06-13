from __future__ import annotations

import pytest

from packages.agent.control.context_builder import ContextBuilder
from packages.schemas.context_packs import GENERIC_PACK, USE_CASE_PACKS, ContextPack


# ---------------------------------------------------------------------------
# build() routing tests
# ---------------------------------------------------------------------------


async def test_build_q1_keywords_return_q1_pack() -> None:
    pack = await ContextBuilder().build(
        "supply_chain", "which products are at risk of stockout"
    )
    assert pack.use_case_id == "Q1"


async def test_build_q1_keyword_running_low_returns_q1_pack() -> None:
    """P116 B-03: 'running low' paraphrase must classify as Q1 stockout risk.

    'running low' was added to _USE_CASE_KEYWORDS['Q1'] in B-03 to cover
    paraphrases of the stockout-risk question.
    """
    pack = await ContextBuilder().build(
        "supply_chain", "which products are running low on inventory"
    )
    assert pack.use_case_id == "Q1"


async def test_build_q5_keyword_actual_vs_forecast_returns_q5_pack() -> None:
    """P116 B-03: 'actual vs forecast' must classify as Q5 forecast gap analysis.

    'actual vs forecast' was added to _USE_CASE_KEYWORDS['Q5'] to cover
    the paraphrase where the user places 'actual' before 'forecast'.
    """
    pack = await ContextBuilder().build(
        "domain_analysis", "show me the actual vs forecast for last month"
    )
    assert pack.use_case_id == "Q5"


async def test_build_q6_keyword_supply_gap_returns_q6_pack() -> None:
    """P116 B-03: 'supply gap' must classify as Q6 forward supply shortage.

    'supply gap' was added to _USE_CASE_KEYWORDS['Q6'] so users asking about
    supply adequacy without using the word 'shortage' still route to Q6.
    """
    pack = await ContextBuilder().build(
        "supply_chain", "what is the supply gap over the next 30 days"
    )
    assert pack.use_case_id == "Q6"


async def test_build_q9_keyword_demand_change_returns_q9_pack() -> None:
    """P116 B-03: 'demand change' (singular, no 's') must classify as Q9.

    'demand change' was added to _USE_CASE_KEYWORDS['Q9'] as a paraphrase for
    demand shift by customer/region; the existing keyword 'demand changes' already
    covered the plural form.
    """
    pack = await ContextBuilder().build(
        "domain_analysis", "has there been a demand change from any key customer"
    )
    assert pack.use_case_id == "Q9"


async def test_build_q3_keyword_exception_returns_q3_pack() -> None:
    pack = await ContextBuilder().build(
        "supply_chain", "what exceptions require attention today"
    )
    assert pack.use_case_id == "Q3"


async def test_build_q6_keyword_supply_shortage_returns_q6_pack() -> None:
    pack = await ContextBuilder().build(
        "supply_chain", "which products may face supply shortage next week"
    )
    assert pack.use_case_id == "Q6"


async def test_build_q9_keyword_demand_shift_returns_q9_pack() -> None:
    pack = await ContextBuilder().build(
        "domain_analysis", "are there demand changes by customer or region"
    )
    assert pack.use_case_id == "Q9"


async def test_build_unrelated_input_returns_generic_pack() -> None:
    pack = await ContextBuilder().build("supply_chain", "hello")
    assert pack.use_case_id == "GENERIC"


# ---------------------------------------------------------------------------
# ContextPack field sanity checks
# ---------------------------------------------------------------------------


async def test_build_generic_pack_has_empty_prohibited_tools() -> None:
    pack = await ContextBuilder().build("supply_chain", "hello")
    assert pack.prohibited_tools == []


def test_q1_pack_prohibited_tools_excludes_list_stockout_risk() -> None:
    """Q1's required tool must not appear in its own prohibited_tools."""
    assert "list_stockout_risk" not in USE_CASE_PACKS["Q1"].prohibited_tools


def test_q6_pack_prohibits_list_stockout_risk() -> None:
    assert "list_stockout_risk" in USE_CASE_PACKS["Q6"].prohibited_tools


def test_q9_pack_prohibits_segment_demand() -> None:
    assert "segment_demand" in USE_CASE_PACKS["Q9"].prohibited_tools


# ---------------------------------------------------------------------------
# Parametrized coverage over all non-GENERIC packs
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("pack", list(USE_CASE_PACKS.values()))
def test_all_use_case_packs_have_required_tools(pack: ContextPack) -> None:
    assert len(pack.required_tools) >= 1


# ---------------------------------------------------------------------------
# Type check
# ---------------------------------------------------------------------------


async def test_build_returns_context_pack_instance() -> None:
    result = await ContextBuilder().build("supply_chain", "which products are at risk of stockout")
    assert isinstance(result, ContextPack)
