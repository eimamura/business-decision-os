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
