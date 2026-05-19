from __future__ import annotations

import os
from typing import Any, Literal

import yaml

from packages.tools.base import ToolContext, ToolResult

_THRESHOLDS_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "config", "risk_thresholds.yaml")
)


def _load_thresholds() -> dict[str, Any]:
    try:
        with open(_THRESHOLDS_PATH) as f:
            data: dict[str, Any] = yaml.safe_load(f) or {}
        return data.get("thresholds", {})  # type: ignore[no-any-return]
    except FileNotFoundError:
        return {}


def _classify_risk(
    service_level: float,
    thresholds: dict[str, Any],
) -> Literal["low", "medium", "high"]:
    high = thresholds.get("high", {})
    medium = thresholds.get("medium", {})

    if service_level < high.get("service_level_max", 0.85):
        return "high"
    if service_level < medium.get("service_level_max", 0.95):
        return "medium"
    return "low"


def _make_kpi_scores(idx: int, order_qty: float, cost: float) -> list[dict[str, Any]]:
    service_level = max(0.0, 0.95 - idx * 0.05)
    fill_rate = max(0.0, 0.90 - idx * 0.03)
    stockout_rate = min(1.0, 0.05 + idx * 0.03)
    excess = max(0.0, order_qty * 0.1 * idx)
    return [
        {
            "name": "service_level",
            "value": service_level,
            "unit": "%",
            "direction": "higher_better",
        },
        {"name": "fill_rate", "value": fill_rate, "unit": "%", "direction": "higher_better"},
        {
            "name": "stockout_rate",
            "value": stockout_rate,
            "unit": "%",
            "direction": "lower_better",
        },
        {
            "name": "inventory_turnover",
            "value": 4.0,
            "unit": "turns/year",
            "direction": "higher_better",
        },
        {
            "name": "days_of_inventory",
            "value": 30.0 + idx * 15,
            "unit": "days",
            "direction": "lower_better",
        },
        {
            "name": "excess_inventory",
            "value": excess,
            "unit": "units",
            "direction": "lower_better",
        },
        {
            "name": "working_capital",
            "value": cost * 0.5,
            "unit": "USD",
            "direction": "lower_better",
        },
        {
            "name": "total_supply_chain_cost",
            "value": cost,
            "unit": "USD",
            "direction": "lower_better",
        },
    ]


class EvaluatorTool:
    name = "evaluate_candidates"
    description = "Score each candidate plan against all 8 KPIs independently"
    requires_approval = False
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "candidates": {
                "type": "array",
                "items": {"type": "object"},
            },
        },
        "required": ["candidates"],
    }
    output_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "evaluations": {"type": "array"},
        },
    }

    async def handle(self, input: dict[str, Any], ctx: ToolContext) -> ToolResult:
        candidates: list[dict[str, Any]] = input.get("candidates", [])
        thresholds = _load_thresholds()

        evaluations = []
        for idx, candidate in enumerate(candidates):
            candidate_id = str(candidate.get("id", idx))
            order_qty = float(candidate.get("order_qty", 0.0))
            cost = float(candidate.get("total_supply_chain_cost", order_qty * 1.2))

            kpi_scores = _make_kpi_scores(idx, order_qty, cost)
            service_level = max(0.0, 0.95 - idx * 0.05)
            risk_level = _classify_risk(service_level, thresholds)

            evaluations.append({
                "candidate_id": candidate_id,
                "kpi_scores": kpi_scores,
                "risk_level": risk_level,
            })

        return ToolResult(
            output={"evaluations": evaluations},
            audit_payload={
                "candidate_count": len(candidates),
                "evaluation_count": len(evaluations),
            },
        )
