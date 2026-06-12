"""analyze_shipment_delay_causes — T-544

Cross-references customer_orders × shipments × inventory_snapshot × supply_orders
and classifies each delayed or unshipped order into root-cause candidates.

## Root-cause classification

### Candidate set
Only orders that are in a "delayed" state enter classification:

  Unshipped candidates (status IN ('open','allocated') AND requested_ship_date < today):
    The order should have shipped but has not.

  Shipped-late candidates (status = 'shipped' AND a shipments row exists):
    A shipments row is required — shipped orders without a shipments row are
    treated as "out of scope" (see KNOWN SEED QUIRK below).

    Shipped late sub-cases:
      (A) actual_ship_date > planned_ship_date  →  warehouse_processing_delay
          (possibly also carrier_delay if also delivered late)
      (B) shipped on time (actual_ship_date <= planned_ship_date) AND
          (actual_delivery_date > planned_delivery_date OR
           status='in_transit' AND today > planned_delivery_date)  →  carrier_delay

### Precedence for unshipped orders
When multiple causes could apply, the following order is used (first match wins):

  1. unknown
     Condition: on_hand snapshot is missing (cannot evaluate stock level).
     The order appears in missing_data.

  2. unknown
     Condition: on_hand at ship-from location >= order quantity
     Reasoning: stock is physically present but the order has not shipped; the
     root cause is not a supply problem, and more investigation is needed.
     The order appears in missing_data.

  3. upstream_supply_delay
     Condition: on_hand < order quantity
                AND an open supply order (pending/confirmed/in_transit) exists
                    for the SKU with expected_arrival > requested_ship_date.
     Reasoning: the SKU's risk is not low stock — inbound supply is coming but
     will arrive too late to rescue the order.

  4. inventory_shortage
     Condition: on_hand < order quantity
                AND no open supply order exists for the SKU at all.
     Reasoning: nothing is on its way; the root cause is an absence of inbound
     supply.

  Note: An open supply order that arrives on or before requested_ship_date is
  not "delayed" — in practice these orders should have already resolved the
  shortage, so the order is treated as unknown (step 2) rather than
  upstream_supply_delay.

### Precedence for shipped orders (have a shipments row)
Shipped-late orders can carry multiple causes simultaneously:

  - warehouse_processing_delay is assigned when actual_ship_date > planned_ship_date.
  - carrier_delay is assigned when the shipment was (or will be) delivered late
    regardless of whether it was also shipped late.
  - Both can co-exist. If both apply, both are listed in the order's `cause` field
    (comma-separated: "warehouse_processing_delay,carrier_delay") and both cause
    counts are incremented.

  A shipped order is only considered "delayed" for this tool if:
    (a) actual_ship_date > planned_ship_date, OR
    (b) actual_delivery_date > planned_delivery_date, OR
    (c) status = 'in_transit' AND today > planned_delivery_date.

### KNOWN SEED QUIRK
Orders with status='shipped' that have NO shipments row are on-time historical
orders added for the P88 demand-shift signal (CO-DS01..CO-DS08). These orders
are NOT flagged as delayed and are NOT listed in missing_data. They are simply
out of scope for this tool's delay classification.

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

# Maximum number of per-order detail rows returned before truncated=True.
_ROW_CAP = 50

# Open supply statuses used when checking inbound supply context.
_OPEN_SUPPLY_STATUSES = ["pending", "confirmed", "in_transit"]


class AnalyzeShipmentDelayCausesTool:
    """Cross-reference orders, shipments, inventory, and supply to classify delay causes.

    Classification precedence is documented in the module docstring.
    No LLM calls — purely deterministic SQL + Python logic.

    Output:
    - per-cause counts (inventory_shortage, upstream_supply_delay,
      warehouse_processing_delay, carrier_delay, unknown)
    - capped order detail list (order_id, customer_id, sku_id, region, cause,
      key evidence numbers)
    - truncated flag
    - missing_data: orders/SKUs where facts were insufficient to classify
    """

    name = "analyze_shipment_delay_causes"
    description = (
        "Cross-reference customer_orders, shipments, inventory_snapshot, and supply_orders "
        "to classify each delayed or unshipped order into root-cause categories: "
        "inventory_shortage, upstream_supply_delay, warehouse_processing_delay, "
        "carrier_delay, or unknown. "
        "Call this once for shipment-delay or unshipped-order root-cause questions. "
        "Do NOT reconstruct causes by hand-joining tables — this tool handles "
        "the cross-domain join and classification internally."
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
            "cause_counts": {
                "type": "object",
                "description": "Count of delayed orders per root cause",
                "properties": {
                    "inventory_shortage": {"type": "integer"},
                    "upstream_supply_delay": {"type": "integer"},
                    "warehouse_processing_delay": {"type": "integer"},
                    "carrier_delay": {"type": "integer"},
                    "unknown": {"type": "integer"},
                },
            },
            "total_delayed": {"type": "integer"},
            "truncated": {"type": "boolean"},
            "missing_data": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Orders classified as unknown due to insufficient data; "
                    "also records SKU/location gaps that prevented inventory classification."
                ),
            },
            "orders": {
                "type": "array",
                "description": "Capped per-order detail records",
                "items": {
                    "type": "object",
                    "properties": {
                        "order_id": {"type": "string"},
                        "customer_id": {"type": "string"},
                        "sku_id": {"type": "string"},
                        "region": {"type": "string"},
                        "status": {"type": "string"},
                        "cause": {
                            "type": "string",
                            "description": (
                                "Root-cause label; comma-separated when multiple apply "
                                "(e.g. 'warehouse_processing_delay,carrier_delay')"
                            ),
                        },
                        "evidence": {
                            "type": "object",
                            "description": "Key numeric evidence for the assigned cause",
                        },
                    },
                },
            },
        },
        "required": ["cause_counts", "total_delayed", "truncated", "missing_data", "orders"],
    }

    def __init__(self, db_session: Any | None = None) -> None:
        pass

    async def handle(self, input: dict[str, Any], ctx: ToolContext) -> ToolResult:  # noqa: A002
        try:
            unshipped_rows = await _fetch_unshipped_delayed()
            shipped_rows = await _fetch_shipped_delayed()
        except Exception as exc:
            return ToolResult(
                output={"error": db_error_message(exc)},
                audit_payload={"total_delayed": 0, "cause_counts": {}},
            )

        today = datetime.date.today()
        missing_data: list[str] = []
        all_classified: list[dict[str, Any]] = []

        # -----------------------------------------------------------------
        # Classify unshipped delayed orders
        # -----------------------------------------------------------------
        for row in unshipped_rows:
            cause, evidence = _classify_unshipped(row, today, missing_data)
            all_classified.append(_build_detail(row, cause, evidence))

        # -----------------------------------------------------------------
        # Classify shipped delayed orders (those with a shipments row)
        # -----------------------------------------------------------------
        for row in shipped_rows:
            cause, evidence = _classify_shipped(row, today)
            all_classified.append(_build_detail(row, cause, evidence))

        # Count causes (a shipped row can have comma-separated multi-cause)
        cause_counts: dict[str, int] = {
            "inventory_shortage": 0,
            "upstream_supply_delay": 0,
            "warehouse_processing_delay": 0,
            "carrier_delay": 0,
            "unknown": 0,
        }
        for record in all_classified:
            for cause_part in record["cause"].split(","):
                key = cause_part.strip()
                if key in cause_counts:
                    cause_counts[key] += 1

        total_delayed = len(all_classified)
        truncated = total_delayed > _ROW_CAP
        capped_orders = all_classified[:_ROW_CAP]

        return ToolResult(
            output={
                "cause_counts": cause_counts,
                "total_delayed": total_delayed,
                "truncated": truncated,
                "missing_data": missing_data,
                "orders": capped_orders,
            },
            audit_payload={
                "total_delayed": total_delayed,
                "cause_counts": cause_counts,
                "truncated": truncated,
                "missing_data_count": len(missing_data),
            },
        )


# ---------------------------------------------------------------------------
# Classification helpers
# ---------------------------------------------------------------------------


def _coerce_date(value: object) -> datetime.date | None:
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    return None


def _date_str(value: object) -> str | None:
    d = _coerce_date(value)
    return d.isoformat() if d else None


def _classify_unshipped(
    row: dict[str, Any],
    today: datetime.date,
    missing_data: list[str],
) -> tuple[str, dict[str, Any]]:
    """Classify an unshipped delayed order.

    Precedence (first match wins):
      1. unknown               — no inventory snapshot (cannot evaluate stock level)
      2. unknown               — on_hand >= quantity (stock present but unshipped;
                                 needs investigation)
      3. upstream_supply_delay — on_hand < quantity AND open supply exists with arrival > ship date
      4. inventory_shortage    — on_hand < quantity AND no open supply order at all
    """
    order_id: str = row["order_id"]
    quantity: int = int(row["quantity"])
    requested_ship_date: datetime.date | None = _coerce_date(row["requested_ship_date"])
    on_hand: int | None = row.get("on_hand_at_ship_from")
    open_supply_qty: float = float(row.get("open_supply_total_qty") or 0)
    nearest_arrival: datetime.date | None = _coerce_date(row.get("nearest_expected_arrival"))

    # Precedence 1: no inventory snapshot → unknown (cannot evaluate stock level)
    if on_hand is None:
        missing_data.append(
            f"no inventory_snapshot for {row['sku_id']} at "
            f"{row['ship_from_location_id']} (order {order_id})"
        )
        missing_data.append(
            f"order {order_id} unshipped but facts insufficient for classification "
            f"(on_hand=N/A, open_supply_qty={open_supply_qty:.0f})"
        )
        return "unknown", {
            "on_hand": None,
            "order_quantity": quantity,
            "open_inbound_supply_qty": open_supply_qty,
        }

    # Precedence 2: sufficient stock but order not shipped → unknown (not a supply problem)
    if on_hand >= quantity:
        missing_data.append(
            f"order {order_id} overdue but on_hand ({on_hand}) >= quantity ({quantity}); "
            "cause cannot be determined from supply data"
        )
        return "unknown", {
            "on_hand": on_hand,
            "order_quantity": quantity,
            "shortfall": 0,
            "open_inbound_supply_qty": open_supply_qty,
        }

    # on_hand < quantity from here on
    # Precedence 3: upstream_supply_delay — open supply exists with arrival after ship date
    supply_late = (
        open_supply_qty > 0
        and nearest_arrival is not None
        and (requested_ship_date is None or nearest_arrival > requested_ship_date)
    )
    if supply_late:
        return "upstream_supply_delay", {
            "on_hand": on_hand,
            "order_quantity": quantity,
            "shortfall": quantity - on_hand,
            "open_inbound_supply_qty": open_supply_qty,
            "nearest_supply_arrival": _date_str(nearest_arrival),
            "requested_ship_date": _date_str(requested_ship_date),
            "supply_arrival_delay_days": (
                (nearest_arrival - requested_ship_date).days
                if requested_ship_date and nearest_arrival else None
            ),
        }

    # Precedence 4: inventory_shortage — on_hand < quantity AND no open supply at all
    return "inventory_shortage", {
        "on_hand": on_hand,
        "order_quantity": quantity,
        "shortfall": quantity - on_hand,
        "open_inbound_supply_qty": open_supply_qty,
        "nearest_supply_arrival": _date_str(nearest_arrival),
    }


def _classify_shipped(
    row: dict[str, Any],
    today: datetime.date,
) -> tuple[str, dict[str, Any]]:
    """Classify a shipped order that has a shipments row.

    A shipped order can have multiple causes (warehouse + carrier).
    Returns a comma-separated cause string and combined evidence.

    Warehouse processing delay:
      actual_ship_date > planned_ship_date

    Carrier delay:
      actual_delivery_date > planned_delivery_date, OR
      status = 'in_transit' AND today > planned_delivery_date
    """
    planned_ship = _coerce_date(row.get("planned_ship_date"))
    actual_ship = _coerce_date(row.get("actual_ship_date"))
    planned_delivery = _coerce_date(row.get("planned_delivery_date"))
    actual_delivery = _coerce_date(row.get("actual_delivery_date"))
    shipment_status: str = str(row.get("shipment_status") or "")

    causes: list[str] = []
    evidence: dict[str, Any] = {
        "planned_ship_date": _date_str(planned_ship),
        "actual_ship_date": _date_str(actual_ship),
        "planned_delivery_date": _date_str(planned_delivery),
        "actual_delivery_date": _date_str(actual_delivery),
    }

    # Warehouse processing delay
    if planned_ship and actual_ship and actual_ship > planned_ship:
        causes.append("warehouse_processing_delay")
        evidence["ship_delay_days"] = (actual_ship - planned_ship).days

    # Carrier delay
    carrier_late = False
    if actual_delivery and planned_delivery and actual_delivery > planned_delivery:
        carrier_late = True
        evidence["delivery_delay_days"] = (actual_delivery - planned_delivery).days
    elif shipment_status == "in_transit" and planned_delivery and today > planned_delivery:
        carrier_late = True
        evidence["days_past_planned_delivery"] = (today - planned_delivery).days
    if carrier_late:
        causes.append("carrier_delay")

    if not causes:
        causes.append("unknown")

    return ",".join(causes), evidence


def _build_detail(row: dict[str, Any], cause: str, evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "order_id": row["order_id"],
        "customer_id": row["customer_id"],
        "sku_id": row["sku_id"],
        "region": row["region"],
        "status": row["status"],
        "cause": cause,
        "evidence": evidence,
    }


# ---------------------------------------------------------------------------
# Internal query helpers
# ---------------------------------------------------------------------------


async def _fetch_unshipped_delayed() -> list[dict[str, Any]]:
    """Fetch open/allocated orders whose requested_ship_date is in the past.

    Includes on_hand at the ship-from location (latest snapshot) and open
    inbound supply aggregated per SKU.
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
                    SUM(quantity)         AS total_qty,
                    MIN(expected_arrival) AS nearest_expected_arrival
                FROM supply_orders
                WHERE status = ANY($1)
                GROUP BY sku_id
            ) sup ON sup.sku_id = co.sku_id
            WHERE co.status IN ('open', 'allocated')
              AND co.requested_ship_date < CURRENT_DATE
            ORDER BY co.requested_ship_date ASC, co.order_id ASC
            """,
            _OPEN_SUPPLY_STATUSES,
        )
        return [dict(r) for r in rows]


async def _fetch_shipped_delayed() -> list[dict[str, Any]]:
    """Fetch shipped orders that have a shipments row and are delayed.

    Delayed = actual_ship_date > planned_ship_date (warehouse delay)
           OR actual_delivery_date > planned_delivery_date (carrier delay)
           OR in_transit past planned_delivery_date (carrier delay in progress).

    KNOWN SEED QUIRK: orders with status='shipped' that have NO shipments row
    (CO-DS01..CO-DS08) are intentionally excluded by the INNER JOIN on shipments.
    These are on-time historical demand-shift orders for P88; they should not be
    flagged as delayed.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                co.order_id,
                co.customer_id,
                co.sku_id,
                co.region,
                co.status,
                sh.planned_ship_date,
                sh.actual_ship_date,
                sh.planned_delivery_date,
                sh.actual_delivery_date,
                sh.status                               AS shipment_status
            FROM customer_orders co
            INNER JOIN shipments sh ON sh.order_id = co.order_id
            WHERE co.status = 'shipped'
              AND (
                (sh.actual_ship_date IS NOT NULL AND sh.actual_ship_date > sh.planned_ship_date)
                OR (sh.actual_delivery_date IS NOT NULL
                    AND sh.actual_delivery_date > sh.planned_delivery_date)
                OR (sh.status = 'in_transit' AND sh.planned_delivery_date < CURRENT_DATE)
              )
            ORDER BY co.order_id ASC
            """
        )
        return [dict(r) for r in rows]
