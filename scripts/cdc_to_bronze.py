"""CDC ingestion: PostgreSQL decisions → Bronze Delta layer.

Runs as a scheduled job (Databricks Jobs in production, cron locally).
Supports --dry-run for CI smoke tests without a live database.

Usage:
  uv run python scripts/cdc_to_bronze.py
  uv run python scripts/cdc_to_bronze.py --dry-run
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from packages.lakehouse import LakehouseClient
from packages.lakehouse.bronze import write_decisions

_SAMPLE_ROWS = [
    {
        "session_id": "00000000-0000-0000-0000-000000000001",
        "user_id": "user-1",
        "goal": "Minimize stockout risk for SKU001",
        "status": "completed",
        "risk_level": "low",
        "auto_execute": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    },
    {
        "session_id": "00000000-0000-0000-0000-000000000002",
        "user_id": "user-1",
        "goal": "Reduce inventory cost by 15%",
        "status": "awaiting_approval",
        "risk_level": "high",
        "auto_execute": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    },
]


def _fetch_from_postgres() -> list[dict]:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required for live CDC ingestion")
    import asyncpg  # type: ignore[import]

    async def _query() -> list[dict]:
        conn = await asyncpg.connect(database_url)
        try:
            rows = await conn.fetch(
                "SELECT id AS session_id, user_id, goal, status, risk_level, created_at "
                "FROM decision_sessions ORDER BY created_at DESC LIMIT 1000"
            )
            return [dict(r) for r in rows]
        finally:
            await conn.close()

    return asyncio.run(_query())


def main(dry_run: bool = False) -> int:
    client = LakehouseClient()
    if dry_run:
        rows = _SAMPLE_ROWS
        print(f"[dry-run] Using {len(rows)} sample rows")
    else:
        rows = _fetch_from_postgres()
        print(f"Fetched {len(rows)} rows from PostgreSQL")

    n = write_decisions(client, rows)
    result = {"status": "SUCCEEDED", "rows_written": n, "dry_run": dry_run}
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CDC ingestion: PostgreSQL → Bronze")
    parser.add_argument("--dry-run", action="store_true", help="Use sample data, skip DB")
    args = parser.parse_args()
    sys.exit(main(dry_run=args.dry_run))
