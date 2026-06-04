from __future__ import annotations

import json
from typing import Any, Literal

from packages.persistence.db import get_pool
from packages.tools.base import ToolContext, ToolResult


class DemandDriversTool:
    name = "analyze_demand_drivers"
    description = (
        "Identify top customers driving demand for a SKU and assess customer concentration risk"
    )
    safety_level: Literal["read_only", "write", "hitl"] = "read_only"
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "sku_id": {"type": "string"},
            "lookback_days": {"type": "integer", "minimum": 7, "default": 90},
        },
        "required": ["sku_id"],
    }
    output_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "sku_id": {"type": "string"},
            "lookback_days": {"type": "integer"},
            "total_demand": {"type": "number"},
            "top_customers": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "customer_id": {"type": "string"},
                        "segment": {"type": ["string", "null"]},
                        "total_qty": {"type": "number"},
                        "demand_share": {"type": "number"},
                        "avg_daily_qty": {"type": "number"},
                    },
                },
            },
            "customer_concentration": {"type": "number"},
            "sku_risk_level": {"type": "string"},
        },
    }

    def __init__(self, db_session: Any | None = None) -> None:
        pass

    async def handle(self, input: dict[str, Any], ctx: ToolContext) -> ToolResult:
        sku_id: str = input.get("sku_id", "")
        lookback_days: int = int(input.get("lookback_days", 90))

        try:
            total_demand = await _fetch_total_demand(sku_id, lookback_days)
            customer_rows = await _fetch_customer_rows()
        except Exception as exc:
            return ToolResult(
                output={"error": _connection_error_message(exc)},
                audit_payload={
                    "sku_id": sku_id,
                    "lookback_days": lookback_days,
                    "customer_count": 0,
                },
            )

        # Find customers with affinity for this SKU
        matched: list[tuple[str, str | None, float]] = []  # (customer_id, segment, weight)
        for row in customer_rows:
            affinity_raw = row.get("sku_affinity_json")
            if not affinity_raw:
                continue
            affinity = _parse_affinity(affinity_raw)
            if affinity is None:
                continue
            weight = _extract_sku_weight(affinity, sku_id)
            if weight is not None:
                matched.append((row["customer_id"], row.get("segment"), weight))

        if not matched or total_demand == 0.0:
            return ToolResult(
                output={
                    "sku_id": sku_id,
                    "lookback_days": lookback_days,
                    "total_demand": float(total_demand),
                    "top_customers": [],
                    "customer_concentration": 0.0,
                    "sku_risk_level": "low",
                },
                audit_payload={
                    "sku_id": sku_id,
                    "lookback_days": lookback_days,
                    "customer_count": 0,
                },
            )

        # Distribute demand proportionally by affinity weight
        total_weight = sum(w for _, _, w in matched)
        customers: list[dict[str, Any]] = []
        for customer_id, segment, weight in matched:
            share = weight / total_weight if total_weight > 0 else 0.0
            cust_qty = total_demand * share
            customers.append({
                "customer_id": customer_id,
                "segment": segment,
                "total_qty": round(cust_qty, 4),
                "demand_share": round(share, 6),
                "avg_daily_qty": round(cust_qty / lookback_days, 6),
            })

        # Sort by demand_share descending, keep top 5
        customers.sort(key=lambda c: c["demand_share"], reverse=True)
        top_customers = customers[:5]

        # HHI-like concentration score across ALL customers
        customer_concentration = sum(c["demand_share"] ** 2 for c in customers)
        customer_concentration = round(min(1.0, customer_concentration), 6)

        if customer_concentration > 0.5:
            sku_risk_level = "high"
        elif customer_concentration > 0.25:
            sku_risk_level = "medium"
        else:
            sku_risk_level = "low"

        return ToolResult(
            output={
                "sku_id": sku_id,
                "lookback_days": lookback_days,
                "total_demand": float(total_demand),
                "top_customers": top_customers,
                "customer_concentration": customer_concentration,
                "sku_risk_level": sku_risk_level,
            },
            audit_payload={
                "sku_id": sku_id,
                "lookback_days": lookback_days,
                "customer_count": len(top_customers),
            },
        )


async def _fetch_total_demand(sku_id: str, lookback_days: int) -> float:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT COALESCE(SUM(quantity), 0) AS total_qty
            FROM demand_history
            WHERE sku_id = $1
              AND date >= CURRENT_DATE - ($2 * INTERVAL '1 day')
              AND is_missing IS NOT TRUE
            """,
            sku_id,
            lookback_days,
        )
        return float(row["total_qty"]) if row else 0.0


async def _fetch_customer_rows() -> list[dict[str, Any]]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT customer_id, segment, sku_affinity_json
            FROM customer_master
            """
        )
        return [dict(r) for r in rows]


def _parse_affinity(raw: Any) -> dict[str, Any] | list[Any] | None:
    if isinstance(raw, (dict, list)):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, (dict, list)):
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass
    return None


def _extract_sku_weight(affinity: dict[str, Any] | list[Any], sku_id: str) -> float | None:
    """Return affinity weight for sku_id, or None if not found."""
    if isinstance(affinity, dict):
        if sku_id in affinity:
            val = affinity[sku_id]
            try:
                return float(val)
            except (TypeError, ValueError):
                return 1.0
        return None
    if isinstance(affinity, list):
        if sku_id in affinity:
            return 1.0
        return None
    return None


def _connection_error_message(exc: Exception) -> str:
    message = str(exc).lower()
    class_name = exc.__class__.__name__.lower()
    module_name = exc.__class__.__module__.lower()
    if isinstance(exc, RuntimeError) and "database_url" in message:
        return "no database connection"
    if "asyncpg" in module_name and (
        "connection" in class_name
        or "connection" in message
        or "connect call failed" in message
    ):
        return "no database connection"
    return str(exc)
