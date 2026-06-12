"""T-549 / T-551: Unit tests for detect_demand_shift_tool.

Covers:
- Schema contract: required keys present in output (window, customer_shifts, region_shifts,
  missing_data).
- Shift math: pct_change and abs_change computed correctly for normal, new_activity,
  and full_decline cases.
- Grouping: customer_id and region axes aggregated independently.
- No-baseline (prior_qty=0, current_qty>0) → activity_flag='new_activity', pct_change=null,
  entry in missing_data.
- Full-decline (prior_qty>0, current_qty=0) → activity_flag='full_decline', pct_change=-100.0.
- Both-zero group → excluded from output silently.
- Window parameter handling: custom window_days / end_date_offset.
- Cap + truncated: >50 shift records → truncated=True, lists capped.
- DB error → output contains error key.
- Top-SKU list: populated from SKU breakdown rows, sorted by abs abs_change, capped to 5.
"""
from __future__ import annotations

import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from packages.tools.base import ToolContext


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_ctx() -> ToolContext:
    return ToolContext(
        session_id=uuid4(),
        agent_step_id=uuid4(),
        specialist_role="control",
        actor="test",
        correlation_id=uuid4(),
    )


def _make_pool_with_two_fetches(
    agg_rows: list[Any],
    sku_rows: list[Any],
) -> MagicMock:
    """Return a pool mock whose conn.fetch returns agg_rows then sku_rows (twice each)."""
    mock_conn = AsyncMock()
    # The tool calls fetch 4 times total: customer agg, region agg, customer sku, region sku
    mock_conn.fetch.side_effect = [
        agg_rows,   # customer agg
        agg_rows,   # region agg (same data reused; tests override where needed)
        sku_rows,   # customer sku breakdown
        sku_rows,   # region sku breakdown
    ]
    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_pool


def _make_pool_seq(*fetch_seqs: list[Any]) -> MagicMock:
    """Return a pool mock with each call to fetch() returning the next seq."""
    mock_conn = AsyncMock()
    mock_conn.fetch.side_effect = list(fetch_seqs)
    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_pool


def _agg_row(group_id: str, prior_qty: int, current_qty: int) -> dict[str, Any]:
    return {"group_id": group_id, "prior_qty": prior_qty, "current_qty": current_qty}


def _sku_row(
    group_id: str,
    sku_id: str,
    prior_qty: int,
    current_qty: int,
) -> dict[str, Any]:
    return {
        "group_id": group_id,
        "sku_id": sku_id,
        "prior_qty": prior_qty,
        "current_qty": current_qty,
    }


# ---------------------------------------------------------------------------
# T-551: Schema contract
# ---------------------------------------------------------------------------


async def test_detect_demand_shift_returns_required_top_level_keys() -> None:
    """Output must include window, customer_shifts, region_shifts, missing_data."""
    from packages.tools.detect_demand_shift_tool import DetectDemandShiftTool

    mock_pool = _make_pool_seq([], [], [], [])
    with patch("packages.tools.detect_demand_shift_tool.get_pool", return_value=mock_pool):
        tool = DetectDemandShiftTool()
        result = await tool.handle({}, make_ctx())

    assert "window" in result.output
    assert "customer_shifts" in result.output
    assert "region_shifts" in result.output
    assert "missing_data" in result.output
    assert isinstance(result.output["missing_data"], list)


async def test_detect_demand_shift_window_has_required_keys() -> None:
    """window dict must have current_start, current_end, prior_start, prior_end, window_days."""
    from packages.tools.detect_demand_shift_tool import DetectDemandShiftTool

    mock_pool = _make_pool_seq([], [], [], [])
    with patch("packages.tools.detect_demand_shift_tool.get_pool", return_value=mock_pool):
        tool = DetectDemandShiftTool()
        result = await tool.handle({}, make_ctx())

    w = result.output["window"]
    for key in ("current_start", "current_end", "prior_start", "prior_end", "window_days"):
        assert key in w, f"window missing key: {key}"


async def test_detect_demand_shift_shifts_have_growth_decline_truncated() -> None:
    """customer_shifts and region_shifts must each have growth, decline, truncated."""
    from packages.tools.detect_demand_shift_tool import DetectDemandShiftTool

    mock_pool = _make_pool_seq([], [], [], [])
    with patch("packages.tools.detect_demand_shift_tool.get_pool", return_value=mock_pool):
        tool = DetectDemandShiftTool()
        result = await tool.handle({}, make_ctx())

    for axis in ("customer_shifts", "region_shifts"):
        assert "growth" in result.output[axis], f"{axis} missing 'growth'"
        assert "decline" in result.output[axis], f"{axis} missing 'decline'"
        assert "truncated" in result.output[axis], f"{axis} missing 'truncated'"


# ---------------------------------------------------------------------------
# T-551: Shift math
# ---------------------------------------------------------------------------


async def test_detect_demand_shift_pct_change_computed_correctly() -> None:
    """pct_change = (current - prior) / prior * 100 (rounded to 4 dp)."""
    from packages.tools.detect_demand_shift_tool import DetectDemandShiftTool

    # prior=100, current=150 → +50% exactly
    agg = [_agg_row("CUST-001", prior_qty=100, current_qty=150)]
    sku = [_sku_row("CUST-001", "SKU-001", prior_qty=100, current_qty=150)]
    mock_pool = _make_pool_seq(agg, [], sku, [])
    with patch("packages.tools.detect_demand_shift_tool.get_pool", return_value=mock_pool):
        tool = DetectDemandShiftTool()
        result = await tool.handle({}, make_ctx())

    growth = result.output["customer_shifts"]["growth"]
    assert len(growth) == 1
    rec = growth[0]
    assert rec["id"] == "CUST-001"
    assert rec["prior_qty"] == 100
    assert rec["current_qty"] == 150
    assert rec["abs_change"] == 50
    assert rec["pct_change"] == pytest.approx(50.0)
    assert rec["activity_flag"] is None


async def test_detect_demand_shift_abs_change_is_negative_for_decline() -> None:
    """A declining group must appear in 'decline' with negative abs_change."""
    from packages.tools.detect_demand_shift_tool import DetectDemandShiftTool

    # prior=200, current=50 → -75%
    agg = [_agg_row("CUST-010", prior_qty=200, current_qty=50)]
    sku = [_sku_row("CUST-010", "SKU-001", prior_qty=200, current_qty=50)]
    mock_pool = _make_pool_seq(agg, [], sku, [])
    with patch("packages.tools.detect_demand_shift_tool.get_pool", return_value=mock_pool):
        tool = DetectDemandShiftTool()
        result = await tool.handle({}, make_ctx())

    decline = result.output["customer_shifts"]["decline"]
    assert len(decline) == 1
    rec = decline[0]
    assert rec["id"] == "CUST-010"
    assert rec["abs_change"] == -150
    assert rec["pct_change"] == pytest.approx(-75.0)
    assert rec["activity_flag"] is None


# ---------------------------------------------------------------------------
# T-551: Baseline edge cases
# ---------------------------------------------------------------------------


async def test_detect_demand_shift_new_activity_pct_is_null() -> None:
    """prior_qty=0, current_qty>0 → pct_change=null, activity_flag='new_activity', in missing_data."""
    from packages.tools.detect_demand_shift_tool import DetectDemandShiftTool

    agg = [_agg_row("CUST-NEW", prior_qty=0, current_qty=100)]
    sku = [_sku_row("CUST-NEW", "SKU-001", prior_qty=0, current_qty=100)]
    mock_pool = _make_pool_seq(agg, [], sku, [])
    with patch("packages.tools.detect_demand_shift_tool.get_pool", return_value=mock_pool):
        tool = DetectDemandShiftTool()
        result = await tool.handle({}, make_ctx())

    growth = result.output["customer_shifts"]["growth"]
    assert len(growth) == 1
    rec = growth[0]
    assert rec["pct_change"] is None
    assert rec["activity_flag"] == "new_activity"
    assert any("new_activity" in m or "CUST-NEW" in m for m in result.output["missing_data"])


async def test_detect_demand_shift_full_decline_pct_is_minus_100() -> None:
    """prior_qty>0, current_qty=0 → pct_change=-100.0, activity_flag='full_decline'."""
    from packages.tools.detect_demand_shift_tool import DetectDemandShiftTool

    agg = [_agg_row("CUST-GONE", prior_qty=150, current_qty=0)]
    sku = [_sku_row("CUST-GONE", "SKU-001", prior_qty=150, current_qty=0)]
    mock_pool = _make_pool_seq(agg, [], sku, [])
    with patch("packages.tools.detect_demand_shift_tool.get_pool", return_value=mock_pool):
        tool = DetectDemandShiftTool()
        result = await tool.handle({}, make_ctx())

    decline = result.output["customer_shifts"]["decline"]
    assert len(decline) == 1
    rec = decline[0]
    assert rec["pct_change"] == pytest.approx(-100.0)
    assert rec["activity_flag"] == "full_decline"


async def test_detect_demand_shift_both_zero_group_excluded() -> None:
    """prior_qty=0 and current_qty=0 → group must not appear in output."""
    from packages.tools.detect_demand_shift_tool import DetectDemandShiftTool

    # In practice the SQL HAVING clause filters these out, but test pure Python logic too.
    agg = [
        _agg_row("CUST-EMPTY", prior_qty=0, current_qty=0),
        _agg_row("CUST-REAL", prior_qty=100, current_qty=150),
    ]
    sku = [_sku_row("CUST-REAL", "SKU-001", prior_qty=100, current_qty=150)]
    mock_pool = _make_pool_seq(agg, [], sku, [])
    with patch("packages.tools.detect_demand_shift_tool.get_pool", return_value=mock_pool):
        tool = DetectDemandShiftTool()
        result = await tool.handle({}, make_ctx())

    all_ids = [
        r["id"]
        for r in result.output["customer_shifts"]["growth"]
        + result.output["customer_shifts"]["decline"]
    ]
    assert "CUST-EMPTY" not in all_ids
    assert "CUST-REAL" in all_ids


# ---------------------------------------------------------------------------
# T-551: Grouping axes
# ---------------------------------------------------------------------------


async def test_detect_demand_shift_groups_independently_by_customer_and_region() -> None:
    """customer_shifts and region_shifts are populated from independent query calls."""
    from packages.tools.detect_demand_shift_tool import DetectDemandShiftTool

    cust_agg = [_agg_row("CUST-009", prior_qty=50, current_qty=150)]
    region_agg = [_agg_row("Kanto", prior_qty=50, current_qty=150)]
    cust_sku = [_sku_row("CUST-009", "SKU-001", prior_qty=50, current_qty=150)]
    region_sku = [_sku_row("Kanto", "SKU-001", prior_qty=50, current_qty=150)]
    mock_pool = _make_pool_seq(cust_agg, region_agg, cust_sku, region_sku)
    with patch("packages.tools.detect_demand_shift_tool.get_pool", return_value=mock_pool):
        tool = DetectDemandShiftTool()
        result = await tool.handle({}, make_ctx())

    assert result.output["customer_shifts"]["growth"][0]["id"] == "CUST-009"
    assert result.output["region_shifts"]["growth"][0]["id"] == "Kanto"


# ---------------------------------------------------------------------------
# T-551: Window parameter handling
# ---------------------------------------------------------------------------


async def test_detect_demand_shift_default_window_is_28_days() -> None:
    """With no parameters, window.window_days must be 28."""
    from packages.tools.detect_demand_shift_tool import DetectDemandShiftTool

    mock_pool = _make_pool_seq([], [], [], [])
    with patch("packages.tools.detect_demand_shift_tool.get_pool", return_value=mock_pool):
        tool = DetectDemandShiftTool()
        result = await tool.handle({}, make_ctx())

    assert result.output["window"]["window_days"] == 28


async def test_detect_demand_shift_custom_window_days_reflected_in_output() -> None:
    """window_days=14 must be reflected in window dict and date boundaries."""
    from packages.tools.detect_demand_shift_tool import DetectDemandShiftTool

    mock_pool = _make_pool_seq([], [], [], [])
    with patch("packages.tools.detect_demand_shift_tool.get_pool", return_value=mock_pool):
        tool = DetectDemandShiftTool()
        result = await tool.handle({"window_days": 14}, make_ctx())

    w = result.output["window"]
    assert w["window_days"] == 14
    current_start = datetime.date.fromisoformat(w["current_start"])
    current_end = datetime.date.fromisoformat(w["current_end"])
    assert (current_end - current_start).days == 13  # 14-day window inclusive


async def test_detect_demand_shift_invalid_window_days_returns_error() -> None:
    """window_days=0 must return an output dict with an error key."""
    from packages.tools.detect_demand_shift_tool import DetectDemandShiftTool

    tool = DetectDemandShiftTool()
    result = await tool.handle({"window_days": 0}, make_ctx())
    assert "error" in result.output


# ---------------------------------------------------------------------------
# T-551: Cap + truncated
# ---------------------------------------------------------------------------


async def test_detect_demand_shift_truncated_when_more_than_50_growth_records() -> None:
    """51 growing customer records → truncated=True, growth list capped at 50."""
    from packages.tools.detect_demand_shift_tool import DetectDemandShiftTool

    agg = [
        _agg_row(f"CUST-{i:03d}", prior_qty=10, current_qty=20 + i)
        for i in range(51)
    ]
    mock_pool = _make_pool_seq(agg, [], [], [])
    with patch("packages.tools.detect_demand_shift_tool.get_pool", return_value=mock_pool):
        tool = DetectDemandShiftTool()
        result = await tool.handle({}, make_ctx())

    assert result.output["customer_shifts"]["truncated"] is True
    assert len(result.output["customer_shifts"]["growth"]) == 50


async def test_detect_demand_shift_not_truncated_for_50_records() -> None:
    """Exactly 50 growing customer records → truncated=False."""
    from packages.tools.detect_demand_shift_tool import DetectDemandShiftTool

    agg = [
        _agg_row(f"CUST-{i:03d}", prior_qty=10, current_qty=20 + i)
        for i in range(50)
    ]
    mock_pool = _make_pool_seq(agg, [], [], [])
    with patch("packages.tools.detect_demand_shift_tool.get_pool", return_value=mock_pool):
        tool = DetectDemandShiftTool()
        result = await tool.handle({}, make_ctx())

    assert result.output["customer_shifts"]["truncated"] is False
    assert len(result.output["customer_shifts"]["growth"]) == 50


# ---------------------------------------------------------------------------
# T-551: Top-SKU list
# ---------------------------------------------------------------------------


async def test_detect_demand_shift_top_skus_sorted_by_abs_change_desc() -> None:
    """top_skus within a shift record must be sorted by abs(abs_change) descending."""
    from packages.tools.detect_demand_shift_tool import DetectDemandShiftTool

    agg = [_agg_row("CUST-001", prior_qty=100, current_qty=400)]
    sku = [
        _sku_row("CUST-001", "SKU-A", prior_qty=50, current_qty=100),   # abs=50
        _sku_row("CUST-001", "SKU-B", prior_qty=50, current_qty=300),   # abs=250
    ]
    mock_pool = _make_pool_seq(agg, [], sku, [])
    with patch("packages.tools.detect_demand_shift_tool.get_pool", return_value=mock_pool):
        tool = DetectDemandShiftTool()
        result = await tool.handle({}, make_ctx())

    growth = result.output["customer_shifts"]["growth"]
    assert len(growth) == 1
    top_skus = growth[0]["top_skus"]
    assert len(top_skus) == 2
    assert top_skus[0]["sku_id"] == "SKU-B"  # larger abs change first
    assert top_skus[1]["sku_id"] == "SKU-A"


async def test_detect_demand_shift_top_skus_capped_at_5() -> None:
    """top_skus must contain at most 5 entries even if more SKUs changed."""
    from packages.tools.detect_demand_shift_tool import DetectDemandShiftTool

    agg = [_agg_row("CUST-001", prior_qty=100, current_qty=700)]
    sku = [
        _sku_row("CUST-001", f"SKU-{i:02d}", prior_qty=10, current_qty=100)
        for i in range(10)
    ]
    mock_pool = _make_pool_seq(agg, [], sku, [])
    with patch("packages.tools.detect_demand_shift_tool.get_pool", return_value=mock_pool):
        tool = DetectDemandShiftTool()
        result = await tool.handle({}, make_ctx())

    growth = result.output["customer_shifts"]["growth"]
    assert len(growth[0]["top_skus"]) == 5


# ---------------------------------------------------------------------------
# T-551: DB error path
# ---------------------------------------------------------------------------


async def test_detect_demand_shift_db_error_returns_error_key() -> None:
    """When get_pool raises, output must contain an 'error' key."""
    from packages.tools.detect_demand_shift_tool import DetectDemandShiftTool

    with patch(
        "packages.tools.detect_demand_shift_tool.get_pool",
        side_effect=RuntimeError("DATABASE_URL not set"),
    ):
        tool = DetectDemandShiftTool()
        result = await tool.handle({}, make_ctx())

    assert "error" in result.output


# ---------------------------------------------------------------------------
# T-551: Sorting direction
# ---------------------------------------------------------------------------


async def test_detect_demand_shift_growth_sorted_highest_first() -> None:
    """Growth list must be sorted by abs_change descending (highest growth first)."""
    from packages.tools.detect_demand_shift_tool import DetectDemandShiftTool

    agg = [
        _agg_row("CUST-A", prior_qty=100, current_qty=110),   # +10
        _agg_row("CUST-B", prior_qty=100, current_qty=200),   # +100
        _agg_row("CUST-C", prior_qty=100, current_qty=150),   # +50
    ]
    mock_pool = _make_pool_seq(agg, [], [], [])
    with patch("packages.tools.detect_demand_shift_tool.get_pool", return_value=mock_pool):
        tool = DetectDemandShiftTool()
        result = await tool.handle({}, make_ctx())

    ids = [r["id"] for r in result.output["customer_shifts"]["growth"]]
    assert ids == ["CUST-B", "CUST-C", "CUST-A"]


async def test_detect_demand_shift_decline_sorted_most_negative_first() -> None:
    """Decline list must be sorted by abs_change ascending (most negative first)."""
    from packages.tools.detect_demand_shift_tool import DetectDemandShiftTool

    agg = [
        _agg_row("CUST-A", prior_qty=200, current_qty=190),   # -10
        _agg_row("CUST-B", prior_qty=200, current_qty=100),   # -100
        _agg_row("CUST-C", prior_qty=200, current_qty=150),   # -50
    ]
    mock_pool = _make_pool_seq(agg, [], [], [])
    with patch("packages.tools.detect_demand_shift_tool.get_pool", return_value=mock_pool):
        tool = DetectDemandShiftTool()
        result = await tool.handle({}, make_ctx())

    ids = [r["id"] for r in result.output["customer_shifts"]["decline"]]
    assert ids == ["CUST-B", "CUST-C", "CUST-A"]


# ---------------------------------------------------------------------------
# T-551: Seed scenario — growth and decline (pure-Python logic, no DB)
# ---------------------------------------------------------------------------


async def test_detect_demand_shift_seed_growth_scenario() -> None:
    """CUST-009 growth signal: prior=50 (1 order), current=150 (3 orders × 50)."""
    from packages.tools.detect_demand_shift_tool import DetectDemandShiftTool

    # Mirrors seed: 1 order × 50 qty prior, 3 orders × 50 qty current
    agg = [_agg_row("CUST-009", prior_qty=50, current_qty=150)]
    sku = [_sku_row("CUST-009", "SKU-SEED", prior_qty=50, current_qty=150)]
    mock_pool = _make_pool_seq(agg, [], sku, [])
    with patch("packages.tools.detect_demand_shift_tool.get_pool", return_value=mock_pool):
        tool = DetectDemandShiftTool()
        result = await tool.handle({}, make_ctx())

    growth = result.output["customer_shifts"]["growth"]
    assert len(growth) == 1
    rec = growth[0]
    assert rec["id"] == "CUST-009"
    assert rec["abs_change"] == 100
    assert rec["pct_change"] == pytest.approx(200.0)
    assert rec["activity_flag"] is None


async def test_detect_demand_shift_seed_decline_scenario() -> None:
    """CUST-010 decline signal: prior=150 (3 orders × 50), current=50 (1 order × 50)."""
    from packages.tools.detect_demand_shift_tool import DetectDemandShiftTool

    agg = [_agg_row("CUST-010", prior_qty=150, current_qty=50)]
    sku = [_sku_row("CUST-010", "SKU-SEED", prior_qty=150, current_qty=50)]
    mock_pool = _make_pool_seq(agg, [], sku, [])
    with patch("packages.tools.detect_demand_shift_tool.get_pool", return_value=mock_pool):
        tool = DetectDemandShiftTool()
        result = await tool.handle({}, make_ctx())

    decline = result.output["customer_shifts"]["decline"]
    assert len(decline) == 1
    rec = decline[0]
    assert rec["id"] == "CUST-010"
    assert rec["abs_change"] == -100
    assert rec["pct_change"] == pytest.approx(-66.6667, rel=1e-3)
    assert rec["activity_flag"] is None


async def test_detect_demand_shift_seed_kanto_growth_region() -> None:
    """Kanto region growth mirrors CUST-009 seed signal."""
    from packages.tools.detect_demand_shift_tool import DetectDemandShiftTool

    cust_agg = [_agg_row("CUST-009", prior_qty=50, current_qty=150)]
    region_agg = [_agg_row("Kanto", prior_qty=50, current_qty=150)]
    cust_sku = [_sku_row("CUST-009", "SKU-SEED", prior_qty=50, current_qty=150)]
    region_sku = [_sku_row("Kanto", "SKU-SEED", prior_qty=50, current_qty=150)]
    mock_pool = _make_pool_seq(cust_agg, region_agg, cust_sku, region_sku)
    with patch("packages.tools.detect_demand_shift_tool.get_pool", return_value=mock_pool):
        tool = DetectDemandShiftTool()
        result = await tool.handle({}, make_ctx())

    region_growth = result.output["region_shifts"]["growth"]
    assert len(region_growth) == 1
    assert region_growth[0]["id"] == "Kanto"
    assert region_growth[0]["abs_change"] == 100


async def test_detect_demand_shift_seed_kansai_decline_region() -> None:
    """Kansai region decline mirrors CUST-010 seed signal."""
    from packages.tools.detect_demand_shift_tool import DetectDemandShiftTool

    cust_agg = [_agg_row("CUST-010", prior_qty=150, current_qty=50)]
    region_agg = [_agg_row("Kansai", prior_qty=150, current_qty=50)]
    cust_sku = [_sku_row("CUST-010", "SKU-SEED", prior_qty=150, current_qty=50)]
    region_sku = [_sku_row("Kansai", "SKU-SEED", prior_qty=150, current_qty=50)]
    mock_pool = _make_pool_seq(cust_agg, region_agg, cust_sku, region_sku)
    with patch("packages.tools.detect_demand_shift_tool.get_pool", return_value=mock_pool):
        tool = DetectDemandShiftTool()
        result = await tool.handle({}, make_ctx())

    region_decline = result.output["region_shifts"]["decline"]
    assert len(region_decline) == 1
    assert region_decline[0]["id"] == "Kansai"
    assert region_decline[0]["abs_change"] == -100
