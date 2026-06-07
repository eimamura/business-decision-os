from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from packages.agent.base import AgentBasedSpecialist
from packages.knowledge import SkillLoader
from packages.memory.decision import DecisionMemoryStore
from packages.memory.long_term import LongTermMemoryStore

if TYPE_CHECKING:
    from packages.agent.orchestrator import SpecialistResult, SpecialistTask
    from packages.tools.base import ToolContext

_log = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a cross-domain operational judgment center for supply chain decisions.\n\n"
    "Responsibilities:\n"
    "- Assess stockout risk across demand, inventory, and supply signals\n"
    "- Prioritize exceptions and escalations spanning logistics, finance, and operations\n"
    "- Identify root causes of shipment delays through logistics and supply data\n"
    "- Analyze supply gaps relative to demand forecasts and inventory positions\n"
    "- Recommend prioritized actions that account for cost impact, "
    "lead times, and service levels\n\n"
    "Domains in scope: demand forecasting and trend analysis, inventory positioning and risk,\n"
    "supply order status and lead time, logistics execution and delay diagnosis,\n"
    "and finance impact quantification (holding costs, stockout costs, expedite costs).\n\n"
    "Always ground recommendations in tool results. Do not fabricate quantities or risk scores."
)

_SKILL_HEADER = "\n\n---\n## Analysis Procedures\n\n"
_SKILL_SEPARATOR = "\n\n---\n\n"

_PAST_DECISIONS_HEADER = "\n\n---\n## Past Decisions\n\n"

_DOMAIN_KNOWLEDGE_HEADER = "\n\n---\n## Domain Knowledge\n\n"

# Narrow the tool set per intent so local models aren't overwhelmed by 23+ definitions.
# Fallback: if intent not in map, all control tools remain available.
_INTENT_TOOL_SUBSET: dict[str, list[str]] = {
    "supply_chain": [
        "sql_query",
        "get_delayed_supply_orders",
        "get_open_supply_orders",
        "calculate_supply_gap",
        "analyze_supply_lead_time",
        "calculate_days_of_supply",
        "analyze_supply_risk",
        "calculate_stockout_risk",
        "calculate_stockout_cost_impact",
        "calculate_expedite_cost",
    ],
    "demand": [
        "sql_query",
        "profile_demand_data",
        "analyze_demand_trend",
        "evaluate_forecast_accuracy",
        "detect_demand_anomalies",
        "analyze_seasonality",
        "analyze_demand_drivers",
        "segment_demand",
        "compare_demand_periods",
    ],
    "inventory": [
        "sql_query",
        "calculate_days_of_inventory",
        "calculate_stockout_risk",
        "calculate_excess_inventory_risk",
        "get_available_to_promise",
        "get_open_supply_orders",
    ],
    "finance": [
        "sql_query",
        "calculate_holding_cost_impact",
        "calculate_stockout_cost_impact",
        "calculate_expedite_cost",
        "compare_cost_scenarios",
    ],
}


class ControlAgent(AgentBasedSpecialist):
    _SYSTEM_PROMPT: str = _SYSTEM_PROMPT

    def __init__(
        self,
        llm_client: Any,
        tool_registry: Any,
        sse_queue: Any = None,
        model_registry: Any = None,
    ) -> None:
        super().__init__(
            name="ControlAgent",
            role="control",
            llm_client=llm_client,
            tool_registry=tool_registry,
            sse_queue=sse_queue,
            system_prompt=self._SYSTEM_PROMPT,
            model_registry=model_registry,
        )

    async def run(
        self,
        task: "SpecialistTask",
        ctx: "ToolContext",
        agent_run_id: str = "",
    ) -> "SpecialistResult":
        intent_category: str = (
            (task.context_payload.get("intent") or {}).get("category") or ""
        )

        # T-299 — Pre-call: retrieve past decisions and append to context.
        # session_id is available on ctx; also accept an override from context_payload
        # for forward compatibility with callers that embed it there.
        session_id: str = (
            task.context_payload.get("session_id")
            or str(ctx.session_id)
        )

        # --- Skills block (prepended first, per P40) ---
        skills = SkillLoader().load(intent_category)
        if skills:
            skill_block = _SKILL_HEADER + _SKILL_SEPARATOR.join(skills)
            task = task.model_copy(
                update={"instruction": skill_block + "\n\n" + task.instruction}
            )

        # --- Past Decisions block (appended after skills) ---
        if session_id:
            try:
                past_records = await DecisionMemoryStore().search(
                    json.dumps({"session_id": session_id}),
                    k=3,
                )
                if past_records:
                    decision_lines: list[str] = []
                    for idx, record in enumerate(past_records, start=1):
                        raw_content = record.get("content_json", "")
                        if isinstance(raw_content, str):
                            try:
                                content_repr = json.dumps(json.loads(raw_content))
                            except (json.JSONDecodeError, ValueError):
                                content_repr = raw_content
                        else:
                            content_repr = json.dumps(raw_content)
                        decision_lines.append(f"Decision {idx}: {content_repr}")
                    past_block = _PAST_DECISIONS_HEADER + "\n".join(decision_lines)
                    task = task.model_copy(
                        update={"instruction": task.instruction + past_block}
                    )
            except Exception:
                _log.exception(
                    "DecisionMemoryStore.search failed; continuing without past decisions",
                    extra={"session_id": session_id},
                )

        # --- Domain Knowledge block (from LongTermMemoryStore, by intent scope) ---
        if intent_category:
            try:
                domain_records = await LongTermMemoryStore().search(
                    f"scope:{intent_category}", k=3
                )
                if domain_records:
                    knowledge_lines: list[str] = [
                        r.get("content", "") for r in domain_records if r.get("content")
                    ]
                    if knowledge_lines:
                        knowledge_block = _DOMAIN_KNOWLEDGE_HEADER + "\n\n".join(knowledge_lines)
                        task = task.model_copy(
                            update={"instruction": task.instruction + knowledge_block}
                        )
            except Exception:
                _log.exception(
                    "LongTermMemoryStore.search failed; continuing without domain knowledge",
                    extra={"intent_category": intent_category},
                )

        # --- Narrow allowed tools by intent (helps local models with many tool definitions) ---
        if intent_category and intent_category in _INTENT_TOOL_SUBSET:
            task = task.model_copy(update={"allowed_tools": _INTENT_TOOL_SUBSET[intent_category]})

        # --- Delegate to base runtime ---
        result: "SpecialistResult | None" = None
        try:
            result = await super().run(task, ctx, agent_run_id=agent_run_id)
        except Exception as exc:
            # T-301 — On failure: write failure record to DecisionMemoryStore.
            if session_id:
                try:
                    await DecisionMemoryStore().write({
                        "session_id": session_id,
                        "content_json": {
                            "intent": intent_category,
                            "error": str(exc),
                            "error_type": type(exc).__name__,
                        },
                        "record_type": "failure",
                        "agent_role": "control",
                    })
                except Exception:
                    _log.exception(
                        "DecisionMemoryStore.write (failure record) failed; re-raising original",
                        extra={"session_id": session_id},
                    )
            raise

        # T-300 — Post-call: write decision record to DecisionMemoryStore on success.
        if session_id and result is not None:
            try:
                response_text: str = (result.output.get("text") or "") if result.output else ""
                tool_calls_count: int = len(result.tool_calls_made)
                await DecisionMemoryStore().write({
                    "session_id": session_id,
                    "content_json": {
                        "intent": intent_category,
                        "response_summary": response_text[:500],
                        "tool_calls_count": tool_calls_count,
                    },
                    "record_type": "decision",
                    "agent_role": "control",
                })
            except Exception:
                _log.exception(
                    "DecisionMemoryStore.write (decision record) failed; result is still returned",
                    extra={"session_id": session_id},
                )

        return result
