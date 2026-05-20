"""Silver → Gold aggregation pipeline.

Aggregates cleaned decisions into analytics-ready summaries.

Usage:
  uv run python scripts/silver_to_gold.py
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from packages.lakehouse import LakehouseClient
from packages.lakehouse.gold import run_gold


def main() -> int:
    client = LakehouseClient()
    n = run_gold(client)
    result = {"status": "SUCCEEDED", "rows_written": n, "pipeline": "silver_to_gold"}
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
