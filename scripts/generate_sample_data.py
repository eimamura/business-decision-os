#!/usr/bin/env python3
"""Generate synthetic operational sample data for Business Decision OS.

Usage:
    uv run python scripts/generate_sample_data.py [--seed N]

Outputs written to data/sample/ (NOT ground_truth/).
"""
import argparse
import csv
import math
import random
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

CsvRow = dict[str, str]

START_DATE = date(2025, 1, 1)
SUPPLIERS = {"critical": "SUP-001", "standard": "SUP-002", "slow_moving": "SUP-003"}

DETERMINISTIC_NULL_SKUS = {"SKU-003", "SKU-005", "SKU-007"}
CONTIGUOUS_GAP_SKU = "SKU-001"
CONTIGUOUS_GAP_START_DAY = 60
CONTIGUOUS_GAP_LENGTH = 7


@dataclass(frozen=True)
class SampleDataConfig:
    seed: int = 42
    sku_count: int = 30
    horizon_days: int = 365
    warehouse_count: int = 2
    missing_rate: float = 0.02

    @property
    def warehouses(self) -> list[str]:
        return [f"WH-{idx:03d}" for idx in range(1, self.warehouse_count + 1)]


def _load_csv(path: Path) -> list[CsvRow]:
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def _neg_binom_demand(rng: random.Random, mu: float, dispersion: float) -> int:
    if mu <= 0:
        return 0
    variance = mu + (dispersion * mu) ** 2
    if variance <= mu:
        return max(0, int(rng.gauss(mu, mu**0.5)))
    sigma = variance**0.5
    return max(0, int(rng.gauss(mu, sigma)))


def _lognormal_lead_time(rng: random.Random, mean: float, std: float) -> int:
    if mean <= 0:
        return 1
    cv = std / mean if mean > 0 else 0.1
    sigma_log = math.log(1 + cv**2) ** 0.5
    mu_log = math.log(mean) - 0.5 * sigma_log**2
    sample = rng.gauss(mu_log, sigma_log)
    return max(1, int(math.exp(sample) + 0.5))


def _seasonal_factor(day: int, amplitude: float, period: float) -> float:
    if amplitude == 0.0:
        return 1.0
    return 1.0 + amplitude * math.sin(2 * math.pi * day / period)


def generate_sku_master(skus: list[CsvRow], out_dir: Path) -> None:
    fields = [
        "sku_id", "name", "category", "sku_type", "moq",
        "lead_time_days_mean", "lead_time_days_std", "holding_cost_pct", "unit_cost",
    ]
    with open(out_dir / "sku_master.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in skus:
            writer.writerow({k: row[k] for k in fields})


def generate_customers(customers: list[CsvRow], out_dir: Path) -> None:
    fields = ["customer_id", "segment", "sku_affinity_json"]
    with open(out_dir / "customers.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in customers:
            writer.writerow({k: row[k] for k in fields})


def generate_demand_history(
    skus: list[CsvRow], rng: random.Random, out_dir: Path, config: SampleDataConfig
) -> None:
    gap_end = CONTIGUOUS_GAP_START_DAY + CONTIGUOUS_GAP_LENGTH
    gap_days = set(range(CONTIGUOUS_GAP_START_DAY, gap_end))

    fields = ["sku_id", "date", "quantity", "is_missing"]
    with open(out_dir / "demand_history.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()

        for sku in skus:
            sku_id = sku["sku_id"]
            base_mean = float(sku["base_demand_mean"])
            dispersion = float(sku["demand_dispersion"])
            amplitude = float(sku["seasonal_amplitude"])
            period = float(sku["seasonal_period_days"])

            for day_idx in range(config.horizon_days):
                current_date = START_DATE + timedelta(days=day_idx)
                mu = base_mean * _seasonal_factor(day_idx, amplitude, period)
                qty = _neg_binom_demand(rng, mu, dispersion)

                is_missing = False

                if sku_id == CONTIGUOUS_GAP_SKU and day_idx in gap_days:
                    is_missing = True
                elif sku_id in DETERMINISTIC_NULL_SKUS and rng.random() < config.missing_rate:
                    is_missing = True
                elif sku_id not in DETERMINISTIC_NULL_SKUS and sku_id != CONTIGUOUS_GAP_SKU:
                    if rng.random() < config.missing_rate:
                        is_missing = True

                writer.writerow({
                    "sku_id": sku_id,
                    "date": current_date.isoformat(),
                    "quantity": "" if is_missing else qty,
                    "is_missing": is_missing,
                })


def generate_inventory(
    skus: list[CsvRow], rng: random.Random, out_dir: Path, config: SampleDataConfig
) -> None:
    snapshot_date = date(2026, 5, 19).isoformat()
    fields = ["sku_id", "warehouse_id", "on_hand", "on_order", "snapshot_date"]

    with open(out_dir / "inventory.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()

        for sku in skus:
            sku_id = sku["sku_id"]
            daily_demand = float(sku["base_demand_mean"])
            lt_mean = float(sku["lead_time_days_mean"])
            unit_cost = float(sku["unit_cost"])

            normal_on_hand = int(daily_demand * (lt_mean + 14))

            for wh in config.warehouses:
                roll = rng.random()
                if roll < 0.15 and unit_cost > 100:
                    on_hand = int(daily_demand * 150)
                    on_order = 0
                elif roll < 0.10:
                    on_hand = 0
                    on_order = max(1, int(daily_demand * lt_mean))
                else:
                    on_hand = max(0, int(rng.gauss(normal_on_hand, normal_on_hand * 0.15)))
                    on_order = max(0, int(rng.gauss(daily_demand * 7, daily_demand * 2)))

                writer.writerow({
                    "sku_id": sku_id,
                    "warehouse_id": wh,
                    "on_hand": on_hand,
                    "on_order": on_order,
                    "snapshot_date": snapshot_date,
                })


def generate_supply(skus: list[CsvRow], rng: random.Random, out_dir: Path) -> None:
    fields = ["sku_id", "supplier_id", "order_date", "expected_arrival", "quantity", "status"]
    base_order_date = date(2026, 4, 1)

    with open(out_dir / "supply.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()

        for sku in skus:
            sku_id = sku["sku_id"]
            sku_type = sku["sku_type"]
            supplier_id = SUPPLIERS[sku_type]
            moq = int(sku["moq"])
            lt_mean = float(sku["lead_time_days_mean"])
            lt_std = float(sku["lead_time_days_std"])

            num_orders = rng.randint(3, 5)
            for i in range(num_orders):
                order_offset = rng.randint(0, 45)
                order_date = base_order_date + timedelta(days=order_offset)
                lead_days = _lognormal_lead_time(rng, lt_mean, lt_std)
                arrival_date = order_date + timedelta(days=lead_days)
                quantity = moq * rng.randint(1, 4)

                if arrival_date < date(2026, 5, 19):
                    status = "delivered"
                elif arrival_date < date(2026, 6, 1):
                    status = "in_transit"
                else:
                    status = "pending"

                writer.writerow({
                    "sku_id": sku_id,
                    "supplier_id": supplier_id,
                    "order_date": order_date.isoformat(),
                    "expected_arrival": arrival_date.isoformat(),
                    "quantity": quantity,
                    "status": status,
                })


def generate_cost(
    skus: list[CsvRow], rng: random.Random, out_dir: Path, config: SampleDataConfig
) -> None:
    period_start = date(2025, 1, 1).isoformat()
    period_end = date(2025, 12, 31).isoformat()
    fields = [
        "sku_id", "period_start", "period_end",
        "cogs", "holding_cost", "ordering_cost", "stockout_cost",
    ]

    with open(out_dir / "cost.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()

        for sku in skus:
            sku_id = sku["sku_id"]
            unit_cost = float(sku["unit_cost"])
            holding_pct = float(sku["holding_cost_pct"])
            daily_demand = float(sku["base_demand_mean"])
            annual_demand = daily_demand * config.horizon_days

            cogs = round(annual_demand * unit_cost * rng.uniform(0.9, 1.1), 2)
            avg_inventory = daily_demand * float(sku["lead_time_days_mean"])
            holding_cost = round(
                avg_inventory * unit_cost * holding_pct * rng.uniform(0.85, 1.15), 2
            )
            ordering_cost = round(rng.uniform(50, 500) * rng.randint(12, 52), 2)
            stockout_cost = round(annual_demand * unit_cost * rng.uniform(0.01, 0.05), 2)

            writer.writerow({
                "sku_id": sku_id,
                "period_start": period_start,
                "period_end": period_end,
                "cogs": cogs,
                "holding_cost": holding_cost,
                "ordering_cost": ordering_cost,
                "stockout_cost": stockout_cost,
            })


def generate(config: SampleDataConfig, out_dir: Path = Path("data/sample")) -> None:
    rng = random.Random(config.seed)

    gt_dir = Path("data/sample/ground_truth")
    out_dir.mkdir(parents=True, exist_ok=True)

    skus = _load_csv(gt_dir / "sku_parameters.csv")[: config.sku_count]
    customers = _load_csv(gt_dir / "customer_parameters.csv")

    generate_sku_master(skus, out_dir)
    generate_customers(customers, out_dir)
    generate_demand_history(skus, rng, out_dir, config)
    generate_inventory(skus, rng, out_dir, config)
    generate_supply(skus, rng, out_dir)
    generate_cost(skus, rng, out_dir, config)

    print(
        f"Sample data generated in {out_dir}/ "
        f"(seed={config.seed}, sku_count={config.sku_count}, "
        f"horizon_days={config.horizon_days}, warehouse_count={config.warehouse_count}, "
        f"missing_rate={config.missing_rate})"
    )


def main(
    seed: int = 42,
    sku_count: int = 30,
    horizon_days: int = 365,
    warehouse_count: int = 2,
    missing_rate: float = 0.02,
) -> None:
    generate(
        SampleDataConfig(
            seed=seed,
            sku_count=sku_count,
            horizon_days=horizon_days,
            warehouse_count=warehouse_count,
            missing_rate=missing_rate,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate synthetic sample data")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")
    parser.add_argument("--sku-count", type=int, default=30, help="SKU count, 1..30 (default: 30)")
    parser.add_argument(
        "--horizon-days", type=int, default=365, help="Demand horizon days, 1..1095 (default: 365)"
    )
    parser.add_argument(
        "--warehouse-count", type=int, default=2, help="Warehouse count, 1..10 (default: 2)"
    )
    parser.add_argument(
        "--missing-rate",
        type=float,
        default=0.02,
        help="Demand missing rate, 0..0.25 (default: 0.02)",
    )
    args = parser.parse_args()
    main(
        seed=args.seed,
        sku_count=args.sku_count,
        horizon_days=args.horizon_days,
        warehouse_count=args.warehouse_count,
        missing_rate=args.missing_rate,
    )
