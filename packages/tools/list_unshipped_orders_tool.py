"""list_unshipped_orders — T-543

Lists open/allocated customer orders that are past or near their requested_ship_date,
enriched with per-order context: on_hand at the ship-from location and open inbound
supply for the SKU.

No LLM calls. All queries are parameterized and restricted to ALLOWED_READ_TABLES.
Output follows the hybrid tool output contract
(ADR docs/adr/2026-06-10-tool-output-contract-hybrid.md).
"""
from __future__ import annotations

import datetime
import logging
from typing import Any, Literal

from packages.persistence.db import get_pool
from packages.tools._shared import db_error_message
from packages.tools.base import ToolContext, ToolResult

_log = logging.getLogger(__name__)

# Maximum number of order rows returned before truncated=True.
_ROW_CAP = 50

# Open supply order statuses eligible for "inbound supply" context.
_OPEN_SUPPLY_STATUSES = ["pending", "confirmed", "in_transit"]


class ListUnshippedOrdersTool:
    """List open/allocated customer orders past or near their requested_ship_date.

    For each order, returns:
    - Per-order details: order_id, customer_id, sku_id, region, quantity,
      requested_ship_date, days_overdue (negative means not yet past ship date),
      status.
    - on_hand at the ship-from location (latest inventory_snapshot).
    - open_inbound_supply: sum of open supply order quantities for the SKU,
      nearest expected_arrival, and whether any supply is delayed past the
      requested_ship_date.

    Output contract (hybrid):
    - rows capped at 50; truncated=True when total exceeds cap.
    - missing_data: list of messages for orders whose SKU/location lacks an
      inventory_snapshot row.

    Parameters
    ----------
    within_days : int
        Include orders whose requested_ship_date is within this many days in
        the future (default 7). All overdue orders (requested_ship_date < today)
        are always included regardless of this parameter.
    status_filter : list[str]
        Customer order statuses to include (default ["open", "allocated"]).
    """

    name = "list_unshipped_orders"
    description = (
        "List open/allocated customer orders past or near their requested_ship_date, "
        "with per-order inventory context (on_hand at ship-from location) and open "
        "inbound supply for the SKU. Use this for a plain listing of unshipped orders. "
        "For root-cause classification of shipment delays use analyze_shipment_delay_causes."
    )
    safety_level: Literal["read_only", "write", "hitl"] = "read_only"
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "within_days": {
                "type": "integer",
                "minimum": 0,
                "default": 7,
                "description": (
                    "Include orders whose requested_ship_date falls within this many "
                    "days in the future. All overdue orders are always included. Default 7."
                ),
            },
            "status_filter": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Customer order statuses to include; default ['open', 'allocated']"
                ),
            },
        },
        "required": [],
    }
    output_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "order_count": {"type": "integer"},
            "truncated": {"type": "boolean"},
            "missing_data": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Data gaps (e.g. SKU/location lacks an inventory_snapshot row)",
            },
            "orders": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "order_id": {"type": "string"},
                        "customer_id": {"type": "string"},
                        "sku_id": {"type": "string"},
                        "ship_from_location_id": {"type": "string"},
                        "region": {"type": "string"},
                        "quantity": {"type": "integer"},
                        "order_date": {"type": "string"},
                        "requested_ship_date": {"type": "string"},
                        "status": {"type": "string"},
                        "days_overdue": {
                            "type": "integer",
                            "description": (
                                "Positive: days past requested_ship_date; "
                                "negative: days until requested_ship_date"
                            ),
                        },
                        "on_hand_at_ship_from": {
                            "type": ["integer", "null"],
                            "description": (
                                "on_hand from latest inventory_snapshot for this SKU "
                                "at the ship-from location; null if no snapshot exists"
                            ),
                        },
                        "open_inbound_supply": {
                            "type": "object",
                            "description": "Open supply context for the SKU",
                            "properties": {
                                "total_qty": {"type": "number"},
                                "nearest_expected_arrival": {"type": ["string", "null"]},
                                "any_supply_delayed_past_ship_date": {"type": "boolean"},
                            },
                        },
                    },
                },
            },
        },
        "required": ["order_count", "truncated", "missing_data", "orders"],
    }

    def __init__(self, db_session: Any | None = None) -> None:
        pass

    async def handle(self, input: dict[str, Any], ctx: ToolContext) -> ToolResult:  # noqa: A002
        within_days: int = int(input.get("within_days") or 7)
        raw_status = input.get("status_filter")
        status_filter: list[str] = (
            list(raw_status) if raw_status else ["open", "allocated"]
        )

        try:
            order_rows = await _fetch_unshipped_orders(within_days, status_filter)
        except Exception as exc:
            return ToolResult(
                output={"error": db_error_message(exc)},
                audit_payload={
                    "within_days": within_days,
                    "status_filter": status_filter,
                    "order_count": 0,
                },
            )

        truncated = len(order_rows) > _ROW_CAP
        order_rows = order_rows[:_ROW_CAP]

        today = datetime.date.today()
        missing_data: list[str] = []
        orders: list[dict[str, Any]] = []

        for row in order_rows:
            requested_ship_date = _coerce_date(row["requested_ship_date"])
            days_overdue = (today - requested_ship_date).days if requested_ship_date else 0

            on_hand = row.get("on_hand_at_ship_from")
            if on_hand is None:
                missing_data.append(
                    f"no inventory_snapshot for {row['sku_id']} at {row['ship_from_location_id']}"
                )

            # Open inbound supply context
            raw_supply_qty = row.get("open_supply_total_qty")
            supply_qty: float | int | None = (
                float(raw_supply_qty) if raw_supply_qty is not None else None
            )
            open_supply = _build_supply_context(
                supply_qty,
                row.get("nearest_expected_arrival"),
                requested_ship_date,
            )

            orders.append({
                "order_id": row["order_id"],
                "customer_id": row["customer_id"],
                "sku_id": row["sku_id"],
                "ship_from_location_id": row["ship_from_location_id"],
                "region": row["region"],
                "quantity": int(row["quantity"]),
                "order_date": _date_str(row["order_date"]),
                "requested_ship_date": _date_str(requested_ship_date),
                "status": row["status"],
                "days_overdue": days_overdue,
                "on_hand_at_ship_from": int(on_hand) if on_hand is not None else None,
                "open_inbound_supply": open_supply,
            })

        return ToolResult(
            output={
                "order_count": len(orders),
                "truncated": truncated,
                "missing_data": missing_data,
                "orders": orders,
            },
            audit_payload={
                "within_days": within_days,
                "status_filter": status_filter,
                "order_count": len(orders),
                "truncated": truncated,
                "missing_data_count": len(missing_data),
            },
        )


# ---------------------------------------------------------------------------
# Internal query helpers
# ---------------------------------------------------------------------------


def _coerce_date(value: object) -> datetime.date:
    """Convert a DB date/datetime value to datetime.date."""
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    # Fallback: treat as today so days_overdue = 0
    return datetime.date.today()


def _date_str(value: object) -> str:
    if isinstance(value, datetime.datetime):
        return value.date().isoformat()
    if isinstance(value, datetime.date):
        return value.isoformat()
    return str(value) if value is not None else ""


def _build_supply_context(
    total_qty: float | int | None,
    nearest_arrival: object,
    requested_ship_date: datetime.date,
) -> dict[str, Any]:
    qty = float(total_qty) if total_qty is not None else 0.0
    arrival_date: datetime.date | None = None
    if isinstance(nearest_arrival, datetime.datetime):
        arrival_date = nearest_arrival.date()
    elif isinstance(nearest_arrival, datetime.date):
        arrival_date = nearest_arrival

    arrival_str = arrival_date.isoformat() if arrival_date else None
    any_delayed = (arrival_date is not None and arrival_date > requested_ship_date)
    return {
        "total_qty": qty,
        "nearest_expected_arrival": arrival_str,
        "any_supply_delayed_past_ship_date": any_delayed,
    }


async def fetch_unshipped_orders_for_exceptions(
    within_days: int,
    status_filter: list[str],
) -> list[dict[str, Any]]:
    """Public helper: same query as the tool; used by list_today_exceptions screen (e)."""
    return await _fetch_unshipped_orders(within_days, status_filter)


async def _fetch_unshipped_orders(
    within_days: int,
    status_filter: list[str],
) -> list[dict[str, Any]]:
    """Fetch up to _ROW_CAP + 1 rows so the caller can detect truncation.

    Joins:
    - customer_orders (filtered by status and ship date horizon)
    - inventory_snapshot (latest snapshot per SKU/location via MAX snapshot_date)
    - supply_orders (open inbound supply aggregated per SKU)
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                co.order_id,
                co.customer_id,
                co.sku_id,
                co.ship_from_location_id,
                co.region,
                co.quantity,
                co.order_date,
                co.requested_ship_date,
                co.status,
                snap.on_hand                             AS on_hand_at_ship_from,
                sup.total_qty                            AS open_supply_total_qty,
                sup.nearest_expected_arrival
            FROM customer_orders co
            LEFT JOIN LATERAL (
                SELECT on_hand
                FROM inventory_snapshot
                WHERE sku_id = co.sku_id
                  AND warehouse_id = co.ship_from_location_id
                ORDER BY snapshot_date DESC
                LIMIT 1
            ) snap ON TRUE
            LEFT JOIN (
                SELECT
                    sku_id,
                    SUM(quantity)       AS total_qty,
                    MIN(expected_arrival) AS nearest_expected_arrival
                FROM supply_orders
                WHERE status = ANY($3)
                GROUP BY sku_id
            ) sup ON sup.sku_id = co.sku_id
            WHERE co.status = ANY($1)
              AND co.requested_ship_date <= CURRENT_DATE + ($2 * INTERVAL '1 day')
            ORDER BY co.requested_ship_date ASC, co.order_id ASC
            LIMIT 51
            """,
            status_filter,
            within_days,
            _OPEN_SUPPLY_STATUSES,
        )
        return [dict(r) for r in rows]
