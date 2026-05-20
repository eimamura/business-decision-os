from __future__ import annotations

from typing import Any

from packages.lakehouse import LakehouseClient
from packages.lakehouse.bronze import read_decisions

SILVER_DECISIONS_TABLE = "decisions_clean"


def transform_decisions(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    clean: list[dict[str, Any]] = []
    for row in rows:
        key = row.get("session_id", "") + str(row.get("created_at", ""))
        if key in seen:
            continue
        seen.add(key)
        clean.append({k: v for k, v in row.items() if v is not None})
    return clean


def run_silver(client: LakehouseClient) -> int:
    bronze_rows = read_decisions(client)
    silver_rows = transform_decisions(bronze_rows)
    return client.write("silver", SILVER_DECISIONS_TABLE, silver_rows)
