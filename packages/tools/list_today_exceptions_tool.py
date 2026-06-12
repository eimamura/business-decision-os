"""list_today_exceptions — T-535

Aggregates four existing detector screens into one severity-ranked exception list.

Screens:
  (a) stockout_risk    — critical/high SKUs, shared query logic from list_stockout_risk_tool
  (b) supply_delays    — overdue inbound orders, shared query from supply_delayed_orders_tool
  (c) demand_anomalies — z-score anomalies in the last 7 days (cross-SKU)
  (d) data_quality     — null profiles for all ALLOWED_READ_TABLES

No LLM calls, no new SQL surface. All queries are parameterized and restricted to
ALLOWED_READ_TABLES. Output follows the hybrid tool output contract
(ADR docs/adr/2026-06-10-tool-output-contract-hybrid.md).
"""
from __future__ import annotations

import datetime
import logging
import math
from typing import Any, Literal

from packages.persistence.catalog_repo import get_null_profile
from packages.persistence.db import get_pool
from packages.tools._shared import classify_stockout_risk, db_error_message
from packages.tools.base import ToolContext, ToolResult
from packages.tools.sql_allowlist import ALLOWED_READ_TABLES

_log = logging.getLogger(__name__)

# Maximum number of exception items returned before `truncated` is set to True.
_EXCEPTION_LIMIT = 50

# Stockout-risk horizon for the exceptions screen (7-day operational window).
_STOCKOUT_HORIZON_DAYS = 7

# Only surface stockout risk at high or critical level for daily exception review.
_STOCKOUT_MIN_RISK_LEVELS = {"high", "critical"}

# Z-score threshold for demand anomaly detection in the 7-day window.
_DEMAND_ANOMALY_Z_THRESHOLD = 2.5

# Supply order open-but-not-delivered statuses used by the delayed-orders screen.
_OPEN_STATUSES = ["pending", "confirmed", "in_transit"]

_SEVERITY_ORDER: dict[str, int] = {
    "critical": 4,
    "high": 3,
    "medium": 2,
    "low": 1,
    "info": 0,
}

_STOCKOUT_RISK_ORDER: dict[str, int] = {
    "none": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}


class ListTodayExceptionsTool:
    """Aggregate all operational exceptions into one prioritized list for daily review.

    Composes four screens in a single tool call — stockout risk, delayed inbound supply,
    recent demand anomalies, and data quality issues — so the ControlAgent never needs to
    loop the individual detector tools to answer "What exceptions need my attention today?".
    """

    name = "list_today_exceptions"
    description = (
        "Aggregate all operational exceptions (stockout risk, delayed supply orders, "
        "demand anomalies, data quality issues) into one severity-ranked list for daily review. "
        "Call this once instead of looping list_stockout_risk, get_delayed_supply_orders, "
        "detect_demand_anomalies, and data_quality_checker individually."
    )
    safety_level: Literal["read_only", "write", "hitl"] = "read_only"
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {},
        "required": [],
    }
    output_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "exceptions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "domain": {"type": "string"},
                        "severity": {"type": "string"},
                        "sku_id": {"type": ["string", "null"]},
                        "order_ref": {"type": ["string", "null"]},
                        "headline_metric": {"type": "string"},
                        "detail": {"type": "string"},
                    },
                    "required": ["domain", "severity", "headline_metric", "detail"],
                },
            },
            "counts": {
                "type": "object",
                "description": "Count of exceptions per domain",
                "additionalProperties": {"type": "integer"},
            },
            "truncated": {"type": "boolean"},
            "missing_data": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Data gaps that prevented evaluation (not execution failures)",
            },
        },
        "required": ["exceptions", "counts", "truncated", "missing_data"],
    }

    def __init__(self, db_session: Any | None = None) -> None:
        pass

    async def handle(self, input: dict[str, Any], ctx: ToolContext) -> ToolResult:  # noqa: A002
        all_exceptions: list[dict[str, Any]] = []
        missing_data: list[str] = []

        # ------------------------------------------------------------------ #
        # Screen (a): stockout risk — critical and high SKUs                  #
        # ------------------------------------------------------------------ #
        try:
            stockout_rows = await _fetch_all_stockout_risk(_STOCKOUT_HORIZON_DAYS)
            today = datetime.date.today()
            for row in stockout_rows:
                on_hand_qty = float(row["on_hand_qty"])
                avg_daily = float(row["avg_daily"])
                incoming_supply = float(row["incoming_supply"])
                sku_id: str = row["sku_id"]

                if avg_daily == 0:
                    missing_data.append(f"no demand history in last 30 days: {sku_id}")
                    continue

                demand_forecast = avg_daily * _STOCKOUT_HORIZON_DAYS
                projected_ending_stock = on_hand_qty + incoming_supply - demand_forecast
                risk_level = classify_stockout_risk(projected_ending_stock, demand_forecast)

                if risk_level not in _STOCKOUT_MIN_RISK_LEVELS:
                    continue

                if projected_ending_stock < 0 and avg_daily > 0:
                    days_until_stockout = (on_hand_qty + incoming_supply) / avg_daily
                    stockout_date = today + datetime.timedelta(days=int(days_until_stockout))
                    detail = (
                        f"Projected ending stock {projected_ending_stock:.1f} units; "
                        f"estimated stockout {stockout_date.isoformat()}"
                    )
                else:
                    detail = (
                        f"Projected ending stock {projected_ending_stock:.1f} units "
                        f"vs {demand_forecast:.1f} units {_STOCKOUT_HORIZON_DAYS}-day demand"
                    )

                severity = "critical" if risk_level == "critical" else "high"
                all_exceptions.append({
                    "domain": "stockout_risk",
                    "severity": severity,
                    "sku_id": sku_id,
                    "order_ref": None,
                    "headline_metric": (
                        f"stockout risk {risk_level}: {projected_ending_stock:.0f} units projected"
                    ),
                    "detail": detail,
                })
        except Exception as exc:
            missing_data.append(f"stockout_risk screen unavailable: {db_error_message(exc)}")

        # ------------------------------------------------------------------ #
        # Screen (b): delayed inbound supply orders                           #
        # ------------------------------------------------------------------ #
        try:
            delayed_rows = await _fetch_delayed_orders()
            today = datetime.date.today()
            for row in delayed_rows:
                expected_arrival = row["expected_arrival"]
                if isinstance(expected_arrival, datetime.datetime):
                    expected_arrival_date: datetime.date | None = expected_arrival.date()
                elif isinstance(expected_arrival, datetime.date):
                    expected_arrival_date = expected_arrival
                else:
                    expected_arrival_date = None

                days_overdue: int = (
                    (today - expected_arrival_date).days
                    if expected_arrival_date is not None
                    else 0
                )
                expected_str = (
                    expected_arrival_date.isoformat()
                    if expected_arrival_date is not None
                    else "unknown"
                )

                severity = "critical" if days_overdue >= 7 else "high"
                all_exceptions.append({
                    "domain": "supply_delays",
                    "severity": severity,
                    "sku_id": row["sku_id"],
                    "order_ref": str(row["id"]),
                    "headline_metric": f"{days_overdue} days overdue",
                    "detail": (
                        f"Order {row['id']} for {row['sku_id']} from supplier {row['supplier_id']} "
                        f"expected {expected_str}, status {row['status']}, "
                        f"qty {float(row['quantity']):.0f}"
                    ),
                })
        except Exception as exc:
            missing_data.append(f"supply_delays screen unavailable: {db_error_message(exc)}")

        # ------------------------------------------------------------------ #
        # Screen (c): recent demand anomalies — last 7 days, cross-SKU       #
        # ------------------------------------------------------------------ #
        try:
            anomaly_skus = await _fetch_skus_with_recent_anomalies(lookback_days=7)
            for entry in anomaly_skus:
                sku_id = entry["sku_id"]
                anomaly_type: str = entry["anomaly_type"]
                date_str: str = entry["date"]
                z_score: float | None = entry["z_score"]
                quantity: float | None = entry["quantity"]

                if anomaly_type == "missing":
                    severity = "medium"
                    headline = f"missing demand data on {date_str}"
                elif anomaly_type == "spike":
                    severity = "high"
                    z_label = f"z={z_score:.1f}" if z_score is not None else ""
                    headline = f"demand spike on {date_str} ({z_label})"
                elif anomaly_type == "drop":
                    severity = "high"
                    z_label = f"z={z_score:.1f}" if z_score is not None else ""
                    headline = f"demand drop on {date_str} ({z_label})"
                else:  # stockout
                    severity = "medium"
                    headline = f"zero demand (stockout signal) on {date_str}"

                qty_str = f"{quantity:.0f}" if quantity is not None else "N/A"
                all_exceptions.append({
                    "domain": "demand_anomalies",
                    "severity": severity,
                    "sku_id": sku_id,
                    "order_ref": None,
                    "headline_metric": headline,
                    "detail": (
                        f"SKU {sku_id}: {anomaly_type} anomaly on {date_str}, "
                        f"quantity={qty_str}, "
                        f"z_score={f'{z_score:.2f}' if z_score is not None else 'N/A'}"
                    ),
                })
        except Exception as exc:
            missing_data.append(f"demand_anomalies screen unavailable: {db_error_message(exc)}")

        # ------------------------------------------------------------------ #
        # Screen (d): data quality issues across all operational tables       #
        # ------------------------------------------------------------------ #
        try:
            quality_issues = await _fetch_data_quality_issues()
            for issue in quality_issues:
                all_exceptions.append({
                    "domain": "data_quality",
                    "severity": "medium",
                    "sku_id": None,
                    "order_ref": None,
                    "headline_metric": (
                        f"{issue['null_count']} nulls in "
                        f"{issue['table_name']}.{issue['column_name']} "
                        f"({issue['null_pct']:.1f}%)"
                    ),
                    "detail": (
                        f"Table {issue['table_name']} column {issue['column_name']}: "
                        f"{issue['null_count']} null values out of {issue['total_rows']} rows "
                        f"({issue['null_pct']:.1f}% null)"
                    ),
                })
        except Exception as exc:
            missing_data.append(f"data_quality screen unavailable: {db_error_message(exc)}")

        # ------------------------------------------------------------------ #
        # Sort: critical > high > medium > low > info, then by domain         #
        # ------------------------------------------------------------------ #
        all_exceptions.sort(
            key=lambda x: (
                -_SEVERITY_ORDER.get(x["severity"], 0),
                x["domain"],
            )
        )

        # Cap results and set truncated flag
        truncated = len(all_exceptions) > _EXCEPTION_LIMIT
        capped_exceptions = all_exceptions[:_EXCEPTION_LIMIT]

        # Per-domain counts (before cap)
        counts: dict[str, int] = {}
        for exc_item in all_exceptions:
            domain = exc_item["domain"]
            counts[domain] = counts.get(domain, 0) + 1

        return ToolResult(
            output={
                "exceptions": capped_exceptions,
                "counts": counts,
                "truncated": truncated,
                "missing_data": missing_data,
            },
            audit_payload={
                "total_exceptions": len(all_exceptions),
                "truncated": truncated,
                "counts": counts,
                "missing_data_count": len(missing_data),
            },
        )


# ---------------------------------------------------------------------------
# Internal query helpers (shared logic, no duplication of sibling tools)
# ---------------------------------------------------------------------------


async def _fetch_all_stockout_risk(horizon_days: int) -> list[dict[str, Any]]:
    """Single bulk query shared with list_stockout_risk_tool query path."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                inv.sku_id,
                COALESCE(inv.on_hand_qty, 0)   AS on_hand_qty,
                COALESCE(dh.avg_daily, 0)       AS avg_daily,
                COALESCE(so.incoming_supply, 0) AS incoming_supply
            FROM (
                SELECT sku_id, SUM(on_hand) AS on_hand_qty
                FROM inventory_snapshot
                GROUP BY sku_id
            ) inv
            LEFT JOIN (
                SELECT sku_id, AVG(quantity) AS avg_daily
                FROM demand_history
                WHERE date >= CURRENT_DATE - (30 * INTERVAL '1 day')
                  AND is_missing IS NOT TRUE
                GROUP BY sku_id
            ) dh ON dh.sku_id = inv.sku_id
            LEFT JOIN (
                SELECT sku_id, SUM(quantity) AS incoming_supply
                FROM supply_orders
                WHERE status = ANY($1)
                  AND expected_arrival <= CURRENT_DATE + ($2 * INTERVAL '1 day')
                GROUP BY sku_id
            ) so ON so.sku_id = inv.sku_id
            ORDER BY inv.sku_id
            """,
            _OPEN_STATUSES,
            horizon_days,
        )
        return [dict(r) for r in rows]


async def _fetch_delayed_orders() -> list[dict[str, Any]]:
    """Fetch overdue supply orders — mirrors supply_delayed_orders_tool query."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, sku_id, supplier_id, expected_arrival, quantity, status
            FROM supply_orders
            WHERE expected_arrival < CURRENT_DATE
              AND status != 'delivered'
            ORDER BY expected_arrival ASC
            LIMIT 101
            """,
        )
        return [dict(r) for r in rows]


async def _fetch_skus_with_recent_anomalies(
    lookback_days: int,
) -> list[dict[str, Any]]:
    """Detect demand anomalies across all SKUs for the given lookback window.

    Uses a two-step approach:
    1. Fetch demand rows per SKU for the lookback period.
    2. Apply z-score classification (same logic as DemandAnomalyTool) and
       return only rows that qualify as anomalous.

    Returns a flat list of anomaly records, each with sku_id, anomaly_type, date,
    quantity, and z_score.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Fetch all demand rows for the lookback period in one query.
        rows = await conn.fetch(
            """
            SELECT sku_id, date, quantity, is_missing
            FROM demand_history
            WHERE date >= CURRENT_DATE - ($1 * INTERVAL '1 day')
            ORDER BY sku_id, date
            """,
            lookback_days,
        )

    raw_rows = [dict(r) for r in rows]

    # Group by SKU
    by_sku: dict[str, list[dict[str, Any]]] = {}
    for r in raw_rows:
        by_sku.setdefault(r["sku_id"], []).append(r)

    anomaly_records: list[dict[str, Any]] = []

    for sku_id, sku_rows in by_sku.items():
        if len(sku_rows) < 3:
            # Too few data points to compute statistics — skip (not a data gap for exceptions)
            continue

        non_missing = [
            float(r["quantity"])
            for r in sku_rows
            if not r["is_missing"] and r["quantity"] is not None
        ]

        mean: float = 0.0
        std: float = 0.0
        if non_missing:
            mean = sum(non_missing) / len(non_missing)
            variance = sum((q - mean) ** 2 for q in non_missing) / len(non_missing)
            std = math.sqrt(variance)

        for row in sku_rows:
            is_missing: bool = bool(row["is_missing"])
            quantity: float | None = (
                float(row["quantity"]) if row["quantity"] is not None else None
            )
            row_date = row["date"]
            date_str: str = (
                row_date.isoformat() if hasattr(row_date, "isoformat") else str(row_date)
            )

            if is_missing or quantity is None:
                anomaly_records.append({
                    "sku_id": sku_id,
                    "date": date_str,
                    "quantity": quantity,
                    "z_score": None,
                    "anomaly_type": "missing",
                })
                continue

            z_score: float = (quantity - mean) / std if std > 0 else 0.0

            if z_score > _DEMAND_ANOMALY_Z_THRESHOLD:
                anomaly_type = "spike"
            elif z_score < -_DEMAND_ANOMALY_Z_THRESHOLD:
                anomaly_type = "drop"
            elif quantity == 0:
                anomaly_type = "stockout"
            else:
                continue  # Not anomalous

            anomaly_records.append({
                "sku_id": sku_id,
                "date": date_str,
                "quantity": quantity,
                "z_score": z_score,
                "anomaly_type": anomaly_type,
            })

    return anomaly_records


async def _fetch_data_quality_issues() -> list[dict[str, Any]]:
    """Return columns with null values across all ALLOWED_READ_TABLES.

    Delegates to catalog_repo.get_null_profile() for each table so that all
    null-profile SQL is built in one place (with validated, quoted identifiers)
    and never duplicated or constructed via f-strings here.
    """
    issues: list[dict[str, Any]] = []

    # Sort for deterministic output
    for table_name in sorted(ALLOWED_READ_TABLES):
        profile = await get_null_profile(table_name)
        total_rows = profile["total_rows"]
        if total_rows == 0:
            continue
        for col in profile["columns"]:
            if col["null_count"] > 0:
                issues.append({
                    "table_name": table_name,
                    "column_name": col["column_name"],
                    "null_count": col["null_count"],
                    "null_pct": col["null_pct"],
                    "total_rows": total_rows,
                })

    return issues
