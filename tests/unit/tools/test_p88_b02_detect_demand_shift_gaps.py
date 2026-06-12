"""T-551: Gap-fill unit tests for detect_demand_shift_tool.

Closes the five gaps identified in the P88 B-01 batch check:
  1. prior window length equals window_days
  2. adjacency invariant: prior_end + 1 day == current_start (no gap/overlap)
  3. truncated semantics: mixed 30 growth + 30 decline → truncated=False;
     >50 in one list → True (per-list pre-cap check)
  4. end_date_offset != 1 shifts all four window dates correctly
  5. window date values round-trip via date.fromisoformat

Zero network; asyncio auto mode; naming convention: test_<subject>_<condition>_<expected>.
"""
from __future__ import annotations

import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from packages.tools.base import ToolContext


# ---------------------------------------------------------------------------
# Helpers (mirror the helpers in the B-01 test file)
# ---------------------------------------------------------------------------


def make_ctx() -> ToolContext:
    return ToolContext(
        session_id=uuid4(),
        agent_step_id=uuid4(),
        specialist_role="control",
        actor="test",
        correlation_id=uuid4(),
    )


def _make_pool_seq(*fetch_seqs: list[Any]) -> MagicMock:
    """Pool mock that returns each positional arg as the result of successive fetch() calls."""
    mock_conn = AsyncMock()
    mock_conn.fetch.side_effect = list(fetch_seqs)
    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_pool


def _agg_row(group_id: str, prior_qty: int, current_qty: int) -> dict[str, Any]:
    return {"group_id": group_id, "prior_qty": prior_qty, "current_qty": current_qty}


# ---------------------------------------------------------------------------
# Gap 1 — prior window length equals window_days
# ---------------------------------------------------------------------------


async def test_detect_demand_shift_prior_window_length_equals_window_days_default() -> None:
    """With default window_days=28, prior window span must also be 28 days inclusive."""
    from packages.tools.detect_demand_shift_tool import DetectDemandShiftTool

    mock_pool = _make_pool_seq([], [], [], [])
    with patch("packages.tools.detect_demand_shift_tool.get_pool", return_value=mock_pool):
        tool = DetectDemandShiftTool()
        result = await tool.handle({}, make_ctx())

    w = result.output["window"]
    prior_start = datetime.date.fromisoformat(w["prior_start"])
    prior_end = datetime.date.fromisoformat(w["prior_end"])
    # Inclusive length: end - start + 1 == window_days
    assert (prior_end - prior_start).days + 1 == w["window_days"], (
        f"prior window span {(prior_end - prior_start).days + 1} != window_days {w['window_days']}"
    )


async def test_detect_demand_shift_prior_window_length_equals_window_days_custom() -> None:
    """With window_days=14, prior window span must also be exactly 14 days inclusive."""
    from packages.tools.detect_demand_shift_tool import DetectDemandShiftTool

    mock_pool = _make_pool_seq([], [], [], [])
    with patch("packages.tools.detect_demand_shift_tool.get_pool", return_value=mock_pool):
        tool = DetectDemandShiftTool()
        result = await tool.handle({"window_days": 14}, make_ctx())

    w = result.output["window"]
    prior_start = datetime.date.fromisoformat(w["prior_start"])
    prior_end = datetime.date.fromisoformat(w["prior_end"])
    assert (prior_end - prior_start).days + 1 == 14, (
        f"prior window span {(prior_end - prior_start).days + 1} != 14"
    )


# ---------------------------------------------------------------------------
# Gap 2 — adjacency invariant: prior_end + 1 day == current_start
# ---------------------------------------------------------------------------


async def test_detect_demand_shift_windows_are_adjacent_no_gap_default() -> None:
    """prior_end + 1 day must equal current_start (no day gap, no overlap) — default params."""
    from packages.tools.detect_demand_shift_tool import DetectDemandShiftTool

    mock_pool = _make_pool_seq([], [], [], [])
    with patch("packages.tools.detect_demand_shift_tool.get_pool", return_value=mock_pool):
        tool = DetectDemandShiftTool()
        result = await tool.handle({}, make_ctx())

    w = result.output["window"]
    prior_end = datetime.date.fromisoformat(w["prior_end"])
    current_start = datetime.date.fromisoformat(w["current_start"])
    assert prior_end + datetime.timedelta(days=1) == current_start, (
        f"Windows not adjacent: prior_end={prior_end}, current_start={current_start}"
    )


async def test_detect_demand_shift_windows_are_adjacent_no_gap_custom_window() -> None:
    """prior_end + 1 day must equal current_start with custom window_days=7."""
    from packages.tools.detect_demand_shift_tool import DetectDemandShiftTool

    mock_pool = _make_pool_seq([], [], [], [])
    with patch("packages.tools.detect_demand_shift_tool.get_pool", return_value=mock_pool):
        tool = DetectDemandShiftTool()
        result = await tool.handle({"window_days": 7}, make_ctx())

    w = result.output["window"]
    prior_end = datetime.date.fromisoformat(w["prior_end"])
    current_start = datetime.date.fromisoformat(w["current_start"])
    assert prior_end + datetime.timedelta(days=1) == current_start, (
        f"Windows not adjacent: prior_end={prior_end}, current_start={current_start}"
    )


# ---------------------------------------------------------------------------
# Gap 3 — truncated semantics: per-list pre-cap check
# ---------------------------------------------------------------------------


async def test_detect_demand_shift_truncated_false_when_30_growth_and_30_decline() -> None:
    """30 growth + 30 decline records → truncated=False (neither list exceeds 50)."""
    from packages.tools.detect_demand_shift_tool import DetectDemandShiftTool

    growth_rows = [
        _agg_row(f"CUST-G{i:03d}", prior_qty=10, current_qty=20 + i)
        for i in range(30)
    ]
    decline_rows = [
        _agg_row(f"CUST-D{i:03d}", prior_qty=20 + i, current_qty=10)
        for i in range(30)
    ]
    agg = growth_rows + decline_rows
    mock_pool = _make_pool_seq(agg, [], [], [])
    with patch("packages.tools.detect_demand_shift_tool.get_pool", return_value=mock_pool):
        tool = DetectDemandShiftTool()
        result = await tool.handle({}, make_ctx())

    cs = result.output["customer_shifts"]
    assert cs["truncated"] is False, (
        f"Expected truncated=False for 30 growth + 30 decline, got {cs['truncated']}"
    )
    assert len(cs["growth"]) == 30
    assert len(cs["decline"]) == 30


async def test_detect_demand_shift_truncated_true_when_51_growth_records() -> None:
    """51 growth records → truncated=True, list capped at 50 (per-list check)."""
    from packages.tools.detect_demand_shift_tool import DetectDemandShiftTool

    agg = [
        _agg_row(f"CUST-G{i:03d}", prior_qty=10, current_qty=20 + i)
        for i in range(51)
    ]
    mock_pool = _make_pool_seq(agg, [], [], [])
    with patch("packages.tools.detect_demand_shift_tool.get_pool", return_value=mock_pool):
        tool = DetectDemandShiftTool()
        result = await tool.handle({}, make_ctx())

    cs = result.output["customer_shifts"]
    assert cs["truncated"] is True
    assert len(cs["growth"]) == 50


async def test_detect_demand_shift_truncated_true_when_51_decline_records() -> None:
    """51 decline records and 0 growth → truncated=True (decline list exceeds cap)."""
    from packages.tools.detect_demand_shift_tool import DetectDemandShiftTool

    agg = [
        _agg_row(f"CUST-D{i:03d}", prior_qty=20 + i, current_qty=10)
        for i in range(51)
    ]
    mock_pool = _make_pool_seq(agg, [], [], [])
    with patch("packages.tools.detect_demand_shift_tool.get_pool", return_value=mock_pool):
        tool = DetectDemandShiftTool()
        result = await tool.handle({}, make_ctx())

    cs = result.output["customer_shifts"]
    assert cs["truncated"] is True
    assert len(cs["decline"]) == 50


# ---------------------------------------------------------------------------
# Gap 4 — end_date_offset != 1 shifts all four window dates correctly
# ---------------------------------------------------------------------------


async def test_detect_demand_shift_end_date_offset_shifts_all_four_dates() -> None:
    """end_date_offset=10 must shift current_end, current_start, prior_end, prior_start by 9 days
    relative to end_date_offset=1 (the default).

    With end_date_offset=1:  current_end = today - 1
    With end_date_offset=10: current_end = today - 10
    All four dates shift backward by (10 - 1) = 9 days.
    """
    from packages.tools.detect_demand_shift_tool import DetectDemandShiftTool

    today = datetime.date.today()

    mock_pool_default = _make_pool_seq([], [], [], [])
    with patch("packages.tools.detect_demand_shift_tool.get_pool", return_value=mock_pool_default):
        tool = DetectDemandShiftTool()
        result_default = await tool.handle({"end_date_offset": 1}, make_ctx())

    mock_pool_offset = _make_pool_seq([], [], [], [])
    with patch("packages.tools.detect_demand_shift_tool.get_pool", return_value=mock_pool_offset):
        tool2 = DetectDemandShiftTool()
        result_offset = await tool2.handle({"end_date_offset": 10}, make_ctx())

    w_default = result_default.output["window"]
    w_offset = result_offset.output["window"]

    shift_days = 9  # 10 - 1

    for key in ("current_end", "current_start", "prior_end", "prior_start"):
        date_default = datetime.date.fromisoformat(w_default[key])
        date_offset = datetime.date.fromisoformat(w_offset[key])
        expected = date_default - datetime.timedelta(days=shift_days)
        assert date_offset == expected, (
            f"{key}: offset window gave {date_offset}, expected {expected} "
            f"({shift_days} days before default {date_default})"
        )

    # Also verify absolute current_end value
    expected_current_end = today - datetime.timedelta(days=10)
    actual_current_end = datetime.date.fromisoformat(w_offset["current_end"])
    assert actual_current_end == expected_current_end, (
        f"current_end with offset=10: expected {expected_current_end}, got {actual_current_end}"
    )


async def test_detect_demand_shift_end_date_offset_zero_yields_current_end_today() -> None:
    """end_date_offset=0 must set current_end to today (include today).

    Regression guard for the `int(input.get("end_date_offset") or 1)` bug where
    explicit 0 was silently coerced to 1 via Python's truthiness evaluation.
    """
    from packages.tools.detect_demand_shift_tool import DetectDemandShiftTool

    today = datetime.date.today()

    mock_pool = _make_pool_seq([], [], [], [])
    with patch("packages.tools.detect_demand_shift_tool.get_pool", return_value=mock_pool):
        tool = DetectDemandShiftTool()
        result = await tool.handle({"end_date_offset": 0}, make_ctx())

    current_end = datetime.date.fromisoformat(result.output["window"]["current_end"])
    assert current_end == today, (
        f"end_date_offset=0 should give current_end=today ({today}), got {current_end}"
    )


# ---------------------------------------------------------------------------
# Gap 5 — all four window date values round-trip via date.fromisoformat
# ---------------------------------------------------------------------------


async def test_detect_demand_shift_all_window_dates_roundtrip_fromisoformat() -> None:
    """All four window date strings must be valid ISO-format dates (YYYY-MM-DD)."""
    from packages.tools.detect_demand_shift_tool import DetectDemandShiftTool

    mock_pool = _make_pool_seq([], [], [], [])
    with patch("packages.tools.detect_demand_shift_tool.get_pool", return_value=mock_pool):
        tool = DetectDemandShiftTool()
        result = await tool.handle({}, make_ctx())

    w = result.output["window"]
    for key in ("current_start", "current_end", "prior_start", "prior_end"):
        raw = w[key]
        assert isinstance(raw, str), f"window[{key!r}] is not a string: {raw!r}"
        parsed = datetime.date.fromisoformat(raw)
        assert parsed.isoformat() == raw, (
            f"window[{key!r}] round-trip failed: {raw!r} → {parsed.isoformat()!r}"
        )


async def test_detect_demand_shift_all_window_dates_roundtrip_fromisoformat_custom_params() -> None:
    """Round-trip holds for non-default window_days and end_date_offset."""
    from packages.tools.detect_demand_shift_tool import DetectDemandShiftTool

    mock_pool = _make_pool_seq([], [], [], [])
    with patch("packages.tools.detect_demand_shift_tool.get_pool", return_value=mock_pool):
        tool = DetectDemandShiftTool()
        result = await tool.handle({"window_days": 7, "end_date_offset": 3}, make_ctx())

    w = result.output["window"]
    for key in ("current_start", "current_end", "prior_start", "prior_end"):
        raw = w[key]
        parsed = datetime.date.fromisoformat(raw)
        assert parsed.isoformat() == raw, (
            f"window[{key!r}] round-trip failed with custom params: {raw!r}"
        )
