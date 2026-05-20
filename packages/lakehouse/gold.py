from __future__ import annotations

from collections import defaultdict
from typing import Any

from packages.lakehouse import LakehouseClient

GOLD_ANALYTICS_TABLE = "decision_analytics"


def _aggregate(silver_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_user: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in silver_rows:
        by_user[row.get("user_id", "unknown")].append(row)
    result: list[dict[str, Any]] = []
    for user_id, rows in by_user.items():
        risk_levels = [r.get("risk_level", "low") for r in rows]
        result.append({
            "user_id": user_id,
            "total_decisions": len(rows),
            "high_risk_count": sum(1 for r in risk_levels if r == "high"),
            "medium_risk_count": sum(1 for r in risk_levels if r == "medium"),
            "low_risk_count": sum(1 for r in risk_levels if r == "low"),
            "auto_executed_count": sum(1 for r in rows if r.get("auto_execute")),
        })
    return result


def run_gold(client: LakehouseClient) -> int:
    silver_rows = client.read("silver", "decisions_clean")
    gold_rows = _aggregate(silver_rows)
    return client.write("gold", GOLD_ANALYTICS_TABLE, gold_rows)
