from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from packages.agent.base import AgentBasedSpecialist
from packages.knowledge import SkillLoader
from packages.memory.decision import DecisionMemoryStore
from packages.memory.long_term import LongTermMemoryStore
from packages.tools.schema_context import get_schema_context
from packages.tools.sql_allowlist import ALLOWED_READ_TABLES

if TYPE_CHECKING:
    from packages.agent.orchestrator import SpecialistResult, SpecialistTask
    from packages.tools.base import ToolContext

_log = logging.getLogger(__name__)


def render_business_guidelines() -> str:
    """Return the fixed role/responsibilities/domains-in-scope preamble.

    Pure fixed text — no backtick-quoted tool names and no table/column names.
    This section describes what the agent IS, not how it routes or responds.
    """
    return (
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
        "and finance impact quantification (holding costs, stockout costs, expedite costs)."
    )


def render_response_format() -> str:
    """Return the response-format section and past-decisions annotation note.

    Pure fixed text — no dynamic placeholders.  Contains only the four-section
    response format and the past-decisions annotation note.  Operational
    grounding constraints (rules 11–12) now live in render_routing_policy().
    """
    return (
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
        " as ineffective and avoid repeating them in your current response."
    )


def render_schema_context(schema: str) -> str:
    """Return the correlated-subquery SQL example for the given schema string.

    Delegates to _make_schema_example(schema) when schema is non-empty.  Returns ""
    (fail-open) when schema is empty so callers need not handle None.

    Args:
        schema: The schema context string (as returned by get_schema_context()).
                Pass "" to suppress the schema example entirely.
    """
    if not schema:
        return ""
    return _make_schema_example(schema)


def render_tool_catalog(subset: dict[str, list[str]]) -> str:
    """Return a readable per-intent catalog string from _INTENT_TOOL_SUBSET.

    Example output (one intent per line):
        supply_chain: nl_query, list_stockout_risk, list_today_exceptions, ...
        lookup: nl_query, table_schema_reader, ...
    """
    lines = []
    for intent, tools in subset.items():
        lines.append(f"{intent}: {', '.join(tools)}")
    return "\n".join(lines)


def render_routing_policy(subset: dict[str, list[str]]) -> str:
    """Generate the routing-instruction text for _SYSTEM_PROMPT_TEMPLATE.

    Produces a section that lists which tools are available per intent, replacing
    the hand-written tool-name enumerations in the template.  Business policy
    prose (safety rules, job_dispatch triggers, response format) is NOT generated
    here — it remains hand-written in the template.
    """
    sc = subset.get("supply_chain", [])
    da = subset.get("domain_analysis", [])

    # Helper: pick first matching name from subset list, or fall back to literal
    def _pick(tools: list[str], *candidates: str) -> str:
        for c in candidates:
            if c in tools:
                return c
        return candidates[0]

    exceptions_tool = _pick(sc, "list_today_exceptions")
    stockout_list_tool = _pick(sc, "list_stockout_risk")
    stockout_calc_tool = _pick(sc, "calculate_stockout_risk")
    nl_tool = _pick(sc, "nl_query")
    supply_gap_tool = _pick(sc, "calculate_supply_gap")
    doi_tool = _pick(sc, "calculate_days_of_inventory")
    delay_tool = _pick(sc, "analyze_shipment_delay_causes")
    unshipped_tool = _pick(sc, "list_unshipped_orders")
    demand_shift_tool = _pick(da, "detect_demand_shift")
    segment_tool = _pick(da, "segment_demand")
    compare_tool = _pick(da, "compare_demand_periods")
    forecast_dev_tool = _pick(da, "analyze_forecast_deviation")
    forecast_acc_tool = _pick(da, "evaluate_forecast_accuracy")
    prod_gap_tool = _pick(da, "analyze_production_plan_gap")
    constraint_tool = _pick(da, "identify_binding_constraint")
    order_timing_tool = _pick(da, "analyze_supply_order_timing")
    delayed_orders_tool = _pick(sc, "get_delayed_supply_orders")

    catalog = render_tool_catalog(subset)

    return (
        f"Tool availability by intent:\n{catalog}\n\n"
        "Tool usage priority (follow this order):\n"
        f"1. For questions about today's exceptions, what needs attention today, or what requires "
        f"human judgment today — call `{exceptions_tool}` ONCE. "
        f"Do NOT loop {stockout_list_tool}, {delayed_orders_tool}, detect_demand_anomalies, "
        f"and data_quality_checker separately to assemble the same picture.\n"
        f"2. To enumerate stockout risk across all SKUs (non-exception context), call "
        f"`{stockout_list_tool}(horizon_days=7)` once — "
        f"do NOT loop `{stockout_calc_tool}` per SKU.\n"
        f"2b. For questions about supply shortages next week or next month "
        f"(e.g. 'which products may face supply shortages', 'supply gap over the next 30 days') "
        f"— DO NOT use `{stockout_list_tool}` (that tool measures on-hand stockout risk only, "
        f"NOT forward supply adequacy). "
        f"Call `{nl_tool}` EXACTLY ONCE — "
        f"do NOT call {nl_tool} a second time after the first result. "
        f"The {nl_tool} must use CORRELATED SUBQUERIES (not JOINs) for each metric. "
        f"{{schema_example}}"
        f"After {nl_tool} returns, synthesize immediately into your final answer — do NOT call "
        f"any tool again. "
        f"`{supply_gap_tool}` is for SINGLE-SKU deep-dive (requires sku_id parameter).\n"
        f"3. Use a specialized tool (e.g. {stockout_calc_tool}, {doi_tool}) "
        f"when it directly covers a single-SKU question, including days-of-cover "
        f"and when-do-we-run-out analysis.\n"
        f"4. For shipment-delay or unshipped-order root-cause questions — call "
        f"`{delay_tool}` ONCE. "
        f"Do NOT reconstruct causes by hand-joining raw tables yourself. "
        f"For a plain listing of unshipped orders (without root-cause analysis) call "
        f"`{unshipped_tool}` ONCE.\n"
        f"5. For demand-shift questions by customer or region — call `{demand_shift_tool}` ONCE. "
        f"{segment_tool} and {compare_tool} are SKU-axis tools (consumption series); "
        f"they do NOT answer customer/region demand questions. "
        f"Customer/region demand questions (SPEC Q9) are answered from order transaction data, "
        f"not from the consumption series. The consumption series is for forecast/stockout "
        f"tools only.\n"
        f"6. For forecast-vs-actual gap questions (SPEC Q5) — why is actual demand deviating "
        f"from the forecast, over-forecast/under-forecast analysis — call "
        f"`{forecast_dev_tool}` ONCE. "
        f"`{forecast_acc_tool}` is the model-quality axis (MAPE/bias); "
        f"pair with `{demand_shift_tool}` when the user asks which customer/region"
        f" drives the gap.\n"
        f"7. For production plan adjustment questions (SPEC Q7) — which products need production "
        f"plan changes, overproduction/underproduction analysis — call "
        f"`{prod_gap_tool}` ONCE. "
        f"Do NOT reconstruct plan-vs-demand gaps by hand-joining "
        f"production and demand tables yourself.\n"
        f"8. For biggest-constraint or bottleneck-impact questions (SPEC Q10) — "
        f"call `{constraint_tool}` ONCE. "
        f"Do NOT separately evaluate capacity, supply-gap, and stockout risks "
        f"by assembling your own ranking from individual tool results.\n"
        f"9. For purchase-earlier/later or order-timing questions (SPEC Q8) — "
        f"call `{order_timing_tool}` ONCE. "
        f"`{delayed_orders_tool}` answers 'what is already late by status'; "
        f"`{order_timing_tool}` answers 'which orders should arrive sooner or later'.\n"
        f"10. Use {nl_tool} for bulk or cross-product questions — "
        f"pass the question in plain English; "
        f"{nl_tool} generates schema-correct SQL internally.\n"
        f"11. Never fabricate column names or assume columns"
        f" that are not confirmed by tool results.\n\n"
        f"Always ground recommendations in tool results."
        f" Do not fabricate quantities or risk scores.\n"
        f"Once you have sufficient data from tools, stop calling tools"
        f" and produce a final text response.\n"
        f"Never call the same tool twice in one analysis pass. "
        f"If you have not yet called any tool in this pass, you MUST call the appropriate tool "
        f"before answering — never produce a final answer without tool data. "
        f"After receiving results from `{stockout_list_tool}`, synthesise them immediately"
        f" into a final answer — do NOT call `{stockout_list_tool}` or any other tool again"
        f" in the same pass.\n"
        f"For exception/delay questions, call `{exceptions_tool}` to surface the full daily"
        f" exception picture in one call.\n"
        f"12. For heavy or long-running work — call `job_dispatch` with the appropriate job_type"
        f" and await human approval before execution begins."
        f" This is MANDATORY; never run these inline.\n"
        f"    Trigger phrases that ALWAYS route to job_dispatch:\n"
        f"    - 'as a background job', 'run in the background', 'notify me when it completes'\n"
        f"    - 'train the forecast model', 'train_forecast'\n"
        f"    - 'run a full ... simulation for all SKUs'\n"
        f"    Job type mapping: train_forecast → job_type='train_forecast';"
        f" inventory simulation → job_type='simulate';"
        f" replenishment optimization → job_type='optimize';"
        f" demand forecast → job_type='forecast'.\n"
    )


# Narrow the tool set per intent so local models aren't overwhelmed by 23+ definitions.
# Fallback: if intent not in map, all control tools remain available.
# IMPORTANT: this dict is the SSoT for per-intent tool availability.  render_routing_policy()
# derives tool-name references from it so the prompt stays consistent when tools are
# added or renamed.
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


# _SYSTEM_PROMPT_TEMPLATE is kept as a legacy alias so that any external code that
# imported this constant before P109 continues to work without changes.  The prompt
# is now assembled by _build_system_prompt() from discrete render_* functions.
# At import time get_schema_context() returns "" (DB not yet ready), which is fine —
# ControlAgent.__init__ calls _build_system_prompt(schema_context=get_schema_context())
# at instance-creation time so every new agent gets the fully-loaded prompt.
_SYSTEM_PROMPT_TEMPLATE = ""  # deprecated; use _build_system_prompt() instead


def _make_schema_example(schema: str) -> str:
    """Build a correlated-subquery SQL example from the given schema context string.

    Returns an empty string when schema is empty (i.e. before API startup calls
    load_schema_context()).  This keeps the prompt valid at import time without
    requiring a DB connection.

    Args:
        schema: The schema context string (as returned by get_schema_context()).
                Callers that previously relied on the global read must now pass
                get_schema_context() explicitly.
    """
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

    # Identify the SKU master table and correlated tables.
    # Names are derived from ALLOWED_READ_TABLES (not literals) so that if the
    # allowlist is ever updated, the example fails open rather than generating SQL
    # with a stale table name.
    sku_table = next((t for t in ALLOWED_READ_TABLES if t == "sku_master"), None)
    demand_table = next((t for t in ALLOWED_READ_TABLES if t == "demand_history"), None)
    inventory_table = next((t for t in ALLOWED_READ_TABLES if t == "inventory_snapshot"), None)
    supply_table = next((t for t in ALLOWED_READ_TABLES if t == "supply_orders"), None)

    # Additionally verify each table is present in the live schema context.
    if sku_table not in table_cols:
        sku_table = None
    if demand_table not in table_cols:
        demand_table = None
    if inventory_table not in table_cols:
        inventory_table = None
    if supply_table not in table_cols:
        supply_table = None

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


def _build_system_prompt(
    intent: str | None = None,
    user_role: str = "analyst",
    schema_context: str = "",
) -> str:
    """Assemble the system prompt from discrete conceptual-module sections.

    Each section is an independently maintainable render_* function:
      - render_business_guidelines(): role/responsibilities/domains (pure fixed text)
      - render_routing_policy():      per-intent tool-routing rules + grounding rules 11–12
                                      (includes render_tool_catalog() output at the top)
      - render_schema_context():      optional correlated-subquery SQL example
      - render_response_format():     four-section response format + past-decisions note

    Sections that return "" are excluded from the join so the prompt degrades
    gracefully when schema context is not yet loaded (e.g. at import time).

    Args:
        intent:         Reserved for future per-intent routing-policy narrowing.
                        Currently unused — full _INTENT_TOOL_SUBSET is always passed.
        user_role:      Reserved for future render_user_permissions(user_role) section.
                        Currently unused.
        schema_context: Schema context string from get_schema_context().  Pass ""
                        to suppress the SQL example (fail-open behaviour).
    """
    # intent and user_role are accepted but unused — reserved for future sections.
    _ = intent
    _ = user_role
    # inject schema_example into the {schema_example} placeholder that
    # render_routing_policy embeds inside its rule-2b text.
    routing_section = render_routing_policy(_INTENT_TOOL_SUBSET).format(
        schema_example=render_schema_context(schema_context)
    )
    return "\n\n".join(
        filter(
            None,
            [
                render_business_guidelines(),
                routing_section,
                render_response_format(),
            ],
        )
    )


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
            system_prompt=_build_system_prompt(intent=None, schema_context=get_schema_context()),
            model_registry=model_registry,
        )

    # ------------------------------------------------------------------
    # Private pipeline helpers (extracted from run() for readability)
    # ------------------------------------------------------------------

    def _inject_skills(
        self,
        task: "SpecialistTask",
        intent_category: str,
    ) -> "SpecialistTask":
        """Prepend skill block to task.instruction if skills exist for intent."""
        skills = SkillLoader().load(intent_category)
        if skills:
            skill_block = _SKILL_HEADER + _SKILL_SEPARATOR.join(skills)
            task = task.model_copy(
                update={"instruction": skill_block + "\n\n" + task.instruction}
            )
        return task

    async def _inject_past_decisions(
        self,
        task: "SpecialistTask",
        session_id: str,
        store: DecisionMemoryStore,
    ) -> "SpecialistTask":
        """Append past-decisions block from DecisionMemoryStore to task.instruction."""
        if not session_id:
            return task
        try:
            past_records = await store.search(
                json.dumps({"session_id": session_id}), k=3
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
        return task

    async def _inject_domain_knowledge(
        self,
        task: "SpecialistTask",
        intent_category: str,
    ) -> "SpecialistTask":
        """Append domain knowledge block from LongTermMemoryStore to task.instruction."""
        if not intent_category:
            return task
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
        return task

    def _narrow_tools(
        self,
        task: "SpecialistTask",
        intent_category: str,
    ) -> "SpecialistTask":
        """Narrow allowed_tools to the intent-specific subset."""
        if intent_category and intent_category in _INTENT_TOOL_SUBSET:
            task = task.model_copy(
                update={"allowed_tools": _INTENT_TOOL_SUBSET[intent_category]}
            )
        return task

    async def _write_decision_record(
        self,
        session_id: str,
        intent_category: str,
        result: "SpecialistResult",
        store: DecisionMemoryStore,
    ) -> None:
        """Write a success decision record to DecisionMemoryStore."""
        try:
            response_text: str = (result.output.get("text") or "") if result.output else ""
            tool_calls_count: int = len(result.tool_calls_made)
            await store.write({
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

    async def _write_failure_record(
        self,
        session_id: str,
        intent_category: str,
        exc: Exception,
        store: DecisionMemoryStore,
    ) -> None:
        """Write a failure record to DecisionMemoryStore."""
        try:
            await store.write({
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

    async def run(
        self,
        task: "SpecialistTask",
        ctx: "ToolContext",
        agent_run_id: str = "",
    ) -> "SpecialistResult":
        intent_category: str = (
            (task.context_payload.get("intent") or {}).get("category") or ""
        )
        session_id: str = (
            task.context_payload.get("session_id") or str(ctx.session_id)
        )
        store = DecisionMemoryStore()

        task = self._inject_skills(task, intent_category)
        task = await self._inject_past_decisions(task, session_id, store)
        task = await self._inject_domain_knowledge(task, intent_category)
        task = self._narrow_tools(task, intent_category)

        result: "SpecialistResult | None" = None
        try:
            result = await super().run(task, ctx, agent_run_id=agent_run_id)
        except Exception as exc:
            if session_id:
                await self._write_failure_record(session_id, intent_category, exc, store)
            raise

        if session_id and result is not None:
            await self._write_decision_record(session_id, intent_category, result, store)

        return result
