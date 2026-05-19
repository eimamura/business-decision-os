"""Unit tests for generate_sample_data.py (B04)."""
import csv
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
import generate_sample_data as gen

OUT_DIR = Path("data/sample")
GT_DIR = Path("data/sample/ground_truth")


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
    rows = _run_and_read(42, "customers.csv")
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
    rows = _run_and_read(42, "inventory.csv")
    required = {"sku_id", "warehouse_id", "on_hand", "on_order", "snapshot_date"}
    assert required <= set(rows[0].keys())
    assert len(rows) == 30 * 2


def test_supply_csv_columns():
    rows = _run_and_read(42, "supply.csv")
    required = {"sku_id", "supplier_id", "order_date", "expected_arrival", "quantity", "status"}
    assert required <= set(rows[0].keys())


def test_cost_csv_columns():
    rows = _run_and_read(42, "cost.csv")
    required = {"sku_id", "period_start", "period_end", "cogs", "holding_cost", "ordering_cost", "stockout_cost"}
    assert required <= set(rows[0].keys())
    assert len(rows) == 30


def _load_gt_sku_params() -> list[dict]:
    with open(GT_DIR / "sku_parameters.csv", newline="") as f:
        return list(csv.DictReader(f))


def _load_gt_customer_params() -> list[dict]:
    with open(GT_DIR / "customer_parameters.csv", newline="") as f:
        return list(csv.DictReader(f))
