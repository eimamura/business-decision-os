"""T-581: Integration tests for analyze_forecast_deviation_tool against a real PostgreSQL DB.

Requires a running PostgreSQL instance reachable via DATABASE_URL with the latest
migrations applied and the P94 seed data loaded (scripts/seed_db.py /
scripts/generate_sample_data.py).

Deterministic seed scenarios (scripts/generate_sample_data.py constants):
    FORECAST_OVER_SKU  = "SKU-028"   forecast=6.0/week, actual≈3.5/week  → over_forecast
    FORECAST_UNDER_SKU = "SKU-029"   forecast=4.0/week, actual≈8.4/week  → under_forecast

The seed inserts exactly 4 complete ISO weeks (anchored to date.today()) so that the
default 4-week analysis window always contains P94 scenario rows on a fresh seed.

Run with:
    docker compose up -d db && \\
    DATABASE_URL=postgresql+asyncpg://bdos:bdos_dev@localhost:5432/bdos \\
        uv run pytest tests/integration/test_p94_b02_analyze_forecast_deviation_integration.py -v
"""
from __future__ import annotations

import os
from uuid import uuid4

import pytest

from packages.tools.base import ToolContext

_HAS_DB = bool(os.environ.get("DATABASE_URL"))
_SKIP_NO_DB = pytest.mark.skipif(not _HAS_DB, reason="DATABASE_URL not set")


def _ctx() -> ToolContext:
    return ToolContext(
        session_id=uuid4(),
        agent_step_id=uuid4(),
        specialist_role="control",
        actor="integration_test",
        correlation_id=uuid4(),
    )


@pytest.fixture(autouse=True)
async def reset_db_pool() -> None:  # type: ignore[misc]
    """Reset the global asyncpg pool before and after each test.

    pytest-asyncio creates a new event loop per test function.  The global pool
    singleton in packages/persistence/db.py is bound to the event loop in which
    it was created, so reusing it across tests causes 'loop is closed' errors.
    Resetting the module-level variable forces pool recreation in the current loop.
    """
    import packages.persistence.db as db_module

    db_module._pool = None
    yield  # type: ignore[misc]
    if db_module._pool is not None:
        await db_module._pool.close()
        db_module._pool = None


# ===========================================================================
# Smoke tests — basic schema + no error
# ===========================================================================


@_SKIP_NO_DB
async def test_analyze_forecast_deviation_returns_no_error() -> None:
    """Tool executes against the real DB without returning an error key."""
    from packages.tools.analyze_forecast_deviation_tool import AnalyzeForecastDeviationTool

    tool = AnalyzeForecastDeviationTool()
    result = await tool.handle({}, _ctx())

    assert "error" not in result.output, (
        f"Unexpected error from analyze_forecast_deviation: {result.output.get('error')}"
    )


@_SKIP_NO_DB
async def test_analyze_forecast_deviation_output_has_required_contract_keys() -> None:
    """Output must include all required top-level contract keys with correct types."""
    from packages.tools.analyze_forecast_deviation_tool import AnalyzeForecastDeviationTool

    tool = AnalyzeForecastDeviationTool()
    result = await tool.handle({}, _ctx())

    out = result.output
    for key in ("weeks_analysed", "window", "skus", "count", "truncated", "missing_data"):
        assert key in out, f"Contract key missing: {key}"

    assert isinstance(out["skus"], list)
    assert isinstance(out["truncated"], bool)
    assert isinstance(out["missing_data"], list)
    assert isinstance(out["count"], int)

    w = out["window"]
    for wkey in ("start_iso_week", "end_iso_week", "weeks_requested"):
        assert wkey in w, f"window missing key: {wkey}"


@_SKIP_NO_DB
async def test_analyze_forecast_deviation_count_reflects_full_sku_set() -> None:
    """count must equal len(skus) when not truncated (seeded DB has < 100 deviation SKUs)."""
    from packages.tools.analyze_forecast_deviation_tool import AnalyzeForecastDeviationTool

    tool = AnalyzeForecastDeviationTool()
    result = await tool.handle({}, _ctx())

    out = result.output
    if not out["truncated"]:
        assert out["count"] == len(out["skus"]), (
            f"count={out['count']} != len(skus)={len(out['skus'])} when truncated=False"
        )


# ===========================================================================
# T-581(a): SKU-028 classified as over_forecast
# ===========================================================================


@_SKIP_NO_DB
async def test_analyze_forecast_deviation_sku028_appears_in_output() -> None:
    """SKU-028 (over-forecast seed) must appear in the tool output."""
    from packages.tools.analyze_forecast_deviation_tool import AnalyzeForecastDeviationTool

    tool = AnalyzeForecastDeviationTool()
    result = await tool.handle({"weeks": 4}, _ctx())

    sku_ids = {s["sku_id"] for s in result.output["skus"]}
    assert "SKU-028" in sku_ids, (
        f"SKU-028 not found in tool output. Present SKUs: {sorted(sku_ids)}"
    )


@_SKIP_NO_DB
async def test_analyze_forecast_deviation_sku028_classified_over_forecast() -> None:
    """SKU-028 must be classified as over_forecast (forecast=6/wk >> actual≈3.5/wk)."""
    from packages.tools.analyze_forecast_deviation_tool import AnalyzeForecastDeviationTool

    tool = AnalyzeForecastDeviationTool()
    result = await tool.handle({"weeks": 4}, _ctx())

    skus = {s["sku_id"]: s for s in result.output["skus"]}
    assert "SKU-028" in skus, "SKU-028 not found in tool output"
    bias = skus["SKU-028"]["bias_direction"]
    assert bias == "over_forecast", (
        f"Expected SKU-028 bias_direction='over_forecast', got {bias!r}"
    )


@_SKIP_NO_DB
async def test_analyze_forecast_deviation_sku028_has_positive_gap() -> None:
    """SKU-028 total_gap_qty must be positive (forecast > actual)."""
    from packages.tools.analyze_forecast_deviation_tool import AnalyzeForecastDeviationTool

    tool = AnalyzeForecastDeviationTool()
    result = await tool.handle({"weeks": 4}, _ctx())

    skus = {s["sku_id"]: s for s in result.output["skus"]}
    assert "SKU-028" in skus, "SKU-028 not found in tool output"
    total_gap = skus["SKU-028"]["total_gap_qty"]
    assert total_gap > 0, (
        f"Expected SKU-028 total_gap_qty > 0 (over-forecast), got {total_gap}"
    )


@_SKIP_NO_DB
async def test_analyze_forecast_deviation_sku028_forecast_exceeds_actual() -> None:
    """SKU-028: total_forecast_qty must exceed total_actual_qty."""
    from packages.tools.analyze_forecast_deviation_tool import AnalyzeForecastDeviationTool

    tool = AnalyzeForecastDeviationTool()
    result = await tool.handle({"weeks": 4}, _ctx())

    skus = {s["sku_id"]: s for s in result.output["skus"]}
    assert "SKU-028" in skus, "SKU-028 not found in tool output"
    sku = skus["SKU-028"]
    assert sku["total_forecast_qty"] > sku["total_actual_qty"], (
        f"SKU-028 forecast={sku['total_forecast_qty']} should > actual={sku['total_actual_qty']}"
    )


# ===========================================================================
# T-581(a): SKU-029 classified as under_forecast
# ===========================================================================


@_SKIP_NO_DB
async def test_analyze_forecast_deviation_sku029_appears_in_output() -> None:
    """SKU-029 (under-forecast seed) must appear in the tool output."""
    from packages.tools.analyze_forecast_deviation_tool import AnalyzeForecastDeviationTool

    tool = AnalyzeForecastDeviationTool()
    result = await tool.handle({"weeks": 4}, _ctx())

    sku_ids = {s["sku_id"] for s in result.output["skus"]}
    assert "SKU-029" in sku_ids, (
        f"SKU-029 not found in tool output. Present SKUs: {sorted(sku_ids)}"
    )


@_SKIP_NO_DB
async def test_analyze_forecast_deviation_sku029_classified_under_forecast() -> None:
    """SKU-029 must be classified as under_forecast (forecast=4/wk << actual≈8.4/wk)."""
    from packages.tools.analyze_forecast_deviation_tool import AnalyzeForecastDeviationTool

    tool = AnalyzeForecastDeviationTool()
    result = await tool.handle({"weeks": 4}, _ctx())

    skus = {s["sku_id"]: s for s in result.output["skus"]}
    assert "SKU-029" in skus, "SKU-029 not found in tool output"
    bias = skus["SKU-029"]["bias_direction"]
    assert bias == "under_forecast", (
        f"Expected SKU-029 bias_direction='under_forecast', got {bias!r}"
    )


@_SKIP_NO_DB
async def test_analyze_forecast_deviation_sku029_has_negative_gap() -> None:
    """SKU-029 total_gap_qty must be negative (forecast < actual)."""
    from packages.tools.analyze_forecast_deviation_tool import AnalyzeForecastDeviationTool

    tool = AnalyzeForecastDeviationTool()
    result = await tool.handle({"weeks": 4}, _ctx())

    skus = {s["sku_id"]: s for s in result.output["skus"]}
    assert "SKU-029" in skus, "SKU-029 not found in tool output"
    total_gap = skus["SKU-029"]["total_gap_qty"]
    assert total_gap < 0, (
        f"Expected SKU-029 total_gap_qty < 0 (under-forecast), got {total_gap}"
    )


@_SKIP_NO_DB
async def test_analyze_forecast_deviation_sku029_actual_exceeds_forecast() -> None:
    """SKU-029: total_actual_qty must exceed total_forecast_qty."""
    from packages.tools.analyze_forecast_deviation_tool import AnalyzeForecastDeviationTool

    tool = AnalyzeForecastDeviationTool()
    result = await tool.handle({"weeks": 4}, _ctx())

    skus = {s["sku_id"]: s for s in result.output["skus"]}
    assert "SKU-029" in skus, "SKU-029 not found in tool output"
    sku = skus["SKU-029"]
    assert sku["total_actual_qty"] > sku["total_forecast_qty"], (
        f"SKU-029 actual={sku['total_actual_qty']} should > forecast={sku['total_forecast_qty']}"
    )


# ===========================================================================
# T-581(b): Output contract keys (missing_data, truncated, count)
# ===========================================================================


@_SKIP_NO_DB
async def test_analyze_forecast_deviation_truncated_is_false_for_seeded_db() -> None:
    """Seeded DB has far fewer than 100 SKUs with deviations — truncated must be False."""
    from packages.tools.analyze_forecast_deviation_tool import AnalyzeForecastDeviationTool

    tool = AnalyzeForecastDeviationTool()
    result = await tool.handle({"weeks": 4}, _ctx())

    assert result.output["truncated"] is False, (
        f"Expected truncated=False for seeded dev DB, got {result.output['truncated']}"
    )


@_SKIP_NO_DB
async def test_analyze_forecast_deviation_missing_data_is_list() -> None:
    """missing_data must always be a list (even if empty)."""
    from packages.tools.analyze_forecast_deviation_tool import AnalyzeForecastDeviationTool

    tool = AnalyzeForecastDeviationTool()
    result = await tool.handle({"weeks": 4}, _ctx())

    assert isinstance(result.output["missing_data"], list), (
        f"missing_data must be a list, got {type(result.output['missing_data'])}"
    )


@_SKIP_NO_DB
async def test_analyze_forecast_deviation_weeks_analysed_equals_requested() -> None:
    """weeks_analysed must equal the requested weeks parameter."""
    from packages.tools.analyze_forecast_deviation_tool import AnalyzeForecastDeviationTool

    tool = AnalyzeForecastDeviationTool()
    result = await tool.handle({"weeks": 4}, _ctx())

    assert result.output["weeks_analysed"] == 4, (
        f"Expected weeks_analysed=4, got {result.output['weeks_analysed']}"
    )
    assert result.output["window"]["weeks_requested"] == 4, (
        f"Expected window.weeks_requested=4, got {result.output['window']['weeks_requested']}"
    )


# ===========================================================================
# T-581(c): Weekly breakdown spans the 4-week window
# ===========================================================================


@_SKIP_NO_DB
async def test_analyze_forecast_deviation_sku028_weekly_breakdown_has_4_rows() -> None:
    """SKU-028 weekly_breakdown must contain exactly 4 rows for the 4-week window."""
    from packages.tools.analyze_forecast_deviation_tool import AnalyzeForecastDeviationTool

    tool = AnalyzeForecastDeviationTool()
    result = await tool.handle({"weeks": 4}, _ctx())

    skus = {s["sku_id"]: s for s in result.output["skus"]}
    assert "SKU-028" in skus, "SKU-028 not found in tool output"
    breakdown = skus["SKU-028"]["weekly_breakdown"]
    assert len(breakdown) == 4, (
        f"Expected 4 weekly rows for SKU-028, got {len(breakdown)}"
    )


@_SKIP_NO_DB
async def test_analyze_forecast_deviation_sku029_weekly_breakdown_has_4_rows() -> None:
    """SKU-029 weekly_breakdown must contain exactly 4 rows for the 4-week window."""
    from packages.tools.analyze_forecast_deviation_tool import AnalyzeForecastDeviationTool

    tool = AnalyzeForecastDeviationTool()
    result = await tool.handle({"weeks": 4}, _ctx())

    skus = {s["sku_id"]: s for s in result.output["skus"]}
    assert "SKU-029" in skus, "SKU-029 not found in tool output"
    breakdown = skus["SKU-029"]["weekly_breakdown"]
    assert len(breakdown) == 4, (
        f"Expected 4 weekly rows for SKU-029, got {len(breakdown)}"
    )


@_SKIP_NO_DB
async def test_analyze_forecast_deviation_weekly_rows_have_required_fields() -> None:
    """Every weekly_breakdown row for SKU-028 must include all required fields."""
    from packages.tools.analyze_forecast_deviation_tool import AnalyzeForecastDeviationTool

    tool = AnalyzeForecastDeviationTool()
    result = await tool.handle({"sku_id": "SKU-028", "weeks": 4}, _ctx())

    skus = {s["sku_id"]: s for s in result.output["skus"]}
    assert "SKU-028" in skus, "SKU-028 not found in tool output"
    required_keys = {"iso_week", "week_start", "forecast_qty", "actual_qty", "gap_qty", "gap_pct"}
    for row in skus["SKU-028"]["weekly_breakdown"]:
        missing = required_keys - row.keys()
        assert not missing, f"weekly_breakdown row missing keys {missing}: {row}"


@_SKIP_NO_DB
async def test_analyze_forecast_deviation_weekly_breakdown_iso_weeks_are_distinct() -> None:
    """Each week in the 4-week breakdown must have a distinct iso_week label."""
    from packages.tools.analyze_forecast_deviation_tool import AnalyzeForecastDeviationTool

    tool = AnalyzeForecastDeviationTool()
    result = await tool.handle({"sku_id": "SKU-028", "weeks": 4}, _ctx())

    skus = {s["sku_id"]: s for s in result.output["skus"]}
    assert "SKU-028" in skus, "SKU-028 not found in tool output"
    iso_weeks = [row["iso_week"] for row in skus["SKU-028"]["weekly_breakdown"]]
    assert len(iso_weeks) == len(set(iso_weeks)), (
        f"Duplicate iso_week labels in SKU-028 breakdown: {iso_weeks}"
    )


@_SKIP_NO_DB
async def test_analyze_forecast_deviation_weekly_breakdown_gap_qty_signs_consistent() -> None:
    """SKU-028 (over-forecast): every weekly gap_qty must be >= 0 where actuals exist."""
    from packages.tools.analyze_forecast_deviation_tool import AnalyzeForecastDeviationTool

    tool = AnalyzeForecastDeviationTool()
    result = await tool.handle({"sku_id": "SKU-028", "weeks": 4}, _ctx())

    skus = {s["sku_id"]: s for s in result.output["skus"]}
    assert "SKU-028" in skus, "SKU-028 not found"
    # For SKU-028 the seed sets forecast=6 >> actual≈3.5 every week → all gaps positive
    for row in skus["SKU-028"]["weekly_breakdown"]:
        if row["actual_qty"] > 0:
            assert row["gap_qty"] > 0, (
                f"SKU-028 week {row['iso_week']}: expected positive gap_qty, got {row['gap_qty']}"
            )


# ===========================================================================
# SKU filter: single-SKU path with real DB
# ===========================================================================


@_SKIP_NO_DB
async def test_analyze_forecast_deviation_sku_filter_returns_only_requested_sku() -> None:
    """sku_id filter must restrict output to exactly that SKU."""
    from packages.tools.analyze_forecast_deviation_tool import AnalyzeForecastDeviationTool

    tool = AnalyzeForecastDeviationTool()
    result = await tool.handle({"sku_id": "SKU-029", "weeks": 4}, _ctx())

    assert "error" not in result.output, result.output.get("error")
    sku_ids = {s["sku_id"] for s in result.output["skus"]}
    assert sku_ids <= {"SKU-029"}, (
        f"sku_id filter returned unexpected SKUs: {sku_ids}"
    )
    assert "SKU-029" in sku_ids or result.output["count"] == 0, (
        "SKU-029 filter returned empty result — seed may be missing"
    )
