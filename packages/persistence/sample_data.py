from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable
from uuid import UUID

import asyncpg

SampleValue = str | int | bool | Decimal | date | None


@dataclass(frozen=True)
class ColumnSpec:
    name: str
    parser: Callable[[str], SampleValue]


@dataclass(frozen=True)
class TableSpec:
    name: str
    columns: tuple[ColumnSpec, ...]


def _text(value: str) -> str | None:
    return value or None


def _int(value: str) -> int | None:
    return int(value) if value else None


def _decimal(value: str) -> Decimal | None:
    return Decimal(value) if value else None


def _date(value: str) -> date | None:
    return date.fromisoformat(value) if value else None


def _bool(value: str) -> bool | None:
    if value == "":
        return None
    return value.lower() == "true"


def _jsonb(value: str) -> str | None:
    if not value:
        return None
    return json.dumps(json.loads(value))


TABLES: tuple[TableSpec, ...] = (
    TableSpec(
        "sku_master",
        (
            ColumnSpec("sku_id", _text),
            ColumnSpec("name", _text),
            ColumnSpec("category", _text),
            ColumnSpec("sku_type", _text),
            ColumnSpec("moq", _decimal),
            ColumnSpec("lead_time_days_mean", _decimal),
            ColumnSpec("lead_time_days_std", _decimal),
            ColumnSpec("holding_cost_pct", _decimal),
            ColumnSpec("unit_cost", _decimal),
        ),
    ),
    TableSpec(
        "location_master",
        (
            ColumnSpec("location_id", _text),
            ColumnSpec("name", _text),
            ColumnSpec("region", _text),
            ColumnSpec("country", _text),
            ColumnSpec("location_type", _text),
            ColumnSpec("capacity_units", _decimal),
            ColumnSpec("handling_cost_per_unit", _decimal),
            ColumnSpec("lead_time_to_customer_days", _int),
        ),
    ),
    TableSpec(
        "customer_master",
        (
            ColumnSpec("customer_id", _text),
            ColumnSpec("segment", _text),
            ColumnSpec("sku_affinity_json", _jsonb),
        ),
    ),
    TableSpec(
        "inventory_snapshot",
        (
            ColumnSpec("sku_id", _text),
            ColumnSpec("warehouse_id", _text),
            ColumnSpec("on_hand", _int),
            ColumnSpec("on_order", _int),
            ColumnSpec("snapshot_date", _date),
        ),
    ),
    TableSpec(
        "demand_history",
        (
            ColumnSpec("sku_id", _text),
            ColumnSpec("date", _date),
            ColumnSpec("quantity", _int),
            ColumnSpec("is_missing", _bool),
        ),
    ),
    TableSpec(
        "supply_orders",
        (
            ColumnSpec("sku_id", _text),
            ColumnSpec("supplier_id", _text),
            ColumnSpec("order_date", _date),
            ColumnSpec("expected_arrival", _date),
            ColumnSpec("quantity", _int),
            ColumnSpec("status", _text),
        ),
    ),
    TableSpec(
        "cost_master",
        (
            ColumnSpec("sku_id", _text),
            ColumnSpec("period_start", _date),
            ColumnSpec("period_end", _date),
            ColumnSpec("cogs", _decimal),
            ColumnSpec("holding_cost", _decimal),
            ColumnSpec("ordering_cost", _decimal),
            ColumnSpec("stockout_cost", _decimal),
        ),
    ),
    TableSpec(
        "forecast_history",
        (
            ColumnSpec("sku_id", _text),
            ColumnSpec("forecast_date", _date),
            ColumnSpec("target_date", _date),
            ColumnSpec("forecast_qty", _decimal),
            ColumnSpec("model_version", _text),
        ),
    ),
    TableSpec(
        "customer_orders",
        (
            ColumnSpec("order_id", _text),
            ColumnSpec("customer_id", _text),
            ColumnSpec("sku_id", _text),
            ColumnSpec("ship_from_location_id", _text),
            ColumnSpec("region", _text),
            ColumnSpec("quantity", _int),
            ColumnSpec("order_date", _date),
            ColumnSpec("requested_ship_date", _date),
            ColumnSpec("status", _text),
        ),
    ),
    TableSpec(
        "shipments",
        (
            ColumnSpec("shipment_id", _text),
            ColumnSpec("order_id", _text),
            ColumnSpec("carrier", _text),
            ColumnSpec("planned_ship_date", _date),
            ColumnSpec("actual_ship_date", _date),
            ColumnSpec("planned_delivery_date", _date),
            ColumnSpec("actual_delivery_date", _date),
            ColumnSpec("status", _text),
        ),
    ),
    TableSpec(
        "production_capacity",
        (
            ColumnSpec("location_id", _text),
            ColumnSpec("week_start", _date),
            ColumnSpec("capacity_units", _int),
        ),
    ),
    TableSpec(
        "production_plan",
        (
            ColumnSpec("sku_id", _text),
            ColumnSpec("location_id", _text),
            ColumnSpec("week_start", _date),
            ColumnSpec("planned_qty", _int),
        ),
    ),
)

DELETE_ORDER = (
    "production_plan",
    "production_capacity",
    "shipments",
    "customer_orders",
    "forecast_history",
    "cost_master",
    "supply_orders",
    "demand_history",
    "inventory_snapshot",
    "customer_master",
    "location_master",
    "sku_master",
)
INSERT_ORDER = (
    "sku_master",
    "location_master",
    "customer_master",
    "inventory_snapshot",
    "demand_history",
    "supply_orders",
    "cost_master",
    "forecast_history",
    "customer_orders",
    "shipments",
    "production_capacity",
    "production_plan",
)


def _table_by_name() -> dict[str, TableSpec]:
    return {table.name: table for table in TABLES}


def _read_csv_rows(sample_dir: Path, table: TableSpec) -> list[tuple[SampleValue, ...]]:
    with open(sample_dir / f"{table.name}.csv", newline="") as f:
        reader = csv.DictReader(f)
        return [
            tuple(column.parser(row[column.name]) for column in table.columns)
            for row in reader
        ]


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    return value


def _row_to_dict(row: asyncpg.Record) -> dict[str, Any]:
    return {key: _json_safe(row[key]) for key in row.keys()}


async def replace_operational_tables(
    conn: asyncpg.Connection, sample_dir: Path = Path("data/sample")
) -> list[dict[str, Any]]:
    tables = _table_by_name()
    loaded_rows: dict[str, int] = {}

    async with conn.transaction():
        for table_name in DELETE_ORDER:
            await conn.execute(f"DELETE FROM {table_name}")

        for table_name in INSERT_ORDER:
            table = tables[table_name]
            rows = _read_csv_rows(sample_dir, table)
            if rows:
                columns = ", ".join(column.name for column in table.columns)
                placeholders = ", ".join(f"${idx}" for idx in range(1, len(table.columns) + 1))
                await conn.executemany(
                    f"INSERT INTO {table.name} ({columns}) VALUES ({placeholders})",
                    rows,
                )
            loaded_rows[table.name] = len(rows)

    summaries: list[dict[str, Any]] = []
    for table_name in INSERT_ORDER:
        preview_rows = await conn.fetch(f"SELECT * FROM {table_name} LIMIT 5")
        summaries.append(
            {
                "table_name": table_name,
                "row_count": loaded_rows[table_name],
                "top_rows": [_row_to_dict(row) for row in preview_rows],
            }
        )
    return summaries


async def seed_from_database_url(sample_dir: Path = Path("data/sample")) -> list[dict[str, Any]]:
    raw = os.environ.get("DATABASE_URL")
    if not raw:
        raise RuntimeError("DATABASE_URL not set")
    url = raw.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(url)
    try:
        return await replace_operational_tables(conn, sample_dir)
    finally:
        await conn.close()
