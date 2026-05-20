"""Lakehouse CLI — local equivalent of 'az databricks workspace show'.

Usage:
  python -m packages.lakehouse.cli status
  python -m packages.lakehouse.cli run-silver
  python -m packages.lakehouse.cli run-gold
"""
from __future__ import annotations

import json
import sys

from packages.lakehouse import LakehouseClient
from packages.lakehouse.gold import run_gold
from packages.lakehouse.silver import run_silver


def cmd_status() -> int:
    client = LakehouseClient()
    layers = [
        ("bronze", "decisions"),
        ("silver", "decisions_clean"),
        ("gold", "decision_analytics"),
    ]
    report: dict[str, object] = {
        "workspace": "local-dev",
        "region": "local",
        "provisioned": True,
        "tables": {},
    }
    all_exist = True
    tables: dict[str, object] = {}
    for layer, table in layers:
        exists = client.table_exists(layer, table)
        status = client.job_status(layer, table)
        tables[f"{layer}.{table}"] = {
            "exists": exists,
            "last_status": status.get("status", "NOT_STARTED"),
            "last_run": status.get("last_run"),
        }
        if not exists:
            all_exist = False
    report["tables"] = tables
    report["all_tables_provisioned"] = all_exist
    print(json.dumps(report, indent=2))
    return 0 if all_exist else 1


def cmd_run_silver() -> int:
    client = LakehouseClient()
    n = run_silver(client)
    print(json.dumps({"status": "SUCCEEDED", "rows_written": n}))
    return 0


def cmd_run_gold() -> int:
    client = LakehouseClient()
    n = run_gold(client)
    print(json.dumps({"status": "SUCCEEDED", "rows_written": n}))
    return 0


def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else "status"
    dispatch = {
        "status": cmd_status,
        "run-silver": cmd_run_silver,
        "run-gold": cmd_run_gold,
    }
    fn = dispatch.get(command)
    if fn is None:
        print(f"Unknown command: {command}", file=sys.stderr)
        sys.exit(1)
    sys.exit(fn())


if __name__ == "__main__":
    main()
