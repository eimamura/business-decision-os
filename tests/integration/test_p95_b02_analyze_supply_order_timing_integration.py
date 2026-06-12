"""T-587: Integration tests for analyze_supply_order_timing_tool against a real PostgreSQL DB.

Requires a running PostgreSQL instance reachable via DATABASE_URL with the latest
migrations applied and the P95 seed data loaded (scripts/seed_db.py /
scripts/generate_sample_data.py).

Deterministic seed scenarios:
    Pull-forward:  P84 risk-band SKUs (SKU-001, SKU-003, SKU-006, SKU-007) have
                   open supply orders pushed to today+10 in generate_supply().
                   Each has DOC < 10 days at seed time, so expected_arrival > projected
                   stockout date → pull_forward_candidate with positive days_misaligned.
                   SKU-001 is the critical-band representative (DOC ≈ 2 days → stockout
                   tomorrow; supply arrives at today+10).
    Push-out:      SKU-027 has a P95 seed order arriving today+5 (order_date = today-2,
                   supplier = SUP-003, status = pending).  On-hand ≈ 115 units,
                   avg_daily ≈ 0.57 → DOC ≈ 200 days.
                   days_of_cover_at_arrival ≈ 200 - 5 ≈ 195 >> 30 → push_out_candidate.

Run with:
    docker compose up -d db && \\
    DATABASE_URL=postgresql+asyncpg://bdos:bdos_dev@localhost:5432/bdos \\
        uv run pytest tests/integration/test_p95_b02_analyze_supply_order_timing_integration.py -v
"""
from __future__ import annotations

import os
from uuid import uuid4

import pytest

from packages.tools.base import ToolContext

_HAS_DB = bool(os.environ.get("DATABASE_URL"))
_SKIP_NO_DB = pytest.mark.skipif(not _HAS_DB, reason="DATABASE_URL not set")

# P84 risk-band SKU whose supply was pushed to today+10 in the seed (critical band —
# DOC ≈ 2 days → stockout is imminent → arrival is well after stockout).
_PULL_FORWARD_SKU = "SKU-001"

# P95 push_out seed SKU (slow_moving; ample cover >> 30 days at arrival).
_PUSH_OUT_SKU = "SKU-027"


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
# Smoke / schema-contract tests
# ===========================================================================


@_SKIP_NO_DB
async def test_analyze_supply_order_timing_returns_no_error() -> None:
    """Tool executes against the real DB without returning an error key."""
    from packages.tools.analyze_supply_order_timing_tool import AnalyzeSupplyOrderTimingTool

    result = await AnalyzeSupplyOrderTimingTool().handle({}, _ctx())

    assert "error" not in result.output, (
        f"Unexpected error: {result.output.get('error')}"
    )


@_SKIP_NO_DB
async def test_analyze_supply_order_timing_output_has_required_contract_keys() -> None:
    """Output must include all required top-level contract keys with correct types."""
    from packages.tools.analyze_supply_order_timing_tool import AnalyzeSupplyOrderTimingTool

    result = await AnalyzeSupplyOrderTimingTool().handle({}, _ctx())

    out = result.output
    for key in ("orders", "count", "truncated", "summary", "missing_data"):
        assert key in out, f"Contract key missing: {key}"

    assert isinstance(out["orders"], list), "orders must be a list"
    assert isinstance(out["count"], int), "count must be an int"
    assert isinstance(out["truncated"], bool), "truncated must be a bool"
    assert isinstance(out["missing_data"], list), "missing_data must be a list"
    assert isinstance(out["summary"], dict), "summary must be a dict"

    for skey in ("pull_forward_count", "push_out_count", "on_track_count"):
        assert skey in out["summary"], f"summary missing key: {skey}"


@_SKIP_NO_DB
async def test_analyze_supply_order_timing_summary_counts_consistent() -> None:
    """Summary counts must equal the row counts of each classification in the result.

    Per pre-cap semantics (AGENTS.md P95-B-01 context and module docstring),
    summary counts are computed BEFORE truncation.  count reflects the full pre-cap
    set.  When not truncated: len(orders) == count and sum of summary counts == count.
    """
    from packages.tools.analyze_supply_order_timing_tool import AnalyzeSupplyOrderTimingTool

    result = await AnalyzeSupplyOrderTimingTool().handle({}, _ctx())

    out = result.output
    if out["truncated"]:
        # When capped, len(orders) < count is expected — only verify summary arithmetic.
        total_in_summary = (
            out["summary"]["pull_forward_count"]
            + out["summary"]["push_out_count"]
            + out["summary"]["on_track_count"]
        )
        assert total_in_summary == out["count"], (
            f"summary counts sum {total_in_summary} != count {out['count']}"
        )
    else:
        # Not truncated: len(orders) == count == sum of summary counts.
        assert len(out["orders"]) == out["count"], (
            f"len(orders)={len(out['orders'])} != count={out['count']}"
        )
        total_in_summary = (
            out["summary"]["pull_forward_count"]
            + out["summary"]["push_out_count"]
            + out["summary"]["on_track_count"]
        )
        assert total_in_summary == out["count"], (
            f"summary counts sum {total_in_summary} != count {out['count']}"
        )


@_SKIP_NO_DB
async def test_analyze_supply_order_timing_truncated_is_false_for_seeded_db() -> None:
    """Seeded DB has far fewer than 100 open orders — truncated must be False."""
    from packages.tools.analyze_supply_order_timing_tool import AnalyzeSupplyOrderTimingTool

    result = await AnalyzeSupplyOrderTimingTool().handle({}, _ctx())

    assert result.output["truncated"] is False, (
        f"Expected truncated=False for seeded dev DB, got {result.output['truncated']}"
    )


# ===========================================================================
# T-587(a): >= 1 pull_forward_candidate including a P84 risk SKU with
#           positive days_misaligned
# ===========================================================================


@_SKIP_NO_DB
async def test_at_least_one_pull_forward_candidate_exists() -> None:
    """The seeded DB must yield at least 1 pull_forward_candidate order."""
    from packages.tools.analyze_supply_order_timing_tool import AnalyzeSupplyOrderTimingTool

    result = await AnalyzeSupplyOrderTimingTool().handle({}, _ctx())

    pull_orders = [
        o for o in result.output["orders"]
        if o["classification"] == "pull_forward_candidate"
    ]
    assert len(pull_orders) >= 1, (
        "Expected at least 1 pull_forward_candidate in seeded DB. "
        f"Got 0 from {result.output['count']} classified orders."
    )


@_SKIP_NO_DB
async def test_pull_forward_sku001_is_classified() -> None:
    """SKU-001 (P84 critical-risk band) must appear as a pull_forward_candidate.

    generate_supply() pushes all non-delivered risk-band orders to today+10.
    SKU-001 has DOC ≈ 2 days (critical band) → stockout is imminent → arrival
    at today+10 is after projected stockout → pull_forward_candidate.
    """
    from packages.tools.analyze_supply_order_timing_tool import AnalyzeSupplyOrderTimingTool

    result = await AnalyzeSupplyOrderTimingTool().handle({}, _ctx())

    sku001_orders = [
        o for o in result.output["orders"] if o["sku_id"] == _PULL_FORWARD_SKU
    ]
    assert len(sku001_orders) >= 1, (
        f"No orders for {_PULL_FORWARD_SKU} in tool output. "
        f"Total orders returned: {result.output['count']}"
    )

    for order in sku001_orders:
        assert order["classification"] == "pull_forward_candidate", (
            f"{_PULL_FORWARD_SKU} order {order['order_id']} expected "
            f"pull_forward_candidate, got {order['classification']!r}"
        )


@_SKIP_NO_DB
async def test_pull_forward_sku001_has_positive_days_misaligned() -> None:
    """SKU-001 pull_forward orders must have positive days_misaligned.

    days_misaligned = (expected_arrival - projected_stockout_date).days > 0
    because critical-band DOC ≈ 2 days < days_until_arrival ≈ 10.
    """
    from packages.tools.analyze_supply_order_timing_tool import AnalyzeSupplyOrderTimingTool

    result = await AnalyzeSupplyOrderTimingTool().handle(
        {"sku_id": _PULL_FORWARD_SKU}, _ctx()
    )

    assert "error" not in result.output, result.output.get("error")
    sku001_orders = result.output["orders"]
    assert len(sku001_orders) >= 1, f"No orders for {_PULL_FORWARD_SKU}"

    for order in sku001_orders:
        assert order["days_misaligned"] > 0, (
            f"{_PULL_FORWARD_SKU} order {order['order_id']}: "
            f"expected positive days_misaligned, got {order['days_misaligned']}"
        )


@_SKIP_NO_DB
async def test_pull_forward_sku001_projected_stockout_date_populated() -> None:
    """SKU-001 pull_forward orders must have a non-null projected_stockout_date.

    avg_daily > 0 (critical-band SKU has meaningful demand history) so the
    projected stockout date must be populated.
    """
    from packages.tools.analyze_supply_order_timing_tool import AnalyzeSupplyOrderTimingTool

    result = await AnalyzeSupplyOrderTimingTool().handle(
        {"sku_id": _PULL_FORWARD_SKU}, _ctx()
    )

    assert "error" not in result.output, result.output.get("error")
    for order in result.output["orders"]:
        assert order["projected_stockout_date"] is not None, (
            f"{_PULL_FORWARD_SKU} order {order['order_id']}: "
            "projected_stockout_date must not be null for a pull_forward order"
        )


@_SKIP_NO_DB
async def test_pull_forward_count_in_summary_is_positive() -> None:
    """pull_forward_count in summary must be >= 1 (P84 risk-band orders guarantee this)."""
    from packages.tools.analyze_supply_order_timing_tool import AnalyzeSupplyOrderTimingTool

    result = await AnalyzeSupplyOrderTimingTool().handle({}, _ctx())

    assert result.output["summary"]["pull_forward_count"] >= 1, (
        f"Expected pull_forward_count >= 1, got {result.output['summary']['pull_forward_count']}"
    )


# ===========================================================================
# T-587(b): SKU-027 order classified push_out_candidate with
#           days_of_cover_at_arrival > 30
# ===========================================================================


@_SKIP_NO_DB
async def test_push_out_sku027_appears_in_output() -> None:
    """SKU-027 (P95 push_out seed) must appear in the tool output."""
    from packages.tools.analyze_supply_order_timing_tool import AnalyzeSupplyOrderTimingTool

    result = await AnalyzeSupplyOrderTimingTool().handle({}, _ctx())

    sku_ids = {o["sku_id"] for o in result.output["orders"]}
    assert _PUSH_OUT_SKU in sku_ids, (
        f"{_PUSH_OUT_SKU} not found in tool output. "
        f"Present SKUs: {sorted(sku_ids)}"
    )


@_SKIP_NO_DB
async def test_push_out_sku027_classified_as_push_out_candidate() -> None:
    """SKU-027 P95 seed order must be classified as push_out_candidate.

    Seed: on_hand ≈ 115 units (inventory_snapshot two-warehouse total),
    avg_daily ≈ 0.57 units/day → DOC ≈ 200 days.  The P95 extra order
    arrives at today+5; days_of_cover_at_arrival ≈ 195 >> 30 → push_out.
    """
    from packages.tools.analyze_supply_order_timing_tool import AnalyzeSupplyOrderTimingTool

    result = await AnalyzeSupplyOrderTimingTool().handle(
        {"sku_id": _PUSH_OUT_SKU}, _ctx()
    )

    assert "error" not in result.output, result.output.get("error")

    sku027_orders = result.output["orders"]
    assert len(sku027_orders) >= 1, (
        f"No orders for {_PUSH_OUT_SKU} in tool output"
    )

    # At least one must be push_out_candidate (the P95 seed order at today+5).
    push_out_orders = [
        o for o in sku027_orders if o["classification"] == "push_out_candidate"
    ]
    assert len(push_out_orders) >= 1, (
        f"Expected at least 1 push_out_candidate for {_PUSH_OUT_SKU}. "
        f"Classifications: {[o['classification'] for o in sku027_orders]}"
    )


@_SKIP_NO_DB
async def test_push_out_sku027_days_of_cover_at_arrival_exceeds_30() -> None:
    """SKU-027 push_out orders must have days_of_cover_at_arrival > 30.

    This is the defining condition for push_out classification.
    """
    from packages.tools.analyze_supply_order_timing_tool import AnalyzeSupplyOrderTimingTool

    result = await AnalyzeSupplyOrderTimingTool().handle(
        {"sku_id": _PUSH_OUT_SKU}, _ctx()
    )

    assert "error" not in result.output, result.output.get("error")

    push_out_orders = [
        o for o in result.output["orders"] if o["classification"] == "push_out_candidate"
    ]
    assert len(push_out_orders) >= 1, f"No push_out orders for {_PUSH_OUT_SKU}"

    for order in push_out_orders:
        doc = order["days_of_cover_at_arrival"]
        assert doc is not None, (
            f"{_PUSH_OUT_SKU} push_out order {order['order_id']}: "
            "days_of_cover_at_arrival must not be null"
        )
        assert doc > 30, (
            f"{_PUSH_OUT_SKU} push_out order {order['order_id']}: "
            f"expected days_of_cover_at_arrival > 30, got {doc}"
        )


@_SKIP_NO_DB
async def test_push_out_sku027_days_misaligned_is_negative() -> None:
    """SKU-027 push_out orders must have negative days_misaligned.

    days_misaligned = -floor(days_of_cover_at_arrival - PUSH_OUT_COVER_DAYS)
    With DOC_at_arrival ≈ 195 and PUSH_OUT_COVER_DAYS=30:
    days_misaligned = -floor(195 - 30) = -165 (exact value depends on seed).
    Must be strongly negative (< -1).
    """
    from packages.tools.analyze_supply_order_timing_tool import AnalyzeSupplyOrderTimingTool

    result = await AnalyzeSupplyOrderTimingTool().handle(
        {"sku_id": _PUSH_OUT_SKU}, _ctx()
    )

    assert "error" not in result.output, result.output.get("error")

    push_out_orders = [
        o for o in result.output["orders"] if o["classification"] == "push_out_candidate"
    ]
    for order in push_out_orders:
        assert order["days_misaligned"] < 0, (
            f"{_PUSH_OUT_SKU} push_out order {order['order_id']}: "
            f"expected negative days_misaligned, got {order['days_misaligned']}"
        )


@_SKIP_NO_DB
async def test_push_out_count_in_summary_is_positive() -> None:
    """push_out_count in summary must be >= 1 (SKU-027 P95 seed guarantees this)."""
    from packages.tools.analyze_supply_order_timing_tool import AnalyzeSupplyOrderTimingTool

    result = await AnalyzeSupplyOrderTimingTool().handle({}, _ctx())

    assert result.output["summary"]["push_out_count"] >= 1, (
        f"Expected push_out_count >= 1, got {result.output['summary']['push_out_count']}"
    )


# ===========================================================================
# T-587(c): Contract keys (missing_data, truncated, count) and
#           summary counts consistent with row classifications (pre-cap semantics)
# ===========================================================================


@_SKIP_NO_DB
async def test_missing_data_is_list_type() -> None:
    """missing_data must always be a list (even if empty)."""
    from packages.tools.analyze_supply_order_timing_tool import AnalyzeSupplyOrderTimingTool

    result = await AnalyzeSupplyOrderTimingTool().handle({}, _ctx())

    assert isinstance(result.output["missing_data"], list), (
        f"missing_data must be a list, got {type(result.output['missing_data'])}"
    )


@_SKIP_NO_DB
async def test_count_equals_sum_of_summary_counts() -> None:
    """count must equal pull_forward_count + push_out_count + on_track_count.

    This is the pre-cap semantics contract: summary counts are derived from the
    full classified set; count is the total pre-cap size.
    """
    from packages.tools.analyze_supply_order_timing_tool import AnalyzeSupplyOrderTimingTool

    result = await AnalyzeSupplyOrderTimingTool().handle({}, _ctx())

    out = result.output
    summary_total = (
        out["summary"]["pull_forward_count"]
        + out["summary"]["push_out_count"]
        + out["summary"]["on_track_count"]
    )
    assert summary_total == out["count"], (
        f"summary_total={summary_total} != count={out['count']}. "
        "Pre-cap semantics violated."
    )


@_SKIP_NO_DB
async def test_order_row_keys_are_complete() -> None:
    """Every order row returned by the real DB must include all required keys."""
    from packages.tools.analyze_supply_order_timing_tool import AnalyzeSupplyOrderTimingTool

    result = await AnalyzeSupplyOrderTimingTool().handle({}, _ctx())

    required_keys = {
        "order_id", "sku_id", "supplier_id", "order_date", "expected_arrival",
        "quantity", "status", "on_hand", "avg_daily_demand",
        "projected_stockout_date", "days_of_cover_at_arrival",
        "days_misaligned", "classification",
    }
    for order in result.output["orders"]:
        missing = required_keys - order.keys()
        assert not missing, (
            f"Order row {order.get('order_id', '?')} is missing keys: {missing}"
        )


# ===========================================================================
# T-587(d): Deterministic ordering
# ===========================================================================


@_SKIP_NO_DB
async def test_orders_sorted_pull_forward_before_push_out_before_on_track() -> None:
    """pull_forward orders must appear before push_out, which appear before on_track.

    The seeded DB contains both pull_forward and push_out candidates, so all
    three class boundaries are exercisable.
    """
    from packages.tools.analyze_supply_order_timing_tool import AnalyzeSupplyOrderTimingTool

    result = await AnalyzeSupplyOrderTimingTool().handle({}, _ctx())

    orders = result.output["orders"]
    if len(orders) < 2:
        pytest.skip("Not enough orders to test sort order")

    _CLASS_ORDER = {"pull_forward_candidate": 0, "push_out_candidate": 1, "on_track": 2}
    prev_rank = -1
    for order in orders:
        rank = _CLASS_ORDER[order["classification"]]
        assert rank >= prev_rank, (
            f"Sort order violated: {order['classification']} (rank {rank}) "
            f"appears after rank {prev_rank}"
        )
        prev_rank = rank


@_SKIP_NO_DB
async def test_orders_within_class_sorted_by_abs_days_misaligned_desc() -> None:
    """Within each classification, orders must be sorted by |days_misaligned| descending.

    Checks the pull_forward group only (most likely to have multiple members in
    the seeded DB due to multiple risk-band SKUs).
    """
    from packages.tools.analyze_supply_order_timing_tool import AnalyzeSupplyOrderTimingTool

    result = await AnalyzeSupplyOrderTimingTool().handle({}, _ctx())

    pull_orders = [
        o for o in result.output["orders"] if o["classification"] == "pull_forward_candidate"
    ]
    if len(pull_orders) < 2:
        pytest.skip("Not enough pull_forward orders to test intra-class sort")

    for i in range(len(pull_orders) - 1):
        a, b = pull_orders[i], pull_orders[i + 1]
        abs_a = abs(a["days_misaligned"])
        abs_b = abs(b["days_misaligned"])
        assert abs_a >= abs_b or a["order_id"] <= b["order_id"], (
            f"Sort violated at position {i}: "
            f"{a['order_id']} |dm|={abs_a} vs {b['order_id']} |dm|={abs_b}"
        )
