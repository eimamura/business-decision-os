from __future__ import annotations

from typing import Any

from packages.lakehouse import LakehouseClient

BRONZE_DECISIONS_TABLE = "decisions"
BRONZE_RECOMMENDATIONS_TABLE = "recommendations"
BRONZE_APPROVALS_TABLE = "approvals"


def write_decisions(client: LakehouseClient, rows: list[dict[str, Any]]) -> int:
    return client.write("bronze", BRONZE_DECISIONS_TABLE, rows)


def write_recommendations(client: LakehouseClient, rows: list[dict[str, Any]]) -> int:
    return client.write("bronze", BRONZE_RECOMMENDATIONS_TABLE, rows)


def write_approvals(client: LakehouseClient, rows: list[dict[str, Any]]) -> int:
    return client.write("bronze", BRONZE_APPROVALS_TABLE, rows)


def read_decisions(client: LakehouseClient) -> list[dict[str, Any]]:
    return client.read("bronze", BRONZE_DECISIONS_TABLE)
