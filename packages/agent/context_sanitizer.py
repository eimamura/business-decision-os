from __future__ import annotations

import json
from typing import Any


def sanitize_sql_results(rows: list[dict[str, Any]], max_rows: int = 50) -> dict[str, Any]:
    total_count = len(rows)
    sample = rows[:max_rows]
    truncated = total_count > max_rows

    if not sample:
        return {
            "rows": [],
            "row_count": 0,
            "truncated": False,
            "columns": [],
        }

    columns = list(sample[0].keys())
    result: dict[str, Any] = {
        "rows": sample,
        "row_count": total_count,
        "truncated": truncated,
        "columns": columns,
    }

    if truncated:
        aggregates: dict[str, dict[str, Any]] = {}
        for col in columns:
            numeric_vals: list[float] = []
            for row in sample:
                val = row.get(col)
                if val is not None:
                    try:
                        numeric_vals.append(float(val))
                    except (TypeError, ValueError):
                        pass
            if numeric_vals:
                aggregates[col] = {
                    "mean": round(sum(numeric_vals) / len(numeric_vals), 4),
                    "min": round(min(numeric_vals), 4),
                    "max": round(max(numeric_vals), 4),
                }
        if aggregates:
            result["sample_aggregates"] = aggregates

    return result


def sanitize_for_llm(data: dict[str, Any]) -> str:
    return json.dumps(data, default=str)
