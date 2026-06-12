from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from packages.persistence.sample_data import replace_operational_tables


class FakeTransaction:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None


class FakeConnection:
    def __init__(self) -> None:
        self.statements: list[str] = []
        self.insert_counts: dict[str, int] = {}

    def transaction(self) -> FakeTransaction:
        return FakeTransaction()

    async def execute(self, sql: str) -> None:
        self.statements.append(sql)

    async def executemany(self, sql: str, rows: list[tuple[Any, ...]]) -> None:
        self.statements.append(sql)
        table_name = sql.split()[2]
        self.insert_counts[table_name] = len(rows)

    async def fetch(self, sql: str) -> list[dict[str, Any]]:
        self.statements.append(sql)
        table_name = sql.split()[3]
        return [{"table_name": table_name, "loaded": self.insert_counts[table_name]}]


def _write_csv(path: Path, columns: list[str], rows: list[list[str]]) -> None:
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        writer.writerows(rows)


async def test_replace_operational_tables_uses_fk_safe_order(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "sku_master.csv",
        ["sku_id", "name", "category", "sku_type", "moq",
         "lead_time_days_mean", "lead_time_days_std", "holding_cost_pct", "unit_cost"],
        [["SKU-001", "Test SKU", "parts", "critical", "10", "5", "1", "0.1", "25.5"]],
    )
    _write_csv(
        tmp_path / "location_master.csv",
        ["location_id", "name", "region", "country", "location_type",
         "capacity_units", "handling_cost_per_unit", "lead_time_to_customer_days"],
        [["WH-001", "Test Hub", "Kanto", "JP", "warehouse", "50000", "0.15", "2"]],
    )
    _write_csv(
        tmp_path / "customer_master.csv",
        ["customer_id", "segment", "sku_affinity_json"],
        [["CUST-001", "large", '{"SKU-001": 1.0}']],
    )
    _write_csv(
        tmp_path / "inventory_snapshot.csv",
        ["sku_id", "warehouse_id", "on_hand", "on_order", "snapshot_date"],
        [["SKU-001", "WH-001", "10", "2", "2026-05-19"]],
    )
    _write_csv(
        tmp_path / "demand_history.csv",
        ["sku_id", "date", "quantity", "is_missing"],
        [["SKU-001", "2025-01-01", "", "True"]],
    )
    _write_csv(
        tmp_path / "supply_orders.csv",
        ["sku_id", "supplier_id", "order_date", "expected_arrival", "quantity", "status"],
        [["SKU-001", "SUP-001", "2026-04-01", "2026-04-07", "10", "delivered"]],
    )
    _write_csv(
        tmp_path / "cost_master.csv",
        ["sku_id", "period_start", "period_end", "cogs",
         "holding_cost", "ordering_cost", "stockout_cost"],
        [["SKU-001", "2025-01-01", "2025-12-31", "100.50", "10.25", "5.75", "2.50"]],
    )
    _write_csv(
        tmp_path / "forecast_history.csv",
        ["sku_id", "forecast_date", "target_date", "forecast_qty", "model_version"],
        [["SKU-001", "2024-12-02", "2025-01-01", "310.50", "v1.0-naive"]],
    )
    _write_csv(
        tmp_path / "customer_orders.csv",
        ["order_id", "customer_id", "sku_id", "ship_from_location_id",
         "region", "quantity", "order_date", "requested_ship_date", "status"],
        [["CO-0001", "CUST-001", "SKU-001", "WH-001",
          "Kanto", "100", "2026-06-01", "2026-06-05", "open"]],
    )
    _write_csv(
        tmp_path / "shipments.csv",
        ["shipment_id", "order_id", "carrier", "planned_ship_date",
         "actual_ship_date", "planned_delivery_date", "actual_delivery_date", "status"],
        [["SH-CO-0009", "CO-0001", "CARRIER-A",
          "2026-06-01", "2026-06-01", "2026-06-04", "2026-06-04", "delivered"]],
    )
    _write_csv(
        tmp_path / "production_capacity.csv",
        ["location_id", "week_start", "capacity_units"],
        [["WH-001", "2026-06-09", "2000"]],
    )
    _write_csv(
        tmp_path / "production_plan.csv",
        ["sku_id", "location_id", "week_start", "planned_qty"],
        [["SKU-001", "WH-001", "2026-06-09", "10"]],
    )

    conn = FakeConnection()

    summaries = await replace_operational_tables(conn, tmp_path)  # type: ignore[arg-type]

    deletes = [s for s in conn.statements if s.startswith("DELETE")]
    inserts = [s.split()[2] for s in conn.statements if s.startswith("INSERT")]

    # DELETE order: child tables first (production_plan → production_capacity →
    #               shipments → customer_orders → ... → sku_master)
    assert deletes == [
        "DELETE FROM production_plan",
        "DELETE FROM production_capacity",
        "DELETE FROM shipments",
        "DELETE FROM customer_orders",
        "DELETE FROM forecast_history",
        "DELETE FROM cost_master",
        "DELETE FROM supply_orders",
        "DELETE FROM demand_history",
        "DELETE FROM inventory_snapshot",
        "DELETE FROM customer_master",
        "DELETE FROM location_master",
        "DELETE FROM sku_master",
    ]
    # INSERT order: parent tables first (sku_master → ... → shipments →
    #               production_capacity → production_plan)
    assert inserts == [
        "sku_master", "location_master", "customer_master",
        "inventory_snapshot", "demand_history", "supply_orders",
        "cost_master", "forecast_history", "customer_orders", "shipments",
        "production_capacity", "production_plan",
    ]
    assert [summary["table_name"] for summary in summaries] == inserts
