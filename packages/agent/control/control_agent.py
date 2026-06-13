from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from packages.agent.base import AgentBasedSpecialist
from packages.knowledge import SkillLoader
from packages.memory.decision import DecisionMemoryStore
from packages.memory.long_term import LongTermMemoryStore
from packages.tools.schema_context import get_schema_context

if TYPE_CHECKING:
    from packages.agent.orchestrator import SpecialistResult, SpecialistTask
    from packages.tools.base import ToolContext

_log = logging.getLogger(__name__)

# Template for the system prompt.  The {schema_example} placeholder is replaced
# at prompt-assembly time via _build_system_prompt().  When schema context is not
# yet loaded (e.g. at import time before the DB is ready) the placeholder is
# replaced with an empty string so the prompt degrades gracefully.
_SYSTEM_PROMPT_TEMPLATE = (
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
    "Tool usage priority (follow this order):\n"
    "1. For questions about today's exceptions, what needs attention today, or what requires "
    "human judgment today — call `list_today_exceptions` ONCE. "
    "Do NOT loop list_stockout_risk, get_delayed_supply_orders, detect_demand_anomalies, "
    "and data_quality_checker separately to assemble the same picture.\n"
    "2. To enumerate stockout risk across all SKUs (non-exception context), call "
    "`list_stockout_risk(horizon_days=7)` once — do NOT loop `calculate_stockout_risk` per SKU.\n"
    "2b. For questions about supply shortages next week or next month "
    "(e.g. 'which products may face supply shortages', 'supply gap over the next 30 days') "
    "— DO NOT use `list_stockout_risk` (that tool measures on-hand stockout risk only, "
    "NOT forward supply adequacy). "
    "Call `nl_query` EXACTLY ONCE — do NOT call nl_query a second time after the first result. "
    "The nl_query must use CORRELATED SUBQUERIES (not JOINs) for each metric. "
    "{schema_example}"
    "After nl_query returns, synthesize immediately into your final answer — do NOT call "
    "any tool again. "
    "`calculate_supply_gap` is for SINGLE-SKU deep-dive (requires sku_id parameter).\n"
    "3. Use a specialized tool (e.g. calculate_stockout_risk, calculate_days_of_inventory) "
    "when it directly covers a single-SKU question, including days-of-cover "
    "and when-do-we-run-out analysis.\n"
    "4. For shipment-delay or unshipped-order root-cause questions — call "
    "`analyze_shipment_delay_causes` ONCE. "
    "Do NOT reconstruct causes by hand-joining raw tables yourself. "
    "For a plain listing of unshipped orders (without root-cause analysis) call "
    "`list_unshipped_orders` ONCE.\n"
    "5. For demand-shift questions by customer or region — call `detect_demand_shift` ONCE. "
    "segment_demand and compare_demand_periods are SKU-axis tools (consumption series); "
    "they do NOT answer customer/region demand questions. "
    "Customer/region demand questions (SPEC Q9) are answered from order transaction data, "
    "not from the consumption series. The consumption series is for forecast/stockout "
    "tools only.\n"
    "6. For forecast-vs-actual gap questions (SPEC Q5) — why is actual demand deviating "
    "from the forecast, over-forecast/under-forecast analysis — call "
    "`analyze_forecast_deviation` ONCE. "
    "`evaluate_forecast_accuracy` is the model-quality axis (MAPE/bias); "
    "pair with `detect_demand_shift` when the user asks which customer/region drives the gap.\n"
    "7. For production plan adjustment questions (SPEC Q7) — which products need production "
    "plan changes, overproduction/underproduction analysis — call "
    "`analyze_production_plan_gap` ONCE. "
    "Do NOT reconstruct plan-vs-demand gaps by hand-joining production and demand tables yourself.\n"
    "8. For biggest-constraint or bottleneck-impact questions (SPEC Q10) — "
    "call `identify_binding_constraint` ONCE. "
    "Do NOT separately evaluate capacity, supply-gap, and stockout risks "
    "by assembling your own ranking from individual tool results.\n"
    "9. For purchase-earlier/later or order-timing questions (SPEC Q8) — "
    "call `analyze_supply_order_timing` ONCE. "
    "`get_delayed_supply_orders` answers 'what is already late by status'; "
    "`analyze_supply_order_timing` answers 'which orders should arrive sooner or later'.\n"
    "10. Use nl_query for bulk or cross-product questions — pass the question in plain English; "
    "nl_query generates schema-correct SQL internally.\n"
    "11. Never fabricate column names or assume columns that are not confirmed by tool results.\n\n"
    "Always ground recommendations in tool results. Do not fabricate quantities or risk scores.\n"
    "Once you have sufficient data from tools, stop calling tools"
    " and produce a final text response.\n"
    "Never call the same tool twice in one analysis pass. "
    "If you have not yet called any tool in this pass, you MUST call the appropriate tool "
    "before answering — never produce a final answer without tool data. "
    "After receiving results from list_stockout_risk, synthesise them immediately"
    " into a final answer — do NOT call list_stockout_risk or any other tool again"
    " in the same pass.\n"
    "For exception/delay questions, call list_today_exceptions to surface the full daily"
    " exception picture in one call.\n"
    "12. For heavy or long-running work — call `job_dispatch` with the appropriate job_type"
    " and await human approval before execution begins."
    " This is MANDATORY; never run these inline.\n"
    "    Trigger phrases that ALWAYS route to job_dispatch:\n"
    "    - 'as a background job', 'run in the background', 'notify me when it completes'\n"
    "    - 'train the forecast model', 'train_forecast'\n"
    "    - 'run a full ... simulation for all SKUs'\n"
    "    Job type mapping: train_forecast → job_type='train_forecast';"
    " inventory simulation → job_type='simulate';"
    " replenishment optimization → job_type='optimize';"
    " demand forecast → job_type='forecast'.\n"
    "\n"
    "## Response Format\n\n"
    "Structure every response using the following four sections:\n\n"
    "**Situation:** [summary of what the data shows]\n"
    "**Root Cause:** [identified cause(s) with data evidence]\n"
    "**Recommended Actions:**\n"
    "1. [action] — [data rationale]\n"
    "2. ...\n"
    "**Confidence Level:** [High / Medium / Low] — [one sentence justification]\n"
    "\n"
    "When past decisions are annotated with [user feedback: negative], treat those approaches"
    " as ineffective and avoid repeating them in your current response.\n"
)


def _make_schema_example() -> str:
    """Build a correlated-subquery SQL example from live schema context.

    Returns an empty string when schema context has not yet been loaded (i.e.
    before API startup calls load_schema_context()).  This keeps the prompt
    valid at import time without requiring a DB connection.
    """
    schema = get_schema_context()
    if not schema:
        return ""

    # Parse the schema context lines to find relevant tables and their columns.
    # Format emitted by load_schema_context(): "table_name(col1 TYPE, col2 TYPE, ...)"
    table_cols: dict[str, list[str]] = {}
    for line in schema.splitlines():
        if "(" not in line or line.startswith("Join rule") or line.startswith("IMPORTANT"):
            continue
        table_name = line[: line.index("(")]
        cols_part = line[line.index("(") + 1 : line.rindex(")")]
        col_names = [c.split()[0] for c in cols_part.split(",") if c.strip()]
        table_cols[table_name] = col_names

    # Identify the SKU master table (expected: sku_master) and correlated tables.
    sku_table = "sku_master" if "sku_master" in table_cols else None
    demand_table = "demand_history" if "demand_history" in table_cols else None
    inventory_table = "inventory_snapshot" if "inventory_snapshot" in table_cols else None
    supply_table = "supply_orders" if "supply_orders" in table_cols else None

    if not all([sku_table, demand_table, inventory_table, supply_table]):
        # Required tables not present in current schema context — omit example.
        return ""

    # Find sku_id column and a numeric metric column in demand table.
    demand_cols = table_cols[demand_table]  # type: ignore[index]
    demand_qty_col = next(
        (c for c in demand_cols if c.lower() in ("quantity", "qty", "demand_qty")),
        demand_cols[1] if len(demand_cols) > 1 else demand_cols[0],
    )

    inventory_cols = table_cols[inventory_table]  # type: ignore[index]
    inventory_qty_col = next(
        (c for c in inventory_cols if c.lower() in ("on_hand", "quantity", "qty", "stock_qty")),
        inventory_cols[1] if len(inventory_cols) > 1 else inventory_cols[0],
    )

    supply_cols = table_cols[supply_table]  # type: ignore[index]
    supply_qty_col = next(
        (c for c in supply_cols if c.lower() in ("quantity", "qty", "order_qty")),
        supply_cols[1] if len(supply_cols) > 1 else supply_cols[0],
    )

    example = (
        f"Example: SELECT m.sku_id, "
        f"(SELECT AVG(d.{demand_qty_col}) FROM {demand_table} d"
        f" WHERE d.sku_id=m.sku_id)*30 AS demand_30d, "
        f"(SELECT SUM(i.{inventory_qty_col}) FROM {inventory_table} i"
        f" WHERE i.sku_id=m.sku_id) AS on_hand, "
        f"(SELECT COALESCE(SUM(o.{supply_qty_col}),0) FROM {supply_table} o"
        f" WHERE o.sku_id=m.sku_id"
        f" AND o.status IN ('pending','confirmed','in_transit')"
        f" AND o.expected_arrival<=CURRENT_DATE+INTERVAL '30 days') AS incoming"
        f" FROM {sku_table} m WHERE ... ORDER BY gap DESC. "
    )
    return example


def _build_system_prompt() -> str:
    """Assemble the system prompt, injecting a dynamic schema example if available."""
    schema_example = _make_schema_example()
    return _SYSTEM_PROMPT_TEMPLATE.format(schema_example=schema_example)


# Module-level constant preserved for backward compatibility (e.g. existing unit tests
# that import _SYSTEM_PROMPT directly).  At import time, get_schema_context() returns ""
# (DB not yet loaded), so the SQL example is omitted — this is intentional fail-open
# behaviour.  ControlAgent.__init__ calls _build_system_prompt() at instance creation
# so that a fully loaded runtime always produces the enriched prompt.
_SYSTEM_PROMPT = _build_system_prompt()

_SKILL_HEADER = "\n\n---\n## Analysis Procedures\n\n"
_SKILL_SEPARATOR = "\n\n---\n\n"

_PAST_DECISIONS_HEADER = "\n\n---\n## Past Decisions\n\n"

_DOMAIN_KNOWLEDGE_HEADER = "\n\n---\n## Domain Knowledge\n\n"

# Narrow the tool set per intent so local models aren't overwhelmed by 23+ definitions.
# Fallback: if intent not in map, all control tools remain available.
_INTENT_TOOL_SUBSET: dict[str, list[str]] = {
    # supply_chain: cross-domain stockout/gap/delay/cost diagnosis
    "supply_chain": [
        "nl_query",
        "list_today_exceptions",
        "list_stockout_risk",
        "list_unshipped_orders",
        "analyze_shipment_delay_causes",
        "get_delayed_supply_orders",
        "get_open_supply_orders",
        "calculate_supply_gap",
        "analyze_supply_lead_time",
        "calculate_days_of_inventory",
        "analyze_supply_risk",
        "calculate_stockout_risk",
        "calculate_stockout_cost_impact",
        "calculate_expedite_cost",
        "analyze_forecast_deviation",
        "identify_binding_constraint",
        "analyze_supply_order_timing",
        "job_dispatch",
    ],
    # lookup: lightweight read-only tools for factual questions (max_tool_calls=5)
    "lookup": [
        "nl_query",
        "table_schema_reader",
        "data_catalog_search",
        "list_today_exceptions",
        "list_stockout_risk",
        "list_unshipped_orders",
        "get_open_supply_orders",
        "get_available_to_promise",
        "profile_demand_data",
    ],
    # domain_analysis: all analytical tools, no heavy execution (max_tool_calls=10)
    "domain_analysis": [
        "nl_query",
        "list_today_exceptions",
        "list_unshipped_orders",
        "analyze_shipment_delay_causes",
        "detect_demand_shift",
        "profile_demand_data",
        "analyze_demand_trend",
        "evaluate_forecast_accuracy",
        "detect_demand_anomalies",
        "analyze_seasonality",
        "analyze_demand_drivers",
        "segment_demand",
        "compare_demand_periods",
        "calculate_days_of_inventory",
        "calculate_stockout_risk",
        "list_stockout_risk",
        "calculate_excess_inventory_risk",
        "get_available_to_promise",
        "get_open_supply_orders",
        "get_delayed_supply_orders",
        "calculate_supply_gap",
        "analyze_supply_lead_time",
        "analyze_supply_risk",
        "calculate_holding_cost_impact",
        "calculate_stockout_cost_impact",
        "calculate_expedite_cost",
        "compare_cost_scenarios",
        "analyze_production_plan_gap",
        "analyze_forecast_deviation",
        "identify_binding_constraint",
        "analyze_supply_order_timing",
    ],
    # cross_domain_analysis: domain_analysis + data quality tools (max_tool_calls=15)
    "cross_domain_analysis": [
        "nl_query",
        "list_today_exceptions",
        "list_unshipped_orders",
        "analyze_shipment_delay_causes",
        "detect_demand_shift",
        "data_catalog_search",
        "data_quality_checker",
        "table_schema_reader",
        "profile_demand_data",
        "analyze_demand_trend",
        "evaluate_forecast_accuracy",
        "detect_demand_anomalies",
        "analyze_seasonality",
        "analyze_demand_drivers",
        "segment_demand",
        "compare_demand_periods",
        "calculate_days_of_inventory",
        "calculate_stockout_risk",
        "list_stockout_risk",
        "calculate_excess_inventory_risk",
        "get_available_to_promise",
        "get_open_supply_orders",
        "get_delayed_supply_orders",
        "calculate_supply_gap",
        "analyze_supply_lead_time",
        "analyze_supply_risk",
        "calculate_holding_cost_impact",
        "calculate_stockout_cost_impact",
        "calculate_expedite_cost",
        "compare_cost_scenarios",
        "analyze_production_plan_gap",
        "analyze_forecast_deviation",
        "identify_binding_constraint",
        "analyze_supply_order_timing",
    ],
    # decision_support: analytical + execution tools for optimization/approval (max_tool_calls=20)
    "decision_support": [
        "nl_query",
        "list_today_exceptions",
        "list_unshipped_orders",
        "analyze_shipment_delay_causes",
        "detect_demand_shift",
        "list_stockout_risk",
        "calculate_stockout_risk",
        "calculate_excess_inventory_risk",
        "get_available_to_promise",
        "calculate_days_of_inventory",
        "get_open_supply_orders",
        "get_delayed_supply_orders",
        "calculate_supply_gap",
        "analyze_supply_lead_time",
        "analyze_supply_risk",
        "calculate_holding_cost_impact",
        "calculate_stockout_cost_impact",
        "calculate_expedite_cost",
        "compare_cost_scenarios",
        "optimize_replenishment",
        "simulate_inventory",
        "evaluate_candidates",
        "request_approval",
        "forecast",
        "evaluate_forecast_accuracy",
        "analyze_production_plan_gap",
        "analyze_forecast_deviation",
        "identify_binding_constraint",
        "analyze_supply_order_timing",
        "job_dispatch",
    ],
}


class ControlAgent(AgentBasedSpecialist):
    # Class attribute kept for introspection / unit tests; the instance always
    # receives the dynamically-built prompt via __init__ so that schema context
    # loaded after module import is reflected in every new agent instance.
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
            system_prompt=_build_system_prompt(),
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
                        line = f"Decision {idx}: {content_repr}"
                        outcome = record.get("outcome")
                        if outcome == 1:
                            line += " [user feedback: positive]"
                        elif outcome == -1:
                            line += " [user feedback: negative]"
                        decision_lines.append(line)
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
