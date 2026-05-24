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
        [
            "sku_id",
            "name",
            "category",
            "sku_type",
            "moq",
            "lead_time_days_mean",
            "lead_time_days_std",
            "holding_cost_pct",
            "unit_cost",
        ],
        [["SKU-001", "Test SKU", "parts", "critical", "10", "5", "1", "0.1", "25.5"]],
    )
    _write_csv(
        tmp_path / "customers.csv",
        ["customer_id", "segment", "sku_affinity_json"],
        [["CUST-001", "large", '{"SKU-001": 1.0}']],
    )
    _write_csv(
        tmp_path / "inventory.csv",
        ["sku_id", "warehouse_id", "on_hand", "on_order", "snapshot_date"],
        [["SKU-001", "WH-001", "10", "2", "2026-05-19"]],
    )
    _write_csv(
        tmp_path / "demand_history.csv",
        ["sku_id", "date", "quantity", "is_missing"],
        [["SKU-001", "2025-01-01", "", "True"]],
    )
    _write_csv(
        tmp_path / "supply.csv",
        ["sku_id", "supplier_id", "order_date", "expected_arrival", "quantity", "status"],
        [["SKU-001", "SUP-001", "2026-04-01", "2026-04-07", "10", "delivered"]],
    )
    _write_csv(
        tmp_path / "cost.csv",
        [
            "sku_id",
            "period_start",
            "period_end",
            "cogs",
            "holding_cost",
            "ordering_cost",
            "stockout_cost",
        ],
        [["SKU-001", "2025-01-01", "2025-12-31", "100.50", "10.25", "5.75", "2.50"]],
    )

    conn = FakeConnection()

    summaries = await replace_operational_tables(conn, tmp_path)  # type: ignore[arg-type]

    deletes = [statement for statement in conn.statements if statement.startswith("DELETE")]
    inserts = [
        statement.split()[2] for statement in conn.statements if statement.startswith("INSERT")
    ]

    assert deletes == [
        "DELETE FROM cost",
        "DELETE FROM supply",
        "DELETE FROM demand_history",
        "DELETE FROM inventory",
        "DELETE FROM sku_master",
        "DELETE FROM customers",
    ]
    assert inserts == ["sku_master", "customers", "inventory", "demand_history", "supply", "cost"]
    assert [summary["table_name"] for summary in summaries] == inserts
