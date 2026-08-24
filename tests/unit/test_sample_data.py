"""Unit tests for generate_sample_data.py (B04).

Hermetic execution (T-748 / D-021): every generated operational CSV is routed
to a pytest tmp_path directory; tracked data/sample/ is never written.
"""
from __future__ import annotations

import csv
import datetime
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
import generate_sample_data as gen

OUT_DIR = Path("data/sample")
GT_DIR = Path("data/sample/ground_truth")


@pytest.fixture(autouse=True)
def _isolated_out_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Route all generated operational CSVs into tmp_path (T-748 / D-021).

    Wraps ``gen.main`` so generation writes to a per-test temporary directory
    instead of the tracked ``data/sample`` default, and repoints the module's
    ``OUT_DIR`` reads at the same directory. Ground-truth parameter reads are
    unaffected.
    """
    out_dir = tmp_path / "sample"

    def _main(**config_overrides: Any) -> None:
        gen.generate(gen.SampleDataConfig(**config_overrides), out_dir=out_dir)

    monkeypatch.setattr(gen, "main", _main)
    monkeypatch.setitem(globals(), "OUT_DIR", out_dir)


def _run_and_read(seed: int, filename: str) -> list[dict]:
    gen.main(seed=seed)
    with open(OUT_DIR / filename, newline="") as f:
        return list(csv.DictReader(f))


def test_deterministic_output_seed42():
    gen.main(seed=42)
    rows_a = (OUT_DIR / "demand_history.csv").read_bytes()

    gen.main(seed=42)
    rows_b = (OUT_DIR / "demand_history.csv").read_bytes()

    assert rows_a == rows_b, "seed=42 must produce byte-identical output on two runs"


def test_sku_master_columns_present():
    gen.main(seed=42)
    rows = _run_and_read(42, "sku_master.csv")
    required = {"sku_id", "name", "category", "sku_type", "moq",
                "lead_time_days_mean", "lead_time_days_std", "holding_cost_pct", "unit_cost"}
    assert required <= set(rows[0].keys())
    assert len(rows) == 30


def test_demand_history_row_count():
    rows = _run_and_read(42, "demand_history.csv")
    assert len(rows) == 30 * 365


def test_configurable_sku_horizon_and_warehouse_counts():
    gen.main(seed=42, sku_count=5, horizon_days=10, warehouse_count=3)

    with open(OUT_DIR / "sku_master.csv", newline="") as f:
        sku_rows = list(csv.DictReader(f))
    with open(OUT_DIR / "inventory_snapshot.csv", newline="") as f:
        inventory_rows = list(csv.DictReader(f))
    with open(OUT_DIR / "demand_history.csv", newline="") as f:
        demand_rows = list(csv.DictReader(f))

    assert len(sku_rows) == 5
    assert len(inventory_rows) == 5 * 3
    assert len(demand_rows) == 5 * 10
    assert {r["warehouse_id"] for r in inventory_rows} == {"WH-001", "WH-002", "WH-003"}


def test_configurable_missing_rate_applies_to_demand_history():
    gen.main(seed=42, sku_count=30, horizon_days=365, missing_rate=0.10)
    with open(OUT_DIR / "demand_history.csv", newline="") as f:
        rows = list(csv.DictReader(f))

    non_gap_rows = [
        r for r in rows
        if not (r["sku_id"] == gen.CONTIGUOUS_GAP_SKU and r["is_missing"] == "True")
    ]
    missing = sum(1 for r in non_gap_rows if r["is_missing"] == "True")
    rate = missing / len(non_gap_rows)
    assert 0.08 <= rate <= 0.12


def test_null_rate_approximately_two_percent():
    rows = _run_and_read(42, "demand_history.csv")
    non_gap_rows = [
        r for r in rows
        if not (r["sku_id"] == gen.CONTIGUOUS_GAP_SKU and r["is_missing"] == "True")
    ]
    missing = sum(1 for r in non_gap_rows if r["is_missing"] == "True")
    rate = missing / len(non_gap_rows)
    assert 0.015 <= rate <= 0.025, f"NULL rate {rate:.4f} outside [0.015, 0.025]"


def test_contiguous_gap_sku001():
    rows = _run_and_read(42, "demand_history.csv")
    sku001 = [r for r in rows if r["sku_id"] == "SKU-001"]
    gap_rows = [r for r in sku001 if r["is_missing"] == "True"]
    assert len(gap_rows) >= gen.CONTIGUOUS_GAP_LENGTH, (
        f"SKU-001 should have at least {gen.CONTIGUOUS_GAP_LENGTH} missing rows"
    )

    missing_indices = [i for i, r in enumerate(sku001) if r["is_missing"] == "True"]
    contiguous = all(
        missing_indices[i + 1] == missing_indices[i] + 1
        for i in range(gen.CONTIGUOUS_GAP_LENGTH - 1)
    )
    assert contiguous, "First 7 missing rows for SKU-001 must be contiguous"


def test_seasonal_amplitude_for_sku_008_009_010():
    rows = _load_gt_sku_params()
    seasonal_skus = {r["sku_id"]: float(r["seasonal_amplitude"]) for r in rows
                     if r["sku_id"] in {"SKU-008", "SKU-009", "SKU-010"}}
    assert len(seasonal_skus) == 3, "SKU-008, 009, 010 must all be in ground truth"
    for sku_id, amplitude in seasonal_skus.items():
        assert amplitude > 0.3, f"{sku_id} seasonal_amplitude {amplitude} must be > 0.3"


def test_sku_type_buckets():
    rows = _load_gt_sku_params()
    critical = [r for r in rows if r["sku_type"] == "critical"]
    standard = [r for r in rows if r["sku_type"] == "standard"]
    slow = [r for r in rows if r["sku_type"] == "slow_moving"]
    assert len(critical) == 10
    assert len(standard) == 15
    assert len(slow) == 5


def test_critical_sku_ids():
    rows = _load_gt_sku_params()
    critical_ids = {r["sku_id"] for r in rows if r["sku_type"] == "critical"}
    expected = {f"SKU-{i:03d}" for i in range(1, 11)}
    assert critical_ids == expected


def test_slow_moving_low_demand():
    rows = _load_gt_sku_params()
    slow = [r for r in rows if r["sku_type"] == "slow_moving"]
    for r in slow:
        demand = float(r["base_demand_mean"])
        assert demand <= 2.0, f"{r['sku_id']} base_demand_mean {demand} must be <= 2.0"


def test_customers_csv_columns():
    rows = _run_and_read(42, "customer_master.csv")
    assert len(rows) == 20
    required = {"customer_id", "segment", "sku_affinity_json"}
    assert required <= set(rows[0].keys())


def test_customer_segment_counts():
    rows = _load_gt_customer_params()
    large = [r for r in rows if r["segment"] == "large"]
    small = [r for r in rows if r["segment"] == "small"]
    spot = [r for r in rows if r["segment"] == "spot"]
    assert len(large) == 5
    assert len(small) == 10
    assert len(spot) == 5


def test_inventory_csv_columns():
    rows = _run_and_read(42, "inventory_snapshot.csv")
    required = {"sku_id", "warehouse_id", "on_hand", "on_order", "snapshot_date"}
    assert required <= set(rows[0].keys())
    assert len(rows) == 30 * 2


def test_supply_csv_columns():
    rows = _run_and_read(42, "supply_orders.csv")
    required = {"sku_id", "supplier_id", "order_date", "expected_arrival", "quantity", "status"}
    assert required <= set(rows[0].keys())


def test_cost_csv_columns():
    rows = _run_and_read(42, "cost_master.csv")
    required = {
        "sku_id", "period_start", "period_end", "cogs",
        "holding_cost", "ordering_cost", "stockout_cost",
    }
    assert required <= set(rows[0].keys())
    assert len(rows) == 30


def test_location_master_csv_columns():
    rows = _run_and_read(42, "location_master.csv")
    required = {"location_id", "name", "region", "country", "location_type",
                "capacity_units", "handling_cost_per_unit", "lead_time_to_customer_days"}
    assert required <= set(rows[0].keys())
    assert len(rows) == 2  # default warehouse_count=2


def test_forecast_history_csv_columns():
    rows = _run_and_read(42, "forecast_history.csv")
    required = {"sku_id", "forecast_date", "target_date", "forecast_qty", "model_version"}
    assert required <= set(rows[0].keys())
    # 30 SKUs × 12 months (365 // 30) = 360 standard rows
    # P94 T-579: FORECAST_OVER_SKU + FORECAST_UNDER_SKU × 4 weeks = 8 additional rows
    assert len(rows) == 30 * 12 + 8  # 368 total rows


def _load_gt_sku_params() -> list[dict]:
    with open(GT_DIR / "sku_parameters.csv", newline="") as f:
        return list(csv.DictReader(f))


def _load_gt_customer_params() -> list[dict]:
    with open(GT_DIR / "customer_parameters.csv", newline="") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------------------
# Risk band distribution (T-529): deterministic inventory overrides ensure
# the demo query "Which products are at stockout risk this week?" returns
# the expected risk distribution after re-seeding.
# ---------------------------------------------------------------------------

def _inv_on_hand(inventory_rows: list[dict], sku_id: str) -> float:
    """Sum on_hand across all warehouses for the given SKU."""
    return sum(float(r["on_hand"]) for r in inventory_rows if r["sku_id"] == sku_id)


def _actual_recent_avg(sku_id: str) -> float:
    """Return the actual 30-day rolling average daily demand for *sku_id*.

    Reads from the already-generated demand_history.csv and applies the same
    logic as ``gen.compute_recent_avg`` (and the tool's SQL query) so the test
    assertion uses the same demand figure that ``list_stockout_risk`` will use
    at runtime.
    """
    with open(OUT_DIR / "demand_history.csv", newline="") as f:
        rows = list(csv.DictReader(f))
    return gen.compute_recent_avg(rows, sku_id)


@pytest.mark.parametrize("sku_id", ["SKU-001", "SKU-002"])
def test_risk_band_critical_projected_negative(sku_id: str) -> None:
    """Critical-band SKUs must have on_hand_qty < 7-day demand (projected < 0).

    Uses the actual recent demand average (mirrors the tool's SQL) rather than
    the nominal base_demand_mean so the assertion is valid even when seasonality
    or noise shifts the rolling average away from the CSV parameter value.
    """
    # _run_and_read calls gen.main internally, regenerating all files consistently.
    inv_rows = _run_and_read(42, "inventory_snapshot.csv")
    on_hand = _inv_on_hand(inv_rows, sku_id)
    avg_daily = _actual_recent_avg(sku_id)
    demand_7 = avg_daily * 7
    projected = on_hand - demand_7  # incoming=0 for risk SKUs
    assert projected < 0, (
        f"{sku_id}: on_hand={on_hand}, avg_daily={avg_daily:.3f}, "
        f"demand_7={demand_7:.3f}, projected={projected:.3f} should be < 0"
    )


@pytest.mark.parametrize("sku_id", ["SKU-003", "SKU-004"])
def test_risk_band_high_ratio_below_0_1(sku_id: str) -> None:
    """High-band SKUs must have 0 <= projected_ending_stock / demand_forecast < 0.1."""
    inv_rows = _run_and_read(42, "inventory_snapshot.csv")
    on_hand = _inv_on_hand(inv_rows, sku_id)
    avg_daily = _actual_recent_avg(sku_id)
    demand_7 = avg_daily * 7
    projected = on_hand - demand_7
    ratio = projected / demand_7
    assert 0.0 <= projected, (
        f"{sku_id}: projected={projected:.3f} must be non-negative for 'high' (not 'critical')"
    )
    assert ratio < 0.1, (
        f"{sku_id}: ratio={ratio:.4f} must be < 0.1 for 'high' band"
    )


@pytest.mark.parametrize("sku_id", ["SKU-005", "SKU-006", "SKU-007"])
def test_risk_band_medium_ratio_in_range(sku_id: str) -> None:
    """Medium-band SKUs must have 0.1 <= projected_ending_stock / demand_forecast < 0.5."""
    inv_rows = _run_and_read(42, "inventory_snapshot.csv")
    on_hand = _inv_on_hand(inv_rows, sku_id)
    avg_daily = _actual_recent_avg(sku_id)
    demand_7 = avg_daily * 7
    projected = on_hand - demand_7
    ratio = projected / demand_7
    assert 0.1 <= ratio < 0.5, (
        f"{sku_id}: ratio={ratio:.4f} must be in [0.1, 0.5) for 'medium' band; "
        f"on_hand={on_hand}, avg_daily={avg_daily:.3f}"
    )


@pytest.mark.parametrize("sku_id", gen.SKU_RISK_BANDS.keys())
def test_risk_band_no_supply_arriving_within_7_days(sku_id: str) -> None:
    """Risk-band SKU supply orders must not have non-delivered arrivals within 7 days."""
    rows = _run_and_read(42, "supply_orders.csv")
    today = datetime.date.today()
    cutoff = today + datetime.timedelta(days=7)
    delivered_cutoff = today - datetime.timedelta(days=22)
    for row in rows:
        if row["sku_id"] != sku_id:
            continue
        arrival = datetime.date.fromisoformat(row["expected_arrival"])
        status = row["status"]
        if arrival >= delivered_cutoff and arrival <= cutoff:
            assert status == "delivered", (
                f"{sku_id}: non-delivered order (status={status}) arriving {arrival} "
                f"is within the 7-day tool horizon — would rescue the risk classification"
            )
