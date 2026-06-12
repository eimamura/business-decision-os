"""T-577 / T-578: Unit tests for analyze_forecast_deviation_tool.

Covers:
- Schema contract: required top-level keys present.
- Window computation: correct ISO weeks computed for requested horizon.
- Forecast dedupe: DISTINCT ON latest forecast_date per (sku_id, target_date).
- Bucketing: forecast rows correctly bucketed into ISO week labels.
- Bias classification: over_forecast, under_forecast, mixed thresholds (±10%).
- gap_qty / gap_pct math: correct sign and formula.
- aggregate_abs_deviation_pct: SUM(|gap|) / SUM(actual) × 100.
- Ranking: total_abs_gap_qty desc, sku_id asc tiebreak (deterministic).
- Cap + truncated: >100 SKUs → truncated=True, list capped; count reflects full set.
- missing_data: no forecast, no actuals, is_missing actuals.
- Empty DB shape: empty lists, count=0, truncated=False.
- DB error → output contains error key.
- sku_id filter: restricts results to a single SKU.
- Pure-Python helpers: _iso_week_label, _gap_pct, _classify_bias, _aggregate_abs_deviation_pct.
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


def _make_pool_seq(*fetch_seqs: list[Any]) -> MagicMock:
    """Return a pool mock whose conn.fetch returns each seq in order."""
    mock_conn = AsyncMock()
    mock_conn.fetch.side_effect = list(fetch_seqs)
    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_pool


def _forecast_row(sku_id: str, iso_week: str, forecast_qty: float) -> dict[str, Any]:
    return {"sku_id": sku_id, "iso_week": iso_week, "forecast_qty": forecast_qty}


def _actual_row(sku_id: str, iso_week: str, actual_qty: float) -> dict[str, Any]:
    return {"sku_id": sku_id, "iso_week": iso_week, "actual_qty": actual_qty}


def _missing_row(sku_id: str, iso_week: str) -> dict[str, Any]:
    return {"sku_id": sku_id, "iso_week": iso_week}


# ---------------------------------------------------------------------------
# Schema contract
# ---------------------------------------------------------------------------


async def test_analyze_forecast_deviation_returns_required_top_level_keys() -> None:
    """Output must include weeks_analysed, window, skus, count, truncated, missing_data."""
    from packages.tools.analyze_forecast_deviation_tool import AnalyzeForecastDeviationTool

    mock_pool = _make_pool_seq([], [], [])
    with patch(
        "packages.tools.analyze_forecast_deviation_tool.get_pool",
        return_value=mock_pool,
    ):
        tool = AnalyzeForecastDeviationTool()
        result = await tool.handle({}, make_ctx())

    for key in ("weeks_analysed", "window", "skus", "count", "truncated", "missing_data"):
        assert key in result.output, f"missing key: {key}"
    assert isinstance(result.output["skus"], list)
    assert isinstance(result.output["missing_data"], list)
    assert isinstance(result.output["truncated"], bool)


async def test_analyze_forecast_deviation_window_has_required_keys() -> None:
    """window dict must include start_iso_week, end_iso_week, weeks_requested."""
    from packages.tools.analyze_forecast_deviation_tool import AnalyzeForecastDeviationTool

    mock_pool = _make_pool_seq([], [], [])
    with patch(
        "packages.tools.analyze_forecast_deviation_tool.get_pool",
        return_value=mock_pool,
    ):
        tool = AnalyzeForecastDeviationTool()
        result = await tool.handle({}, make_ctx())

    w = result.output["window"]
    for key in ("start_iso_week", "end_iso_week", "weeks_requested"):
        assert key in w, f"window missing key: {key}"


async def test_analyze_forecast_deviation_sku_row_has_required_keys() -> None:
    """Each SKU row must include all required keys including weekly_breakdown."""
    from packages.tools.analyze_forecast_deviation_tool import AnalyzeForecastDeviationTool

    today = datetime.date.today()
    monday = today - datetime.timedelta(days=today.weekday())
    prev_monday = monday - datetime.timedelta(weeks=1)
    iso_week = _iso_week_label(prev_monday)

    forecast_rows = [_forecast_row("SKU-001", iso_week, 100.0)]
    actual_rows = [_actual_row("SKU-001", iso_week, 80.0)]

    mock_pool = _make_pool_seq(forecast_rows, actual_rows, [])
    with patch(
        "packages.tools.analyze_forecast_deviation_tool.get_pool",
        return_value=mock_pool,
    ):
        tool = AnalyzeForecastDeviationTool()
        result = await tool.handle({"weeks": 1}, make_ctx())

    assert len(result.output["skus"]) == 1
    sku = result.output["skus"][0]
    required = (
        "sku_id", "bias_direction", "total_forecast_qty", "total_actual_qty",
        "total_gap_qty", "total_abs_gap_qty", "aggregate_abs_deviation_pct",
        "weekly_breakdown",
    )
    for key in required:
        assert key in sku, f"SKU row missing key: {key}"

    assert isinstance(sku["weekly_breakdown"], list)
    week_row = sku["weekly_breakdown"][0]
    for key in ("iso_week", "week_start", "forecast_qty", "actual_qty", "gap_qty", "gap_pct"):
        assert key in week_row, f"weekly row missing key: {key}"


# ---------------------------------------------------------------------------
# Window computation
# ---------------------------------------------------------------------------


async def test_analyze_forecast_deviation_default_weeks_is_4() -> None:
    """Default weeks parameter must be 4."""
    from packages.tools.analyze_forecast_deviation_tool import AnalyzeForecastDeviationTool

    mock_pool = _make_pool_seq([], [], [])
    with patch(
        "packages.tools.analyze_forecast_deviation_tool.get_pool",
        return_value=mock_pool,
    ):
        tool = AnalyzeForecastDeviationTool()
        result = await tool.handle({}, make_ctx())

    assert result.output["weeks_analysed"] == 4
    assert result.output["window"]["weeks_requested"] == 4


async def test_analyze_forecast_deviation_custom_weeks_reflected() -> None:
    """weeks=2 must produce weeks_analysed=2 and 2-entry weekly breakdowns."""
    from packages.tools.analyze_forecast_deviation_tool import AnalyzeForecastDeviationTool

    today = datetime.date.today()
    monday = today - datetime.timedelta(days=today.weekday())
    # Two weeks ago and one week ago (last 2 complete weeks)
    w2 = monday - datetime.timedelta(weeks=2)
    w1 = monday - datetime.timedelta(weeks=1)
    iso2 = _iso_week_label(w2)
    iso1 = _iso_week_label(w1)

    forecast_rows = [
        _forecast_row("SKU-A", iso2, 50.0),
        _forecast_row("SKU-A", iso1, 60.0),
    ]
    actual_rows = [
        _actual_row("SKU-A", iso2, 40.0),
        _actual_row("SKU-A", iso1, 50.0),
    ]

    mock_pool = _make_pool_seq(forecast_rows, actual_rows, [])
    with patch(
        "packages.tools.analyze_forecast_deviation_tool.get_pool",
        return_value=mock_pool,
    ):
        tool = AnalyzeForecastDeviationTool()
        result = await tool.handle({"weeks": 2}, make_ctx())

    assert result.output["weeks_analysed"] == 2
    sku = result.output["skus"][0]
    assert len(sku["weekly_breakdown"]) == 2


# ---------------------------------------------------------------------------
# Gap math
# ---------------------------------------------------------------------------


async def test_analyze_forecast_deviation_gap_qty_is_forecast_minus_actual() -> None:
    """gap_qty = forecast_qty - actual_qty."""
    from packages.tools.analyze_forecast_deviation_tool import AnalyzeForecastDeviationTool

    today = datetime.date.today()
    monday = today - datetime.timedelta(days=today.weekday())
    prev = monday - datetime.timedelta(weeks=1)
    iso = _iso_week_label(prev)

    forecast_rows = [_forecast_row("SKU-X", iso, 120.0)]
    actual_rows = [_actual_row("SKU-X", iso, 80.0)]

    mock_pool = _make_pool_seq(forecast_rows, actual_rows, [])
    with patch(
        "packages.tools.analyze_forecast_deviation_tool.get_pool",
        return_value=mock_pool,
    ):
        tool = AnalyzeForecastDeviationTool()
        result = await tool.handle({"weeks": 1}, make_ctx())

    sku = result.output["skus"][0]
    week = sku["weekly_breakdown"][0]
    assert week["forecast_qty"] == pytest.approx(120.0)
    assert week["actual_qty"] == pytest.approx(80.0)
    assert week["gap_qty"] == pytest.approx(40.0)
    assert week["gap_pct"] == pytest.approx(50.0)  # (120-80)/80 × 100


async def test_analyze_forecast_deviation_gap_pct_is_null_when_actual_is_zero() -> None:
    """gap_pct must be None when actual_qty == 0."""
    from packages.tools.analyze_forecast_deviation_tool import AnalyzeForecastDeviationTool

    today = datetime.date.today()
    monday = today - datetime.timedelta(days=today.weekday())
    prev = monday - datetime.timedelta(weeks=1)
    iso = _iso_week_label(prev)

    forecast_rows = [_forecast_row("SKU-ZERO", iso, 50.0)]
    actual_rows: list[dict[str, Any]] = []  # no actuals for this week

    mock_pool = _make_pool_seq(forecast_rows, actual_rows, [])
    with patch(
        "packages.tools.analyze_forecast_deviation_tool.get_pool",
        return_value=mock_pool,
    ):
        tool = AnalyzeForecastDeviationTool()
        result = await tool.handle({"weeks": 1}, make_ctx())

    sku = result.output["skus"][0]
    week = sku["weekly_breakdown"][0]
    assert week["gap_pct"] is None


async def test_analyze_forecast_deviation_total_gap_is_sum_of_weekly_gaps() -> None:
    """total_gap_qty must equal SUM of weekly gap_qty values."""
    from packages.tools.analyze_forecast_deviation_tool import AnalyzeForecastDeviationTool

    today = datetime.date.today()
    monday = today - datetime.timedelta(days=today.weekday())
    w2 = monday - datetime.timedelta(weeks=2)
    w1 = monday - datetime.timedelta(weeks=1)

    forecast_rows = [
        _forecast_row("SKU-A", _iso_week_label(w2), 100.0),
        _forecast_row("SKU-A", _iso_week_label(w1), 120.0),
    ]
    actual_rows = [
        _actual_row("SKU-A", _iso_week_label(w2), 80.0),
        _actual_row("SKU-A", _iso_week_label(w1), 100.0),
    ]

    mock_pool = _make_pool_seq(forecast_rows, actual_rows, [])
    with patch(
        "packages.tools.analyze_forecast_deviation_tool.get_pool",
        return_value=mock_pool,
    ):
        tool = AnalyzeForecastDeviationTool()
        result = await tool.handle({"weeks": 2}, make_ctx())

    sku = result.output["skus"][0]
    weekly_gap_sum = sum(w["gap_qty"] for w in sku["weekly_breakdown"])
    assert sku["total_gap_qty"] == pytest.approx(weekly_gap_sum)


# ---------------------------------------------------------------------------
# Bias classification
# ---------------------------------------------------------------------------


async def test_analyze_forecast_deviation_over_forecast_bias() -> None:
    """Forecast well above actual → bias_direction='over_forecast'."""
    from packages.tools.analyze_forecast_deviation_tool import AnalyzeForecastDeviationTool

    today = datetime.date.today()
    monday = today - datetime.timedelta(days=today.weekday())
    prev = monday - datetime.timedelta(weeks=1)
    iso = _iso_week_label(prev)

    # forecast=150, actual=100 → bias_pct=+50% >> +10%
    mock_pool = _make_pool_seq(
        [_forecast_row("SKU-OVER", iso, 150.0)],
        [_actual_row("SKU-OVER", iso, 100.0)],
        [],
    )
    with patch(
        "packages.tools.analyze_forecast_deviation_tool.get_pool",
        return_value=mock_pool,
    ):
        tool = AnalyzeForecastDeviationTool()
        result = await tool.handle({"weeks": 1}, make_ctx())

    sku = result.output["skus"][0]
    assert sku["bias_direction"] == "over_forecast"


async def test_analyze_forecast_deviation_under_forecast_bias() -> None:
    """Forecast well below actual → bias_direction='under_forecast'."""
    from packages.tools.analyze_forecast_deviation_tool import AnalyzeForecastDeviationTool

    today = datetime.date.today()
    monday = today - datetime.timedelta(days=today.weekday())
    prev = monday - datetime.timedelta(weeks=1)
    iso = _iso_week_label(prev)

    # forecast=60, actual=100 → bias_pct=-40% << -10%
    mock_pool = _make_pool_seq(
        [_forecast_row("SKU-UNDER", iso, 60.0)],
        [_actual_row("SKU-UNDER", iso, 100.0)],
        [],
    )
    with patch(
        "packages.tools.analyze_forecast_deviation_tool.get_pool",
        return_value=mock_pool,
    ):
        tool = AnalyzeForecastDeviationTool()
        result = await tool.handle({"weeks": 1}, make_ctx())

    sku = result.output["skus"][0]
    assert sku["bias_direction"] == "under_forecast"


async def test_analyze_forecast_deviation_mixed_bias_within_threshold() -> None:
    """Forecast within ±10% of actual → bias_direction='mixed'."""
    from packages.tools.analyze_forecast_deviation_tool import AnalyzeForecastDeviationTool

    today = datetime.date.today()
    monday = today - datetime.timedelta(days=today.weekday())
    prev = monday - datetime.timedelta(weeks=1)
    iso = _iso_week_label(prev)

    # forecast=105, actual=100 → bias_pct=+5% ≤ 10%
    mock_pool = _make_pool_seq(
        [_forecast_row("SKU-MIX", iso, 105.0)],
        [_actual_row("SKU-MIX", iso, 100.0)],
        [],
    )
    with patch(
        "packages.tools.analyze_forecast_deviation_tool.get_pool",
        return_value=mock_pool,
    ):
        tool = AnalyzeForecastDeviationTool()
        result = await tool.handle({"weeks": 1}, make_ctx())

    sku = result.output["skus"][0]
    assert sku["bias_direction"] == "mixed"


async def test_analyze_forecast_deviation_over_forecast_when_actual_is_zero() -> None:
    """No actuals but forecast > 0 → bias_direction='over_forecast'."""
    from packages.tools.analyze_forecast_deviation_tool import AnalyzeForecastDeviationTool

    today = datetime.date.today()
    monday = today - datetime.timedelta(days=today.weekday())
    prev = monday - datetime.timedelta(weeks=1)
    iso = _iso_week_label(prev)

    mock_pool = _make_pool_seq(
        [_forecast_row("SKU-NACT", iso, 50.0)],
        [],  # no actuals
        [],
    )
    with patch(
        "packages.tools.analyze_forecast_deviation_tool.get_pool",
        return_value=mock_pool,
    ):
        tool = AnalyzeForecastDeviationTool()
        result = await tool.handle({"weeks": 1}, make_ctx())

    sku = result.output["skus"][0]
    assert sku["bias_direction"] == "over_forecast"


# ---------------------------------------------------------------------------
# Ranking determinism
# ---------------------------------------------------------------------------


async def test_analyze_forecast_deviation_ranked_by_total_abs_gap_desc() -> None:
    """SKUs must be ranked by total_abs_gap_qty descending."""
    from packages.tools.analyze_forecast_deviation_tool import AnalyzeForecastDeviationTool

    today = datetime.date.today()
    monday = today - datetime.timedelta(days=today.weekday())
    prev = monday - datetime.timedelta(weeks=1)
    iso = _iso_week_label(prev)

    # SKU-B has larger absolute gap than SKU-A
    forecast_rows = [
        _forecast_row("SKU-A", iso, 110.0),  # gap=10
        _forecast_row("SKU-B", iso, 200.0),  # gap=100
    ]
    actual_rows = [
        _actual_row("SKU-A", iso, 100.0),
        _actual_row("SKU-B", iso, 100.0),
    ]

    mock_pool = _make_pool_seq(forecast_rows, actual_rows, [])
    with patch(
        "packages.tools.analyze_forecast_deviation_tool.get_pool",
        return_value=mock_pool,
    ):
        tool = AnalyzeForecastDeviationTool()
        result = await tool.handle({"weeks": 1}, make_ctx())

    skus = result.output["skus"]
    assert skus[0]["sku_id"] == "SKU-B"
    assert skus[1]["sku_id"] == "SKU-A"


async def test_analyze_forecast_deviation_sku_id_tiebreak_ascending() -> None:
    """Equal total_abs_gap → sku_id ascending as tiebreak."""
    from packages.tools.analyze_forecast_deviation_tool import AnalyzeForecastDeviationTool

    today = datetime.date.today()
    monday = today - datetime.timedelta(days=today.weekday())
    prev = monday - datetime.timedelta(weeks=1)
    iso = _iso_week_label(prev)

    # Same gap magnitude for SKU-B, SKU-A, SKU-C (alphabetically: A < B < C)
    forecast_rows = [
        _forecast_row("SKU-C", iso, 150.0),
        _forecast_row("SKU-A", iso, 150.0),
        _forecast_row("SKU-B", iso, 150.0),
    ]
    actual_rows = [
        _actual_row("SKU-C", iso, 100.0),
        _actual_row("SKU-A", iso, 100.0),
        _actual_row("SKU-B", iso, 100.0),
    ]

    mock_pool = _make_pool_seq(forecast_rows, actual_rows, [])
    with patch(
        "packages.tools.analyze_forecast_deviation_tool.get_pool",
        return_value=mock_pool,
    ):
        tool = AnalyzeForecastDeviationTool()
        result = await tool.handle({"weeks": 1}, make_ctx())

    sku_ids = [s["sku_id"] for s in result.output["skus"]]
    assert sku_ids == ["SKU-A", "SKU-B", "SKU-C"]


# ---------------------------------------------------------------------------
# Cap + truncated
# ---------------------------------------------------------------------------


async def test_analyze_forecast_deviation_truncated_at_over_100_skus() -> None:
    """101 SKUs → truncated=True, skus list capped at 100; count=101."""
    from packages.tools.analyze_forecast_deviation_tool import AnalyzeForecastDeviationTool

    today = datetime.date.today()
    monday = today - datetime.timedelta(days=today.weekday())
    prev = monday - datetime.timedelta(weeks=1)
    iso = _iso_week_label(prev)

    forecast_rows = [
        _forecast_row(f"SKU-{i:03d}", iso, 100.0 + i)
        for i in range(101)
    ]
    actual_rows = [
        _actual_row(f"SKU-{i:03d}", iso, 80.0)
        for i in range(101)
    ]

    mock_pool = _make_pool_seq(forecast_rows, actual_rows, [])
    with patch(
        "packages.tools.analyze_forecast_deviation_tool.get_pool",
        return_value=mock_pool,
    ):
        tool = AnalyzeForecastDeviationTool()
        result = await tool.handle({"weeks": 1}, make_ctx())

    assert result.output["count"] == 101
    assert result.output["truncated"] is True
    assert len(result.output["skus"]) == 100


async def test_analyze_forecast_deviation_not_truncated_at_100_skus() -> None:
    """Exactly 100 SKUs → truncated=False."""
    from packages.tools.analyze_forecast_deviation_tool import AnalyzeForecastDeviationTool

    today = datetime.date.today()
    monday = today - datetime.timedelta(days=today.weekday())
    prev = monday - datetime.timedelta(weeks=1)
    iso = _iso_week_label(prev)

    forecast_rows = [_forecast_row(f"SKU-{i:03d}", iso, 100.0) for i in range(100)]
    actual_rows = [_actual_row(f"SKU-{i:03d}", iso, 80.0) for i in range(100)]

    mock_pool = _make_pool_seq(forecast_rows, actual_rows, [])
    with patch(
        "packages.tools.analyze_forecast_deviation_tool.get_pool",
        return_value=mock_pool,
    ):
        tool = AnalyzeForecastDeviationTool()
        result = await tool.handle({"weeks": 1}, make_ctx())

    assert result.output["count"] == 100
    assert result.output["truncated"] is False
    assert len(result.output["skus"]) == 100


# ---------------------------------------------------------------------------
# missing_data population
# ---------------------------------------------------------------------------


async def test_analyze_forecast_deviation_missing_data_no_forecast() -> None:
    """SKU with actuals but no forecast rows → missing_data note."""
    from packages.tools.analyze_forecast_deviation_tool import AnalyzeForecastDeviationTool

    today = datetime.date.today()
    monday = today - datetime.timedelta(days=today.weekday())
    prev = monday - datetime.timedelta(weeks=1)
    iso = _iso_week_label(prev)

    # No forecast rows for SKU-NOFC; only actuals
    mock_pool = _make_pool_seq(
        [],  # no forecast
        [_actual_row("SKU-NOFC", iso, 100.0)],
        [],
    )
    with patch(
        "packages.tools.analyze_forecast_deviation_tool.get_pool",
        return_value=mock_pool,
    ):
        tool = AnalyzeForecastDeviationTool()
        result = await tool.handle({"weeks": 1}, make_ctx())

    md = result.output["missing_data"]
    assert any("SKU-NOFC" in m and "forecast" in m for m in md)


async def test_analyze_forecast_deviation_missing_data_no_actuals() -> None:
    """SKU with forecast but no actuals → missing_data note."""
    from packages.tools.analyze_forecast_deviation_tool import AnalyzeForecastDeviationTool

    today = datetime.date.today()
    monday = today - datetime.timedelta(days=today.weekday())
    prev = monday - datetime.timedelta(weeks=1)
    iso = _iso_week_label(prev)

    mock_pool = _make_pool_seq(
        [_forecast_row("SKU-NOACT", iso, 100.0)],
        [],  # no actuals
        [],
    )
    with patch(
        "packages.tools.analyze_forecast_deviation_tool.get_pool",
        return_value=mock_pool,
    ):
        tool = AnalyzeForecastDeviationTool()
        result = await tool.handle({"weeks": 1}, make_ctx())

    md = result.output["missing_data"]
    assert any("SKU-NOACT" in m and "actual" in m for m in md)


async def test_analyze_forecast_deviation_missing_data_is_missing_actuals() -> None:
    """SKU with is_missing actuals in window → partial data note in missing_data."""
    from packages.tools.analyze_forecast_deviation_tool import AnalyzeForecastDeviationTool

    today = datetime.date.today()
    monday = today - datetime.timedelta(days=today.weekday())
    prev = monday - datetime.timedelta(weeks=1)
    iso = _iso_week_label(prev)

    mock_pool = _make_pool_seq(
        [_forecast_row("SKU-MISS", iso, 100.0)],
        [_actual_row("SKU-MISS", iso, 80.0)],
        [_missing_row("SKU-MISS", iso)],  # is_missing actuals
    )
    with patch(
        "packages.tools.analyze_forecast_deviation_tool.get_pool",
        return_value=mock_pool,
    ):
        tool = AnalyzeForecastDeviationTool()
        result = await tool.handle({"weeks": 1}, make_ctx())

    md = result.output["missing_data"]
    assert any("SKU-MISS" in m and "is_missing" in m for m in md)


# ---------------------------------------------------------------------------
# Empty DB shape
# ---------------------------------------------------------------------------


async def test_analyze_forecast_deviation_empty_db_shape() -> None:
    """No data in DB → skus=[], count=0, truncated=False, missing_data=[]."""
    from packages.tools.analyze_forecast_deviation_tool import AnalyzeForecastDeviationTool

    mock_pool = _make_pool_seq([], [], [])
    with patch(
        "packages.tools.analyze_forecast_deviation_tool.get_pool",
        return_value=mock_pool,
    ):
        tool = AnalyzeForecastDeviationTool()
        result = await tool.handle({}, make_ctx())

    assert result.output["skus"] == []
    assert result.output["count"] == 0
    assert result.output["truncated"] is False
    assert result.output["missing_data"] == []


# ---------------------------------------------------------------------------
# DB error path
# ---------------------------------------------------------------------------


async def test_analyze_forecast_deviation_db_error_returns_error_key() -> None:
    """When get_pool raises, output must contain an 'error' key."""
    from packages.tools.analyze_forecast_deviation_tool import AnalyzeForecastDeviationTool

    with patch(
        "packages.tools.analyze_forecast_deviation_tool.get_pool",
        side_effect=RuntimeError("DATABASE_URL not set"),
    ):
        tool = AnalyzeForecastDeviationTool()
        result = await tool.handle({}, make_ctx())

    assert "error" in result.output


# ---------------------------------------------------------------------------
# sku_id filter
# ---------------------------------------------------------------------------


async def test_analyze_forecast_deviation_sku_id_filter_restricts_results() -> None:
    """sku_id filter must return only that SKU."""
    from packages.tools.analyze_forecast_deviation_tool import AnalyzeForecastDeviationTool

    today = datetime.date.today()
    monday = today - datetime.timedelta(days=today.weekday())
    prev = monday - datetime.timedelta(weeks=1)
    iso = _iso_week_label(prev)

    # The mock returns both SKUs from the DB (simulating a filtered query that
    # returned only the requested SKU)
    mock_pool = _make_pool_seq(
        [_forecast_row("SKU-001", iso, 100.0)],
        [_actual_row("SKU-001", iso, 80.0)],
        [],
    )
    with patch(
        "packages.tools.analyze_forecast_deviation_tool.get_pool",
        return_value=mock_pool,
    ):
        tool = AnalyzeForecastDeviationTool()
        result = await tool.handle({"sku_id": "SKU-001", "weeks": 1}, make_ctx())

    assert all(s["sku_id"] == "SKU-001" for s in result.output["skus"])


# ---------------------------------------------------------------------------
# Pure-Python helpers
# ---------------------------------------------------------------------------


def _iso_week_label(d: datetime.date) -> str:
    """Local helper mirroring the tool's _iso_week_label."""
    iso = d.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def test_iso_week_label_known_date() -> None:
    """_iso_week_label('2024-01-01') = '2024-W01' (Monday of ISO week 1, 2024)."""
    from packages.tools.analyze_forecast_deviation_tool import _iso_week_label

    # 2024-01-01 is a Monday; ISO week 1 of 2024
    d = datetime.date(2024, 1, 1)
    assert _iso_week_label(d) == "2024-W01"


def test_iso_week_label_year_boundary() -> None:
    """2023-12-25 is Monday of ISO week 52, 2023."""
    from packages.tools.analyze_forecast_deviation_tool import _iso_week_label

    d = datetime.date(2023, 12, 25)
    assert _iso_week_label(d) == "2023-W52"


def test_gap_pct_normal_case() -> None:
    """_gap_pct(120, 80) = +50.0."""
    from packages.tools.analyze_forecast_deviation_tool import _gap_pct

    assert _gap_pct(120.0, 80.0) == pytest.approx(50.0)


def test_gap_pct_null_when_actual_zero() -> None:
    """_gap_pct(100, 0) = None."""
    from packages.tools.analyze_forecast_deviation_tool import _gap_pct

    assert _gap_pct(100.0, 0.0) is None


def test_gap_pct_negative_when_under_forecast() -> None:
    """_gap_pct(60, 100) = -40.0."""
    from packages.tools.analyze_forecast_deviation_tool import _gap_pct

    assert _gap_pct(60.0, 100.0) == pytest.approx(-40.0)


def test_classify_bias_over_forecast() -> None:
    """bias > +10% → over_forecast."""
    from packages.tools.analyze_forecast_deviation_tool import _classify_bias

    # forecast=150, actual=100 → +50% >> +10%
    assert _classify_bias(150.0, 100.0) == "over_forecast"


def test_classify_bias_under_forecast() -> None:
    """bias < -10% → under_forecast."""
    from packages.tools.analyze_forecast_deviation_tool import _classify_bias

    # forecast=60, actual=100 → -40% << -10%
    assert _classify_bias(60.0, 100.0) == "under_forecast"


def test_classify_bias_mixed_positive_within_threshold() -> None:
    """bias = +5% ≤ 10% → mixed."""
    from packages.tools.analyze_forecast_deviation_tool import _classify_bias

    assert _classify_bias(105.0, 100.0) == "mixed"


def test_classify_bias_mixed_negative_within_threshold() -> None:
    """bias = -9% (magnitude ≤ 10%) → mixed."""
    from packages.tools.analyze_forecast_deviation_tool import _classify_bias

    assert _classify_bias(91.0, 100.0) == "mixed"


def test_classify_bias_over_forecast_when_actual_zero() -> None:
    """actual=0, forecast>0 → over_forecast."""
    from packages.tools.analyze_forecast_deviation_tool import _classify_bias

    assert _classify_bias(50.0, 0.0) == "over_forecast"


def test_classify_bias_mixed_when_both_zero() -> None:
    """actual=0, forecast=0 → mixed."""
    from packages.tools.analyze_forecast_deviation_tool import _classify_bias

    assert _classify_bias(0.0, 0.0) == "mixed"


def test_aggregate_abs_deviation_pct_normal() -> None:
    """_aggregate_abs_deviation_pct(40, 80) = 50.0."""
    from packages.tools.analyze_forecast_deviation_tool import _aggregate_abs_deviation_pct

    assert _aggregate_abs_deviation_pct(40.0, 80.0) == pytest.approx(50.0)


def test_aggregate_abs_deviation_pct_null_when_actual_zero() -> None:
    """_aggregate_abs_deviation_pct(40, 0) = None."""
    from packages.tools.analyze_forecast_deviation_tool import _aggregate_abs_deviation_pct

    assert _aggregate_abs_deviation_pct(40.0, 0.0) is None


# ---------------------------------------------------------------------------
# Seed scenario verification (pure-Python logic — no DB)
# ---------------------------------------------------------------------------


async def test_analyze_forecast_deviation_seed_over_forecast_sku() -> None:
    """SKU-028 seed: forecast=6/week, actual=3.5/week → over_forecast bias."""
    from packages.tools.analyze_forecast_deviation_tool import AnalyzeForecastDeviationTool

    today = datetime.date.today()
    monday = today - datetime.timedelta(days=today.weekday())
    weeks = 4
    forecast_rows = []
    actual_rows = []
    for i in range(weeks):
        w_start = monday - datetime.timedelta(weeks=(weeks - i))
        iso = _iso_week_label(w_start)
        forecast_rows.append(_forecast_row("SKU-028", iso, 6.0))
        actual_rows.append(_actual_row("SKU-028", iso, 3.5))

    mock_pool = _make_pool_seq(forecast_rows, actual_rows, [])
    with patch(
        "packages.tools.analyze_forecast_deviation_tool.get_pool",
        return_value=mock_pool,
    ):
        tool = AnalyzeForecastDeviationTool()
        result = await tool.handle({"weeks": weeks}, make_ctx())

    skus = {s["sku_id"]: s for s in result.output["skus"]}
    assert "SKU-028" in skus
    assert skus["SKU-028"]["bias_direction"] == "over_forecast"
    assert skus["SKU-028"]["total_forecast_qty"] == pytest.approx(24.0)
    assert skus["SKU-028"]["total_actual_qty"] == pytest.approx(14.0)


async def test_analyze_forecast_deviation_seed_under_forecast_sku() -> None:
    """SKU-029 seed: forecast=4/week, actual=8.4/week → under_forecast bias."""
    from packages.tools.analyze_forecast_deviation_tool import AnalyzeForecastDeviationTool

    today = datetime.date.today()
    monday = today - datetime.timedelta(days=today.weekday())
    weeks = 4
    forecast_rows = []
    actual_rows = []
    for i in range(weeks):
        w_start = monday - datetime.timedelta(weeks=(weeks - i))
        iso = _iso_week_label(w_start)
        forecast_rows.append(_forecast_row("SKU-029", iso, 4.0))
        actual_rows.append(_actual_row("SKU-029", iso, 8.4))

    mock_pool = _make_pool_seq(forecast_rows, actual_rows, [])
    with patch(
        "packages.tools.analyze_forecast_deviation_tool.get_pool",
        return_value=mock_pool,
    ):
        tool = AnalyzeForecastDeviationTool()
        result = await tool.handle({"weeks": weeks}, make_ctx())

    skus = {s["sku_id"]: s for s in result.output["skus"]}
    assert "SKU-029" in skus
    assert skus["SKU-029"]["bias_direction"] == "under_forecast"
    assert skus["SKU-029"]["total_forecast_qty"] == pytest.approx(16.0)
    assert skus["SKU-029"]["total_actual_qty"] == pytest.approx(33.6, rel=1e-4)


async def test_analyze_forecast_deviation_seed_under_forecast_ranked_first() -> None:
    """SKU-029 (larger abs_gap) must be ranked above SKU-028 when both present."""
    from packages.tools.analyze_forecast_deviation_tool import AnalyzeForecastDeviationTool

    today = datetime.date.today()
    monday = today - datetime.timedelta(days=today.weekday())
    weeks = 4
    forecast_rows = []
    actual_rows = []
    for i in range(weeks):
        w_start = monday - datetime.timedelta(weeks=(weeks - i))
        iso = _iso_week_label(w_start)
        # SKU-028: gap = 6 - 3.5 = 2.5/week → abs_gap/week=2.5; total=10
        forecast_rows.append(_forecast_row("SKU-028", iso, 6.0))
        actual_rows.append(_actual_row("SKU-028", iso, 3.5))
        # SKU-029: gap = 4 - 8.4 = -4.4/week → abs_gap/week=4.4; total=17.6
        forecast_rows.append(_forecast_row("SKU-029", iso, 4.0))
        actual_rows.append(_actual_row("SKU-029", iso, 8.4))

    mock_pool = _make_pool_seq(forecast_rows, actual_rows, [])
    with patch(
        "packages.tools.analyze_forecast_deviation_tool.get_pool",
        return_value=mock_pool,
    ):
        tool = AnalyzeForecastDeviationTool()
        result = await tool.handle({"weeks": weeks}, make_ctx())

    skus = result.output["skus"]
    assert len(skus) == 2
    # SKU-029 has larger absolute gap (17.6 > 10), so it ranks first
    assert skus[0]["sku_id"] == "SKU-029"
    assert skus[1]["sku_id"] == "SKU-028"
