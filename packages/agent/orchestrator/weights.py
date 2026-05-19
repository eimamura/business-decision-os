from __future__ import annotations

import csv
import os
from typing import Any

_CONFIG_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "config")


def _config_path(filename: str) -> str:
    return os.path.normpath(os.path.join(_CONFIG_DIR, filename))


def load_global_weights() -> dict[str, float]:
    path = _config_path("kpi_weights.csv")
    weights: dict[str, float] = {}
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            weights[row["kpi_name"]] = float(row["weight"])
    return weights


def load_sku_overrides() -> dict[str, dict[str, float]]:
    path = _config_path("kpi_weights_overrides.csv")
    overrides: dict[str, dict[str, float]] = {}
    try:
        with open(path, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                sku_type = row["sku_type"]
                kpi_name = row["kpi_name"]
                weight = float(row["weight"])
                if sku_type not in overrides:
                    overrides[sku_type] = {}
                overrides[sku_type][kpi_name] = weight
    except FileNotFoundError:
        pass
    return overrides


def resolve_weights(
    session_goal: Any,
    sku_id: str | None = None,
) -> tuple[dict[str, float], str]:
    if session_goal is not None and hasattr(session_goal, "weight_override_json"):
        override = session_goal.weight_override_json
        if override:
            return dict(override), "session_goal"

    if sku_id is not None:
        sku_overrides = load_sku_overrides()
        for sku_type, weights in sku_overrides.items():
            if sku_id.startswith(sku_type) or sku_type == "critical":
                return dict(weights), "critical_sku"

    global_weights = load_global_weights()
    return global_weights, "default"
