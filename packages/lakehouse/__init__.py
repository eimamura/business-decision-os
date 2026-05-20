from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_DEFAULT_BASE = Path(
    os.environ.get("LAKEHOUSE_PATH", "data/lakehouse")
)


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class LakehouseClient:
    """File-based local Lakehouse client (Bronze → Silver → Gold).

    Production: replace with Databricks SDK calls.
    Local dev: reads/writes newline-delimited JSON in LAKEHOUSE_PATH.
    """

    def __init__(self, base_path: Path | None = None) -> None:
        self._base = base_path or _DEFAULT_BASE

    def _table_path(self, layer: str, table: str) -> Path:
        return self._base / layer / table

    def _status_path(self, layer: str, table: str) -> Path:
        return self._table_path(layer, table) / "_status.json"

    def write(self, layer: str, table: str, rows: list[dict[str, Any]]) -> int:
        import uuid as _uuid
        table_dir = self._table_path(layer, table)
        table_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')
        part_file = table_dir / f"part-{ts}-{_uuid.uuid4().hex[:8]}.jsonl"
        with part_file.open("w") as fh:
            for row in rows:
                fh.write(json.dumps(row) + "\n")
        self._write_status(layer, table, len(rows))
        return len(rows)

    def read(self, layer: str, table: str) -> list[dict[str, Any]]:
        table_dir = self._table_path(layer, table)
        if not table_dir.exists():
            return []
        rows: list[dict[str, Any]] = []
        for part in sorted(table_dir.glob("part-*.jsonl")):
            with part.open() as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        rows.append(json.loads(line))
        return rows

    def table_exists(self, layer: str, table: str) -> bool:
        table_dir = self._table_path(layer, table)
        return table_dir.exists() and any(table_dir.glob("part-*.jsonl"))

    def _write_status(self, layer: str, table: str, rows_written: int) -> None:
        status_path = self._status_path(layer, table)
        status: dict[str, Any] = {
            "table": table,
            "layer": layer,
            "last_run": _iso_now(),
            "status": "SUCCEEDED",
            "rows_written": rows_written,
        }
        with status_path.open("w") as fh:
            json.dump(status, fh)

    def job_status(self, layer: str, table: str) -> dict[str, Any]:
        status_path = self._status_path(layer, table)
        if not status_path.exists():
            return {"status": "NOT_STARTED", "table": table, "layer": layer}
        with status_path.open() as fh:
            return json.load(fh)  # type: ignore[no-any-return]
