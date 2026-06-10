# Agent Architecture

Analysis of the product agent architecture: active agents, tool selection mechanism,
execution flow, and improvement directions.

---

## Active Product Agents

Only **ControlAgent** is active in production. `create_domain_agents()` returns only
ControlAgent. Domain specialist agent classes were deleted in P65; no inactive class stubs
remain.

| Agent | Status | Role |
|---|---|---|
| `ControlAgent` | **Active** | Cross-domain supply chain judgment; the sole specialist agent |
| `SessionOrchestrator` | **Active** | Intent classification, routing, execution coordination |

Valid agent roles: `{"control"}` — defined in `packages/agent/orchestrator/roles.py`.

---

## Tool Selection Mechanism — 3 Layers + LLM

Tool selection is a sequential filter pipeline:

```
31 registered tools
      │
      ▼  Layer 1: Agent role allowlist  (packages/tools/base.py  _ROLE_TOOL_ALLOWLIST)
 ≤31 tools  control role ceiling — auto-derived as union of all Layer 3 subsets (P67)
      │
      ▼  Layer 2: User role safety filter  (packages/tools/base.py  filter_for_user_role)
 ≤31 tools  analyst=read_only only / manager=read_only+hitl / admin=all
      │
      ▼  Layer 3: Intent subset  (packages/agent/control/control_agent.py  _INTENT_TOOL_SUBSET)
 5–28 tools  narrowed to the intent's relevant tool set
      │
      ▼  Layer 4: LLM autonomous selection  (system prompt priority rules)
  0–N calls  LLM picks and calls tools from the presented set
```

Applied sequentially in `packages/agent/runtime.py:909–916`:

```python
agent_role_tools     = registry.list_for_role(self.role)          # Layer 1
user_filtered_tools  = registry.filter_for_user_role(user_role, …) # Layer 2
tool_objects         = [t for t in user_filtered_tools
                        if t.name in set(task.allowed_tools)]      # Layer 3
```

Layer 3 (`task.allowed_tools`) is set by `ControlAgent.run()` before delegating to the
runtime:

```python
if intent_category in _INTENT_TOOL_SUBSET:
    task = task.model_copy(update={"allowed_tools": _INTENT_TOOL_SUBSET[intent_category]})
```

### Intent → Tool Subset (Layer 3)

| Intent | Tools | Notes |
|---|---|---|
| `supply_chain` | 11 | Core stockout / gap / delay / cost diagnosis |
| `lookup` | 7 | Lightweight read-only; aligned with max_tool_calls=5 |
| `domain_analysis` | 24 | All analytical tools; no execution tools |
| `cross_domain_analysis` | 28 | Analytical + data quality tools |
| `decision_support` | 22 | Analytical + optimize / simulate / evaluate / approval |
| `chat` | — | skip_tool_loop=True; no tools presented |

### Layer 1 vs Layer 3: Relationship

Layer 1 (`_ROLE_TOOL_ALLOWLIST["control"]`) is the **permissive ceiling** — what ControlAgent
is ever allowed to see. Layer 3 (`_INTENT_TOOL_SUBSET`) is the **intent-level narrowing**
within that ceiling. A tool name in a Layer 3 subset that does not appear in Layer 1 is
silently excluded (the intersection is empty for that name).

Layer 1 is auto-derived as the union of all Layer 3 subsets (P67): adding or removing
a tool from `_INTENT_TOOL_SUBSET` automatically updates the Layer 1 ceiling.
A regression test (`tests/unit/test_control_agent_intent_tool_subset.py`, added in P63)
verifies that every Layer 3 tool name is reachable from Layer 1.

### Layer 4: System Prompt Priority Rules

`ControlAgent._SYSTEM_PROMPT` declares explicit calling priority:

1. `list_stockout_risk(horizon_days=7)` — call once for cross-SKU risk enumeration;
   never loop `calculate_stockout_risk` per SKU.
2. Specialized tools (`calculate_stockout_risk`, `calculate_days_of_inventory`, …) —
   for single-SKU questions, including days-of-cover and when-do-we-run-out analysis.
3. `nl_query` — for bulk or cross-product questions; generates schema-correct SQL internally.
4. Never fabricate column names.

---

## Tool Importance Ranking

### Tier 1 — Core decision engine

| Tool | safety | Basis |
|---|---|---|
| `list_stockout_risk` | read_only | System prompt priority #1; single call covers all SKUs |
| `nl_query` | read_only | System prompt priority #3; most versatile; real SQL generation |
| `calculate_stockout_risk` | read_only | System prompt priority #2; single-SKU quantification |

### Tier 2 — Supply chain essentials

`get_delayed_supply_orders`, `calculate_days_of_inventory`, `calculate_supply_gap`,
`analyze_supply_lead_time`, `get_open_supply_orders`, `calculate_expedite_cost`

### Tier 3 — Inventory health

`calculate_days_of_inventory`, `calculate_stockout_cost_impact`,
`calculate_excess_inventory_risk`, `get_available_to_promise`

### Tier 4 — Demand analytics (real DB, frequently useful)

`profile_demand_data`, `analyze_demand_trend`, `detect_demand_anomalies`,
`evaluate_forecast_accuracy`

### Tier 5 — Financial impact

`calculate_holding_cost_impact`, `compare_cost_scenarios`

### Tier 6 — Advanced analytics (real DB, lower frequency)

`analyze_seasonality`, `analyze_demand_drivers`, `compare_demand_periods`,
`segment_demand`, `analyze_supply_risk`

### Tier 7 — Decision execution (write/hitl; only after analysis)

`optimize_replenishment`, `simulate_inventory`, `evaluate_candidates`,
`request_approval`, `forecast`

### Tier 8 — Infrastructure / support (rarely LLM-initiated)

`table_schema_reader`, `data_catalog_search`, `data_quality_checker`

### Problematic Tools (should not be LLM-callable)

| Tool | Problem | Recommendation |
|---|---|---|
| `write_audit_log` | Audit logging is an infrastructure concern; LLM must not decide when to write it | Remove from registry; trigger automatically in runtime |
| `job_dispatch` | Fully superseded by `optimize_replenishment`, `simulate_inventory`, `forecast`; raw enum-based dispatch is dangerous | Remove from registry |
| `train_forecast` | Batch/scheduled operation; LLM-triggered retraining risks compute cost and data races | Remove from registry; schedule-only |

---

## Orchestrator → Intent → ControlAgent Execution Flow

### SessionOrchestrator Graph (LangGraph)

```
START
  │
classify_intent ── LLM → SessionIntent
  │                       category ∈ {chat, lookup, domain_analysis,
  │                                   cross_domain_analysis, supply_chain,
  │                                   decision_support}
  │
prepare_ask_user ── analytical intent only
  │                 LLM decides whether clarification is needed
  │                 if yes: pushes question via SSE
  │
wait_for_answer ─── interrupt() if question was asked; pass-through otherwise
  │
select_mode
  │  supply_chain → deterministic route (no LLM call) → single_agent
  │  others       → LLM produces AgentRoute
  │
  ├─ direct_chat  → run_direct_chat → END   (chat; no tools)
  └─ single_agent → run_sequential  → END   (all analytical intents)
```

The `sequential_agents`, `planned_execution`, and `dag_execution` execution modes were
removed in P66 (see `docs/adr/2026-06-10-orchestrator-routing-collapse.md`). All
analytical intents now route through `single_agent → run_sequential`. Multi-agent
fan-out and plan-then-execute routing are future work.

### ControlAgent Execution (within run_sequential)

```
ControlAgent.run()
  │
  ├─ Inject skills (SkillLoader — analysis procedures as text)
  ├─ Inject past decisions (DecisionMemoryStore, k=3)
  ├─ Inject domain knowledge (LongTermMemoryStore, k=3)
  ├─ Narrow tools by intent (_INTENT_TOOL_SUBSET)
  └─ super().run() → AgentRuntime (LangGraph)
         │
         compress_history
         │
         call_model ◄─────────────────────┐
         │  LLM receives: system prompt +  │
         │  narrowed tool specs + question │
         │                                 │
         ├─ tool calls → execute_tools ───┘  (ReAct loop)
         │               for call in calls:
         │                 await tool.handle()  ← sequential
         │
         ├─ hitl tool → prepare_hitl → wait_for_approval → execute_tools
         │
         └─ done → verify_findings (rule-based)
                    ├─ tool_results empty + nil claim    → blocked
                    ├─ tool_results present + short text → blocked
                    ├─ tool_results present + nil claim  → blocked (P62)
                    └─ otherwise → pass → END
```

### LLM Call Count per Request (supply_chain)

| Step | LLM calls |
|---|---|
| classify_intent | 1 |
| prepare_ask_user | 1 (result discarded if no question needed) |
| select_mode | 0 (deterministic for supply_chain) |
| call_model (initial) | 1 |
| call_model (after each tool batch) | 1 per iteration |
| **Minimum total** | **3** |

---

## Orchestrator Roles: Routing vs Planning

The Orchestrator acts as a router. Two active execution paths exist (P66 routing collapse):

| Mode | What it does | When used |
|---|---|---|
| `direct_chat` | Routes to no-tool response | `chat` |
| `run_sequential` | Routes to ControlAgent | all analytical intents |

The `planned_execution` path (`run_planned` / `create_execution_plan()`) and the
`dag_execution` path (`run_dag`) were removed in P66. Plan-then-Execute at the
Orchestrator level is future work; see ADR
`docs/adr/2026-06-10-orchestrator-routing-collapse.md` for the decision record.

Plan-then-Execute at the ControlAgent level remains a known gap:

```
ControlAgent (not implemented)
  [gap] → currently pure ReAct; no pre-planning of tool call order
```

---

## Known Gaps and Improvement Directions

### Gap 1: ControlAgent has no tool-level planning

Within the ReAct loop, tool selection is fully reactive. The LLM decides each tool call
based on the previous result, with no explicit plan. This reduces reproducibility and
makes cross-domain analysis unpredictable.

**Direction:** Add a lightweight plan step (structured output: `[{tool, purpose, depends_on}]`)
before the first `call_model` for complex intents (`domain_analysis`, `cross_domain_analysis`,
`decision_support`). Skip for `lookup` and `supply_chain` where system prompt rules suffice.

### Gap 2: execute_tools is sequential

`_execute_tools_node` iterates `response.tool_calls` with a sequential `for` loop.
When the LLM returns multiple independent tool calls in one response, they execute one
at a time.

**Direction:** Replace with `asyncio.gather()` for non-HITL tool calls. Complement with
system prompt guidance to batch independent tool calls in a single response.

### Gap 3: Response synthesis has no format constraint

Tool results are passed to the LLM as raw JSON. The LLM decides structure and depth of
the final response, producing inconsistent output.

**Direction (highest ROI):** Enforce a response format in the system prompt:
- Situation (tool result summary)
- Root cause
- Recommended actions (numbered, with data-backed rationale)
- Confidence level

### Gap 4: Layer 1 and Layer 3 are independent allowlists

`_ROLE_TOOL_ALLOWLIST["control"]` and `_INTENT_TOOL_SUBSET` define overlapping tool sets
in separate files. P63 added a regression test
(`test_control_agent_intent_tool_subset.py`) to catch mismatches. P67 collapsed
`_ROLE_TOOL_ALLOWLIST` to two entries — `"orchestrator"` (empty guard) and `"control"`
(auto-derived from `_INTENT_TOOL_SUBSET`) — eliminating the 14 dead role entries.
The structural redundancy between Layer 1 and Layer 3 persists; Layer 1 is now the
union of all Layer 3 subsets, automatically maintained.

**Direction:** When Specialist Agents are introduced as independent runtimes (Post-MVP),
each will need its own role entry in `_ROLE_TOOL_ALLOWLIST`. Until then, the current
auto-derived approach keeps Layer 1 and Layer 3 in sync.

### Gap 5: Three tools should not be LLM-callable

`write_audit_log`, `job_dispatch`, `train_forecast` are registered in `create_tool_registry()`
but excluded from `_ROLE_TOOL_ALLOWLIST["control"]`. They are inaccessible to ControlAgent
but remain in the registry, creating confusion and maintenance risk.

**Direction:** Remove from `create_tool_registry()`; wire `write_audit_log` into the
runtime's audit path; trigger `job_dispatch` and `train_forecast` via scheduled or
API-initiated jobs only.
