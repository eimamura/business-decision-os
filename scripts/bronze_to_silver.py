"""Bronze → Silver transformation pipeline.

Deduplicates and cleans Bronze decisions table.

Usage:
  uv run python scripts/bronze_to_silver.py
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from packages.lakehouse import LakehouseClient
from packages.lakehouse.silver import run_silver


def main() -> int:
    client = LakehouseClient()
    n = run_silver(client)
    result = {"status": "SUCCEEDED", "rows_written": n, "pipeline": "bronze_to_silver"}
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
