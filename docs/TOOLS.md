# TOOLS.md

## Purpose

This document defines the specifications, arguments, return values, permissions, and failure handling for all tools in the Tool Layer.

Tools are the sole execution capability of product agents. Agents must not access databases, call LLMs, or perform calculations except through the tools defined here.

For tool categories and design principles, see `docs/DESIGN.md` §Tool Design.

---

## API Behavioral Contracts

Behaviors that must survive every refactoring phase. If a change would break one of these, file an ADR before proceeding.

### HTTP API Routes

| Route | Method | Guaranteed behavior |
|---|---|---|
| `/healthz` | GET | 200 `{"status": "ok"}` |
| `/readyz` | GET | 200 when DB reachable; 503 when not |
| `POST /api/v1/sessions` | POST | Creates session; returns `session_id` (UUID, stable across restarts) |
| `GET /api/v1/sessions` | GET | Returns list of sessions for caller |
| `GET /api/v1/sessions/{session_id}` | GET | Returns session or 404 |
| `DELETE /api/v1/sessions/{session_id}` | DELETE | 204; cascades to messages |
| `GET /api/v1/sessions/{session_id}/messages` | GET | Returns ordered message list |
| `POST /api/v1/sessions/{session_id}/messages` | POST | Enqueues user message; returns job handle |
| `GET /api/v1/sessions/{session_id}/stream` | GET | SSE stream (see `packages/schemas/sse_events.py`) |
| `POST /api/v1/sessions/{session_id}/messages/{message_id}/answer` | POST | Submits AskUser answer; resumes orchestrator |
| `POST /api/v1/decisions` | POST | Triggers async decision job; returns `job_id` |
| `GET /api/v1/decisions/{job_id}/status` | GET | Returns job status; never blocks |
| `GET /api/v1/approvals/{approval_id}` | GET | Returns approval or 404 |
| `POST /api/v1/approvals/{approval_id}/decision` | POST | Applies state transition; 422 on illegal transitions |

### Auth Contracts

| Condition | Behavior |
|---|---|
| `APP_ENV=dev` | `user_id` is `None`; all routes accessible without token |
| `APP_ENV != dev` | Auth middleware enforces identity; unauth → 401 |

- Missing/invalid credentials → **401** (not 403, not 200)
- Insufficient permissions → **403**
- These codes MUST NOT be swapped during refactoring.

### Error Contracts

| Situation | Required behavior |
|---|---|
| Request validation failure | 422 (FastAPI default; MUST NOT change to 400) |
| Internal / unexpected error | 500 with error envelope; never silent 200 with error in body |
| Missing `ANTHROPIC_API_KEY` | `RuntimeError` at call site; never stub or no-op |
| Missing external service config | `RuntimeError` at call site; never silently degrade |
| Illegal approval state transition | 422 |

### Persistence Contracts

The following data MUST survive a service restart:

| Entity | Repository | Guarantee |
|---|---|---|
| Sessions | `persistence.sessions_repo` | `session_id` stable; messages preserved |
| Approvals | `persistence.approvals_repo` | Status and all transitions preserved |
| Audit log | `persistence.audit_log_repo` | Append-only; no rows ever deleted |
| LLM usage | `persistence.llm_usage_repo` | Cost/token records preserved |

Approval state machine (enforced at domain layer, not just DB):

```
pending → approved | rejected | needs_revision | expired
approved / rejected / needs_revision / expired → (terminal — no further transitions)
```

### SSE Stream Contract

The SSE event schema is the code: `packages/schemas/sse_events.py` is SSoT.

**Guaranteed invariants (independent of event type):**
- Every stream ends with `done` or `error` — never silently terminates mid-sequence.
- `done.reply` is always populated with the final user-facing text.

---

## Tool Access Control

Tool access is enforced at two layers, both of which must pass for a tool to be callable.

### Layer 1: Role-Based Allowlist

Defined in `packages/tools/base.py` as `_ROLE_TOOL_ALLOWLIST`. Each agent role has a static set of permitted tool names. A tool not in a role's allowlist is never exposed to that agent, regardless of the task.

`ControlAgent` is the only runtime product agent (`VALID_AGENT_ROLES = {"control"}`). Its allowlist is **auto-derived** at first access from the union of all `_INTENT_TOOL_SUBSET` values in `packages/agent/control/control_agent.py`.

| Role | Permitted Tools |
|---|---|
| `orchestrator` | *(empty — safety guard; the SessionOrchestrator calls the LLM directly and never calls tools)* |
| `control` | *(auto-derived from `_INTENT_TOOL_SUBSET` — see below)* |

#### `control` role tool allowlist (derived from `_INTENT_TOOL_SUBSET`)

The full set of tools reachable by the ControlAgent is the union of all intent-subset lists. By intent category:

| Intent | Tools available to ControlAgent |
|---|---|
| `supply_chain` | `nl_query`, `list_stockout_risk`, `get_delayed_supply_orders`, `get_open_supply_orders`, `calculate_supply_gap`, `analyze_supply_lead_time`, `calculate_days_of_inventory`, `analyze_supply_risk`, `calculate_stockout_risk`, `calculate_stockout_cost_impact`, `calculate_expedite_cost` |
| `lookup` | `nl_query`, `table_schema_reader`, `data_catalog_search`, `list_stockout_risk`, `get_open_supply_orders`, `get_available_to_promise`, `profile_demand_data` |
| `domain_analysis` | `nl_query`, `profile_demand_data`, `analyze_demand_trend`, `evaluate_forecast_accuracy`, `detect_demand_anomalies`, `analyze_seasonality`, `analyze_demand_drivers`, `segment_demand`, `compare_demand_periods`, `calculate_days_of_inventory`, `calculate_stockout_risk`, `list_stockout_risk`, `calculate_excess_inventory_risk`, `get_available_to_promise`, `get_open_supply_orders`, `get_delayed_supply_orders`, `calculate_supply_gap`, `analyze_supply_lead_time`, `analyze_supply_risk`, `calculate_holding_cost_impact`, `calculate_stockout_cost_impact`, `calculate_expedite_cost`, `compare_cost_scenarios` |
| `cross_domain_analysis` | everything in `domain_analysis` plus `data_quality_checker`, `table_schema_reader`, `data_catalog_search` |
| `decision_support` | `nl_query`, `list_stockout_risk`, `calculate_stockout_risk`, `calculate_excess_inventory_risk`, `get_available_to_promise`, `calculate_days_of_inventory`, `get_open_supply_orders`, `get_delayed_supply_orders`, `calculate_supply_gap`, `analyze_supply_lead_time`, `analyze_supply_risk`, `calculate_holding_cost_impact`, `calculate_stockout_cost_impact`, `calculate_expedite_cost`, `compare_cost_scenarios`, `optimize_replenishment`, `simulate_inventory`, `evaluate_candidates`, `request_approval`, `forecast`, `evaluate_forecast_accuracy` |

### Layer 2: Task-Level Tool List

When the orchestrator dispatches a task to a specialist, it includes `allowed_tools`: an explicit list of tool names the specialist may use for that specific task. This is the intersection of the role allowlist and the tools the orchestrator has determined are needed for the current step.

`_default_tools(agent_role)` in `packages/agent/orchestrator/runtime.py` reads Layer 1 directly and uses it as the default Layer 2 list. The orchestrator's LLM-generated plan (`TaskNode.tools`) may further narrow this list per step.

**Effective tool set = Layer 1 ∩ Layer 2**

A tool is only callable when it appears in both layers.

### Table Allowlist (SQL-level)

All tools that issue user- or LLM-provided SQL queries are additionally restricted by `validate_read_sql()` in `packages/tools/sql_guardrail.py` before any database execution. The guardrail uses `ALLOWED_READ_TABLES` (`packages/tools/sql_allowlist.py`) as the read table allowlist:

```
sku_master, inventory, demand_history, supply, cost, customers
```

Guardrail rules:

- SQL must be non-empty and parse to exactly one statement.
- Statement type must be `SELECT`.
- The query must reference at least one allowlisted table.
- Referenced tables must be in `ALLOWED_READ_TABLES`.
- `public.<allowed_table>` and quoted allowlisted names such as `"sku_master"` are allowed.
- Non-public schema references such as `other_schema.sku_master` are rejected.
- Table extraction covers `FROM`, `JOIN`, comma joins, CTE bodies, subqueries, and `UNION` branches.
- Non-read operations are rejected regardless of table, including `INSERT`, `UPDATE`, `DELETE`, `DROP`, `CREATE`, `ALTER`, `TRUNCATE`, `COPY`, `CALL`, `DO`, `GRANT`, and `REVOKE`.
- Operationally dangerous functions or features are rejected, including `pg_sleep`, `dblink`, `postgres_fdw`, `lo_import`, `lo_export`, and `copy`.

This guardrail is a Tool Layer responsibility. Repository functions in `packages/persistence/` execute already-validated SQL and do not duplicate SQL safety policy.

---

## MVP Tool Priority

The following tools are required first to achieve the minimum viable agent capability. Priority 1–4 are implemented; 5–10 are deferred.

| Priority | Tool | Status | Rationale |
|---|---|---|---|
| 1 | `data_catalog_search` | ✅ Implemented | Discover what data is available |
| 2 | `nl_query` | ✅ Implemented | Retrieve actual operational data via schema-aware SQL |
| 3 | `table_schema_reader` | ✅ Implemented | Understand data structure |
| 4 | `data_quality_checker` | ✅ Implemented | Detect missing values and anomalies |
| 5 | `business_rules_reader` | Deferred | Enforce business constraints |
| 6 | `metric_definition_reader` | Deferred | Prevent KPI definition drift |
| 7 | `calculator` | Deferred | Perform basic numeric calculations |
| 8 | `scenario_builder` | Deferred | Enable what-if analysis |
| 9 | `summary_generator` | Deferred | Produce human-readable explanations |
| 10 | `audit_log_writer` | ✅ Implemented (`write_audit_log`) | Record decision history and accountability — auto-triggered post-completion by `AgentRuntime`; not LLM-callable |

---

## Tool Specifications

### Data Access Tools

---

#### `data_catalog_search`

List available operational tables and their row counts.

**Class:** `DataCatalogSearchTool` (`packages/tools/data_catalog_search_tool.py`)
**Requires approval:** No

**Input**

| Field | Type | Required | Description |
|---|---|---|---|
| `keyword` | string | No | Partial match filter on table name |

**Output**

| Field | Type | Description |
|---|---|---|
| `tables` | array | List of `{table_name: string, row_count: integer \| null}` |
| `count` | integer | Number of tables returned |

**Failure handling**

If the database is unreachable, `row_count` is `null` for all entries. The tool always returns a valid result; it never raises.

**Audit payload:** `{keyword, table_count}`

---

#### `table_schema_reader`

Read column definitions for an operational table from `information_schema.columns`.

**Class:** `TableSchemaReaderTool` (`packages/tools/table_schema_reader_tool.py`)
**Requires approval:** No

**Input**

| Field | Type | Required | Description |
|---|---|---|---|
| `table_name` | string | Yes | Name of the table to inspect |

**Output**

| Field | Type | Description |
|---|---|---|
| `table_name` | string | Echoed table name |
| `columns` | array | List of `{column_name, data_type, is_nullable: boolean, column_default: string \| null}` |
| `column_count` | integer | Number of columns |
| `error` | string | Present only when table is not in the allowlist |

**Failure handling**

- If `table_name` is not in `ALLOWED_READ_TABLES`: returns `error` in output, `column_count: 0`, no exception raised.
- If the database is unreachable: returns empty `columns`, `column_count: 0`, `note: "no database connection"`.

**Audit payload:** `{table_name, column_count}`

---

#### `data_quality_checker`

Check for missing values in an operational table. Reports NULL counts and NULL percentages per column using a single aggregation query.

**Class:** `DataQualityCheckerTool` (`packages/tools/data_quality_checker_tool.py`)
**Requires approval:** No

**Input**

| Field | Type | Required | Description |
|---|---|---|---|
| `table_name` | string | Yes | Name of the table to check |

**Output**

| Field | Type | Description |
|---|---|---|
| `table_name` | string | Echoed table name |
| `total_rows` | integer | Total row count |
| `columns` | array | List of `{column_name, null_count: integer, null_pct: number}` |
| `has_issues` | boolean | True if any column has at least one NULL |
| `error` | string | Present only when table is not in the allowlist |

**Failure handling**

- If `table_name` is not in `ALLOWED_READ_TABLES`: returns `error` in output, no exception raised.
- If the database is unreachable: returns `total_rows: 0`, empty `columns`, `has_issues: false`, `note: "no database connection"`.

**Security note:** `table_name` is validated against `ALLOWED_READ_TABLES` (a compile-time frozenset) before any SQL is issued. Column names are sourced from `information_schema.columns` for that specific table and are safe to interpolate.

**Audit payload:** `{table_name, total_rows}`

---

#### `nl_query`

Translate a natural-language question into SQL and execute it. Uses the LLM to generate SQL, validates it through `packages/tools/sql_guardrail.py`, and executes it through the repository layer.

The DB schema provided to the LLM is **auto-generated at API startup** from `information_schema.columns` via `packages/tools/schema_context.py`. Do not write or maintain a hand-coded schema string in this tool or anywhere else.

**Class:** `NlQueryTool` (`packages/tools/nl_query_tool.py`)
**Requires approval:** No

**Input**

| Field | Type | Required | Description |
|---|---|---|---|
| `question` | string | Yes | Natural-language question about operational data |

**Output**

| Field | Type | Description |
|---|---|---|
| `results` | array | List of row dicts |
| `count` | integer | Number of rows returned |
| `sql` | string | Generated SQL that was executed |
| `error` | string | Present on failure |

**Failure handling**

- No `LLMClient` provided at registry creation: raises `RuntimeError` at call time (configuration error — must not silently degrade).
- SQL guardrail rejection: returns `error` in output immediately; unsafe generated SQL is not retried or executed.
- Database unreachable: returns empty results with `error`.
- Schema context not yet loaded (DB unavailable at startup): LLM receives no schema section; query quality degrades but the tool does not raise.

**Audit payload:** `{question, sql, count}`

---

### Analysis Tools

---

#### `forecast`

Forecast future demand for a SKU using a linear regression predictor trained on `demand_history`.

**Class:** `ForecastTool` (`packages/tools/forecast_tool.py`)
**Requires approval:** No

**Input**

| Field | Type | Required | Description |
|---|---|---|---|
| `sku_id` | string | Yes | SKU identifier |
| `horizon_days` | integer ≥ 1 | Yes | Number of days to forecast |

**Output**

| Field | Type | Description |
|---|---|---|
| `sku_id` | string | Echoed SKU |
| `forecast_units` | array of number | Forecasted demand per day |
| `model_version` | string | Identifier of the model used |
| `nulls_skipped` | integer | Rows excluded due to missing data |
| `prediction` | number \| null | First day's forecast value |
| `source` | string | `"linear_regression"` or `"stub"` |

**Failure handling**

- If no `predictor` or `db_session` is provided at registry creation: falls back to a stub that returns `10.0` for each day with `source: "stub"`. This is a known degraded state, not a silent failure — `source` always indicates the actual data path.

**Audit payload:** `{sku_id, horizon_days, model_version, source}`

---

#### `evaluate_candidates`

Score a list of candidate replenishment plans against all KPIs independently. Does not collapse scores into a single weighted total.

**Class:** `EvaluatorTool` (`packages/tools/evaluator_tool.py`)
**Requires approval:** No

**Input**

| Field | Type | Required | Description |
|---|---|---|---|
| `candidates` | array | Yes | List of candidate objects with `order_qty` |
| `sku_id` | string | Yes | SKU identifier |

**Output**

| Field | Type | Description |
|---|---|---|
| `evaluated_candidates` | array | Each candidate with `kpi_scores` (per-KPI, not collapsed), `risk_level`, `rank` |
| `primary` | object | Highest-ranked candidate |

**Failure handling**

Returns an empty `evaluated_candidates` list if the input is invalid or empty.

**Audit payload:** `{sku_id, candidate_count}`

---

### Simulation Tools

---

#### `simulate_inventory`

Run a deterministic inventory simulation for a SKU and proposed order quantity over a time horizon.

**Class:** `SimulationTool` (`packages/tools/simulation_tool.py`)
**Requires approval:** No

**Input**

| Field | Type | Required | Description |
|---|---|---|---|
| `sku_id` | string | Yes | SKU identifier |
| `order_qty` | number | Yes | Order quantity to simulate |
| `horizon_days` | integer ≥ 1 | Yes | Simulation horizon in days |

**Output**

| Field | Type | Description |
|---|---|---|
| `sku_id` | string | Echoed SKU |
| `ending_on_hand` | number | Inventory on hand at end of horizon |
| `stockout_days` | integer | Days with zero inventory |
| `mean_lead_time_days` | integer | Mean lead time used in simulation |

**Failure handling**

Raises `RuntimeError` if the underlying job fails. The caller (agent runtime) is responsible for catching and surfacing this.

**Audit payload:** `{sku_id, order_qty, horizon_days}`

---

### Optimization Tools

---

#### `optimize_replenishment`

Enumerate MOQ multiples and return the top 3 replenishment candidates ranked by total supply chain cost.

**Class:** `OptimizerTool` (`packages/tools/optimizer_tool.py`)
**Requires approval:** No

**Input**

| Field | Type | Required | Description |
|---|---|---|---|
| `sku_id` | string | Yes | SKU identifier |
| `moq` | number | Yes | Minimum order quantity |
| `horizon_days` | integer ≥ 1 | Yes | Planning horizon in days |
| `max_stockout_days` | integer ≥ 0 | No | Maximum tolerated stockout days (default: 30) |

**Output**

| Field | Type | Description |
|---|---|---|
| `candidates` | array | Up to 3 candidates, each with `order_qty`, `total_cost`, `kpi_scores` |

**Audit payload:** `{sku_id, moq, horizon_days, candidate_count}`

---

### Memory / Audit Tools

---

#### `write_audit_log`

Write a tamper-evident audit log entry. Each entry is chained to the previous via SHA-256 hash.

**Class:** `AuditLogTool` (`packages/tools/audit_tool.py`)
**Not registered in `create_tool_registry()`** — auto-triggered by `AgentRuntime.run()` post-completion; not LLM-callable and not gated by any role allowlist.
**Requires approval:** No

**Input**

| Field | Type | Required | Description |
|---|---|---|---|
| `event_type` | string | Yes | Category of the event being logged |
| `payload` | object | Yes | Arbitrary event data |

**Output**

| Field | Type | Description |
|---|---|---|
| `audit_hash` | string | SHA-256 hash of this entry chained with the previous |
| `recorded` | boolean | Always `true` |

**Failure handling**

This tool never fails — it always returns `recorded: true`.

**Audit payload:** `{audit_hash, event_type}`

---

### Guardrail Tools

---

#### `request_approval`

Request human approval for a proposed action. Creates a pending approval record that expires after 24 hours.

**Class:** `ApprovalTool` (`packages/tools/approval_tool.py`)
**Requires approval:** Yes — calling this tool itself triggers an approval gate.

**Input**

| Field | Type | Required | Description |
|---|---|---|---|
| `action_summary` | string | Yes | Human-readable description of the action awaiting approval |
| `risk_level` | `"low"` \| `"medium"` \| `"high"` | No | Risk classification of the proposed action |

**Output**

| Field | Type | Description |
|---|---|---|
| `approval_id` | string | UUID of the created approval request |
| `status` | string | Always `"pending"` on creation |
| `expires_at` | string | ISO 8601 timestamp 24 hours from creation |

**Failure handling**

This tool never fails — it always returns a pending record.

**Audit payload:** `{approval_id, action_summary}`

---

### Non-LLM-Callable Tools (Job Pipeline)

These tool classes exist in `packages/tools/` and are exported from `packages/tools/__init__.py`
but are **not registered** in `create_tool_registry()`. They are invoked by non-LLM paths only.

---

#### `job_dispatch`

Dispatch a long-running job for execution with human approval.

**Class:** `JobDispatchTool` (`packages/tools/job_dispatch_tool.py`)
**Not registered in `create_tool_registry()`** — intercepted by `AgentRuntime` at the `hitl` safety level; not exposed to the LLM tool list.

---

#### `train_forecast`

Train the demand forecasting model for a SKU.

**Class:** `TrainForecastTool` (`packages/tools/train_forecast_tool.py`)
**Not registered in `create_tool_registry()`** — invoked directly by `packages/agent/job_executor.py` as a job execution target (job_type=`"train_forecast"`).

---

### Current job_type Registry

| job_type | Tool class | SpecialistRole |
|---|---|---|
| `simulate` | `SimulationTool` | `simulation_optimizer` |
| `inventory_simulation` | `SimulationTool` (alias) | `simulation_optimizer` |
| `optimize` | `OptimizerTool` | `simulation_optimizer` |
| `forecast` | `ForecastTool` | `data_engineer` |
| `train_forecast` | `TrainForecastTool` | `data_engineer` |

`VALID_JOB_TYPES` in `packages/agent/job_executor.py` is the authoritative set. The runtime validates against it before creating DB rows, so an unrecognised `job_type` is rejected before human approval is shown.

---

### How to Add a New job_type

Touch these six locations in order. All must be consistent or the runtime will reject the job at `_prepare_hitl_node`.

1. **`packages/agent/job_executor.py` — `VALID_JOB_TYPES`**
   Add the new string to the `frozenset`. This is the validation gate.

2. **`packages/agent/job_executor.py` — `_build_tool_routes()`**
   Import your new tool class and add `"<job_type>": YourTool` to the returned dict.

3. **`packages/agent/job_executor.py` — `_role_by_type`**
   Add `"<job_type>": "<specialist_role>"` so the executor constructs the correct `ToolContext`.
   Valid roles: `simulation_optimizer`, `data_engineer`.

4. **`packages/tools/job_dispatch_tool.py` — `input_schema` enum**
   Add the new string to `"enum": [...]` so the LLM sees it as a valid choice.
   Update `description` to mention it.

5. **`packages/agent/control/control_agent.py` — system prompt**
   Add a line to the "Job type mapping" block (around line 107) so the LLM knows which
   phrase triggers which `job_type`.

6. **`docs/TOOLS.md` — job_type registry table above**
   Add a row describing the new type and its tool class.

No DB migration is needed — `job_type` is a free-form `VARCHAR(50)`.

---

## Schema Context

`packages/tools/schema_context.py` is the single source of DB schema information for LLM prompts.

- **`load_schema_context() -> str`** — async function called once at API startup (FastAPI lifespan in `apps/api/main.py`). Reads `information_schema.columns` for every table in `ALLOWED_READ_TABLES` and caches the result as a compact text block.
- **`get_schema_context() -> str`** — synchronous accessor that returns the cached string. Free to call from any tool or agent code.

**Rules:**
- Never write a hand-coded table-schema string (`DB_SCHEMA`, `TABLE_COLUMNS`, etc.). Call `get_schema_context()`.
- Never reference column names as string literals in tool code or agent system prompts. If the schema changes, only the Alembic migration and `ALLOWED_READ_TABLES` need to change — everything else derives from them automatically.
- Raw SQL with hardcoded column names belongs in `packages/persistence/` repository functions only. Tool code and agent code must not contain inline SQL.

---

### Demand Analysis Tools

---

#### `profile_demand_data`

Profile demand data quality and statistical distribution for a SKU over a lookback period.

**Class:** `DemandProfileTool` (`packages/tools/demand_profile_tool.py`)
**Requires approval:** No

**Input**

| Field | Type | Required | Description |
|---|---|---|---|
| `sku_id` | string | No | SKU to profile; omit for a cross-SKU summary |
| `lookback_days` | integer ≥ 1 | No | Number of days to look back (default: 90) |

**Output**

| Field | Type | Description |
|---|---|---|
| `sku_id` | string \| null | Echoed SKU (null for cross-SKU) |
| `record_count` | integer | Total demand records in the lookback window |
| `missing_rate` | number | Fraction of records flagged as missing |
| `zero_demand_days` | integer | Days with quantity = 0 |
| `stockout_suspected_days` | integer | Days suspected as stockout (equals missing_rate count) |
| `mean` | number \| null | Mean demand quantity; null if no data |
| `std` | number \| null | Standard deviation; null if no data |
| `cv` | number \| null | Coefficient of variation (std / mean); null if mean is zero |
| `data_quality_score` | number | Score in [0, 1] — 1 = fully clean data |
| `date_range` | object | `{start: string, end: string}` ISO dates |
| `error` | string | Present only on database failure |

**Failure handling**

On database error: returns `{error: "no database connection"}`. Never raises.

**Audit payload:** `{sku_id, lookback_days, record_count}`

---

#### `analyze_demand_trend`

Analyze demand trend direction, slope, and period-over-period growth for a SKU.

**Class:** `DemandTrendTool` (`packages/tools/demand_trend_tool.py`)
**Requires approval:** No

**Input**

| Field | Type | Required | Description |
|---|---|---|---|
| `sku_id` | string | Yes | SKU identifier |
| `lookback_days` | integer ≥ 7 | No | Number of days to look back (default: 90) |
| `granularity` | `"weekly"` \| `"monthly"` | No | Aggregation period (default: `"weekly"`) |

**Output**

| Field | Type | Description |
|---|---|---|
| `sku_id` | string | Echoed SKU |
| `granularity` | string | Echoed granularity |
| `trend_direction` | string | `"up"`, `"down"`, or `"flat"` |
| `trend_slope` | number | Linear regression slope (units per period) |
| `r_squared` | number | Goodness-of-fit for the trend line [0, 1] |
| `period_over_period_growth` | number \| null | Fractional growth from second-to-last to last period |
| `peak_period` | string \| null | Period label with highest demand |
| `trough_period` | string \| null | Period label with lowest demand |
| `periods` | array | `[{period: string, quantity: number}]` aggregated by period |
| `error` | string | Present only on database failure |

**Failure handling**

On database error: returns `{error: "no database connection"}`. Never raises.

**Audit payload:** `{sku_id, lookback_days, granularity}`

---

#### `evaluate_forecast_accuracy`

Compute MAPE, WAPE, and bias for a SKU by comparing forecast history against actual demand.

**Class:** `ForecastAccuracyTool` (`packages/tools/forecast_accuracy_tool.py`)
**Requires approval:** No

**Input**

| Field | Type | Required | Description |
|---|---|---|---|
| `sku_id` | string | Yes | SKU identifier |
| `lookback_days` | integer ≥ 1 | No | Evaluation window in days (default: 90) |

**Output**

| Field | Type | Description |
|---|---|---|
| `sku_id` | string | Echoed SKU |
| `sample_size` | integer | Number of matched forecast–actual pairs |
| `mape` | number \| null | Mean Absolute Percentage Error; null if no positive-actual rows |
| `wape` | number | Weighted Absolute Percentage Error |
| `bias` | number | Average signed error (positive = over-forecast) |
| `coverage` | number | Fraction of demand days that have a corresponding forecast |
| `worst_period` | object \| null | `{date, forecast_qty, actual_qty, error_pct}` for the highest-error day |
| `error` | string | Present only on database failure |

**Failure handling**

On database error: returns `{error: "no database connection"}`. Never raises.

**Audit payload:** `{sku_id, lookback_days, sample_size}`

---

#### `detect_demand_anomalies`

Detect demand spikes, drops, and stockout periods using z-score analysis.

**Class:** `DemandAnomalyTool` (`packages/tools/demand_anomaly_tool.py`)
**Requires approval:** No

**Input**

| Field | Type | Required | Description |
|---|---|---|---|
| `sku_id` | string | Yes | SKU identifier |
| `lookback_days` | integer ≥ 7 | No | Number of days to look back (default: 90) |
| `z_threshold` | number ≥ 0.5 | No | Z-score threshold for spike/drop detection (default: 2.5) |

**Output**

| Field | Type | Description |
|---|---|---|
| `sku_id` | string | Echoed SKU |
| `anomaly_count` | integer | Total number of anomalous days detected |
| `anomalies` | array | `[{date, quantity, z_score, anomaly_type}]`; `anomaly_type` is `"spike"`, `"drop"`, `"stockout"`, or `"missing"` |
| `error` | string | Present only on database failure |

**Failure handling**

On database error: returns `{error: "no database connection"}`. Never raises. Returns empty `anomalies` when fewer than 3 records exist.

**Audit payload:** `{sku_id, lookback_days, z_threshold, anomaly_count}`

---

#### `analyze_seasonality`

Detect weekly and monthly demand seasonality patterns for a SKU.

**Class:** `DemandSeasonalityTool` (`packages/tools/demand_seasonality_tool.py`)
**Requires approval:** No

**Input**

| Field | Type | Required | Description |
|---|---|---|---|
| `sku_id` | string | Yes | SKU identifier |
| `lookback_days` | integer ≥ 28 | No | Number of days to look back (default: 365) |

**Output**

| Field | Type | Description |
|---|---|---|
| `sku_id` | string | Echoed SKU |
| `lookback_days` | integer | Echoed lookback window |
| `record_count` | integer | Number of non-missing demand records used |
| `has_weekly_pattern` | boolean | True if day-of-week CV > 0.15 |
| `has_monthly_pattern` | boolean | True if month-of-year CV > 0.10 |
| `peak_periods` | array of string | Days/months with above-average demand (up to 5) |
| `trough_periods` | array of string | Days/months with below-average demand (up to 5) |
| `seasonality_index` | number | Max of weekly and monthly CVs; 0 if fewer than 28 records |
| `error` | string | Present only on database failure |

**Failure handling**

On database error: returns `{error: "no database connection"}`. Never raises. Returns zeroed seasonality fields when fewer than 14 records exist.

**Audit payload:** `{sku_id, lookback_days, record_count}`

---

#### `analyze_demand_drivers`

Identify top customers driving demand for a SKU and assess customer concentration risk.

**Class:** `DemandDriversTool` (`packages/tools/demand_drivers_tool.py`)
**Requires approval:** No

**Input**

| Field | Type | Required | Description |
|---|---|---|---|
| `sku_id` | string | Yes | SKU identifier |
| `lookback_days` | integer ≥ 7 | No | Number of days to look back (default: 90) |

**Output**

| Field | Type | Description |
|---|---|---|
| `sku_id` | string | Echoed SKU |
| `lookback_days` | integer | Echoed lookback window |
| `total_demand` | number | Total demand quantity for the SKU in the window |
| `top_customers` | array | Up to 5 `{customer_id, segment, total_qty, demand_share, avg_daily_qty}` sorted by demand share |
| `customer_concentration` | number | HHI-like concentration score in [0, 1]; higher = more concentrated |
| `sku_risk_level` | string | `"low"`, `"medium"`, or `"high"` based on concentration |
| `error` | string | Present only on database failure |

**Failure handling**

On database error: returns `{error: "no database connection"}`. Never raises. Returns empty `top_customers` when no affinity data is found.

**Audit payload:** `{sku_id, lookback_days, customer_count}`

---

#### `segment_demand`

Rank SKUs or summarize demand distribution across a dimension (SKU or customer).

**Class:** `DemandSegmentTool` (`packages/tools/demand_segment_tool.py`)
**Requires approval:** No

**Input**

| Field | Type | Required | Description |
|---|---|---|---|
| `dimension` | `"sku"` \| `"customer"` | No | Segmentation dimension (default: `"sku"`) |
| `lookback_days` | integer ≥ 1 | No | Number of days to look back (default: 90) |
| `top_n` | integer 1–50 | No | Maximum segments to return (default: 10) |

**Output**

| Field | Type | Description |
|---|---|---|
| `dimension` | string | Echoed dimension |
| `lookback_days` | integer | Echoed lookback window |
| `total_demand` | number | Total demand across all segments |
| `segments` | array | Up to `top_n` entries of `{id, total_qty, demand_share, trend_direction, cv}` sorted by total quantity descending |
| `error` | string | Present only on database failure |

**Failure handling**

On database error: returns `{error: "no database connection"}`. Never raises.

**Audit payload:** `{dimension, lookback_days, top_n, segment_count}`

---

#### `compare_demand_periods`

Compare total and average demand between two date ranges for a SKU or all SKUs.

**Class:** `DemandCompareTool` (`packages/tools/demand_compare_tool.py`)
**Requires approval:** No

**Input**

| Field | Type | Required | Description |
|---|---|---|---|
| `sku_id` | string | No | SKU identifier; omit for all SKUs |
| `period_a` | object | Yes | `{start: "YYYY-MM-DD", end: "YYYY-MM-DD"}` — baseline period |
| `period_b` | object | Yes | `{start: "YYYY-MM-DD", end: "YYYY-MM-DD"}` — comparison period |

**Output**

| Field | Type | Description |
|---|---|---|
| `sku_id` | string \| null | Echoed SKU (null for all SKUs) |
| `period_a` | object | `{start, end, total_qty, daily_avg, days}` for the baseline period |
| `period_b` | object | `{start, end, total_qty, daily_avg, days}` for the comparison period |
| `change_units` | number | Absolute change in total quantity (period_b − period_a) |
| `change_pct` | number \| null | Percentage change relative to period_a; null if period_a total is 0 |
| `error` | string | Present only on database or date-parse failure |

**Failure handling**

On invalid date format: returns `{error: "Invalid date format: ..."}`. On database error: returns `{error: "no database connection"}`. Never raises.

**Audit payload:** `{sku_id, period_a_start, period_b_end}`

---

## Adding a New Tool

1. Create `packages/tools/<tool_name>_tool.py` implementing the `Tool` protocol (`packages/tools/base.py`).
2. Add the tool name to `_ROLE_TOOL_ALLOWLIST` for every role that should have access.
3. Import and register the tool in `create_tool_registry()` in `packages/tools/__init__.py`.
4. Add the tool's specification to this document under the appropriate category.
5. If the tool queries the database, confirm the tables it touches are in `ALLOWED_READ_TABLES`.
6. Do not hardcode column names. If the tool needs schema information, call `get_schema_context()`. If the tool issues DB queries, put the SQL in a repository function under `packages/persistence/`.
