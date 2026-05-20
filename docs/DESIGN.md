# Technical Design

## Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                         Browser (Next.js)                       │
│  Chat │ Scenarios │ Recommendation │ Approval │ Audit │ KPI    │
│  Reasoning Panel + Tool Call Inspector (Cmd/Ctrl+.)            │
└──────────────────────────┬─────────────────────────────────────┘
                           │ SSE + REST
┌──────────────────────────▼─────────────────────────────────────┐
│                       FastAPI (apps/api)                        │
│  X-Dev-User middleware → REST endpoints + /sessions/{id}/stream │
└──────────────────────────┬─────────────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────────────┐
│ Orchestrator  ──dispatches──►  Specialists (4)                  │
│   ◇ Domain Expert  ◇ Data Engineer  ◇ Sim/Opt  ◇ Evaluator      │
│                           │                                     │
│                           ▼                                     │
│ Tool Layer (schema-driven)                                      │
│   SQL │ Forecast │ Simulation │ Optimization │ Approval │ Audit │
│                           │                                     │
│   ┌───────────────────────┼──────────────────────────┐          │
│   ▼                       ▼                          ▼          │
│ LLMClient            JobRunner                  MemoryStore     │
│ (Claude, embed)     (sync→Celery)              (pgvector)       │
└──────────────────────────┬─────────────────────────────────────┘
                           ▼
       ┌─────────────────────────────────────────┐
       │   PostgreSQL 16 + pgvector              │
       │   sessions / steps / tool_calls /        │
       │   recommendations / approvals /          │
       │   candidates / kpi_scores / memories /   │
       │   audit_log / llm_usage / domain tables  │
       └─────────────────────────────────────────┘
       Operational store only. Analytics → Databricks (Phase 8+).
```

## Design Principles

### Final-Form-First Development

All 10 architectural components must exist from Day 1 with production-grade interfaces. Phases fill in implementations behind stable interfaces — they never add new modules. The MVP runs vertically through every component; stubs return schema-conformant data. **Authentication is the only documented exception** (bolt-on permitted later).

This is encoded operationally as:
- All interface signatures (§Public Interfaces) are normative Day 1. ADR required to change them.
- DB migration 0001 covers Phases 0–9 fields. No additive migrations for new features.
- Stubs are intentionally trivial; tests assert schema conformance, not numerical accuracy.

### Trade-off Resolution is Orchestrator-Owned

Specialists optimize their own slice but never resolve cross-KPI trade-offs unilaterally. The Optimizer returns ≥ 3 Pareto-feasible candidates; the Evaluator scores each candidate per-KPI independently; the Orchestrator applies weights and selects primary + ≥ 2 alternatives at different trade-off positions.

### Multi-Agent Architecture

The Orchestrator coordinates 4 Specialists. The interface is fixed Day 1; implementation downshifts in MVP.

| Stage | Specialist implementation | Behavior |
|---|---|---|
| Phase 1 (MVP) | `PromptBasedSpecialist` — role-prompt + tool subset on shared `LLMClient` | Sequential; LLM routing selects which specialists to invoke per goal |
| Phase 9 (Final) | `AgentBasedSpecialist` — independent context, independent tool registry, possibly different model | True multi-agent with parallel execution |

Future phases split Domain Expert into Forecast / Inventory / Procurement / Production / Cost specialists behind the same Orchestrator interface.

### Orchestrator Routing

Before invoking any specialist, `PhaseOrchestrator` calls `_route_specialists(goal)` — a single LLM call that returns a JSON array of role names needed for the goal. This avoids running the full 4-specialist pipeline for queries that do not require optimization (e.g., data lookups).

**Routing rules (encoded in `_ROUTING_SYSTEM` prompt):**

| Goal type | Roles selected |
|---|---|
| Simple data lookup | `["data_engineer"]` |
| Domain analysis | `["domain_expert", "data_engineer"]` |
| Replenishment / optimisation | `["domain_expert", "data_engineer", "sim_opt", "evaluator"]` |
| Greeting / chit-chat / off-topic | `["none"]` → conversational path |

**Conversational path** (`["none"]` or `[]` returned by routing): the Orchestrator skips all specialists and calls the LLM directly with a brief system prompt. Returns a `Recommendation` with `direct_reply` set and `primary = None`. `sessions.py` short-circuits on `direct_reply` and returns the text directly without attempting to format a recommendation.

**Invariants enforced in code:**
- `sim_opt` and `evaluator` are always selected together — one without the other is invalid.
- Canonical execution order is always preserved: `domain_expert → data_engineer → sim_opt → evaluator`.
- `["none"]` / `[]` routing is intentional — it does **not** trigger the full-sequence fallback.
- Any other routing failure (parse error, invalid roles, LLM error) falls back to the full sequence and logs a warning.

**SSE events:** The routing step emits `step_started` / `step_completed` events with `step_type: "routing"`. The `step_completed` event includes a `selected_roles` field visible in the Reasoning Panel.

## Components

| Component | Day-1 Status | Module |
|---|---|---|
| LLMClient (Claude impl) | Implemented | `packages/agent/llm` |
| Orchestrator | Implemented | `packages/agent/orchestrator` |
| Specialists (4 × PromptBasedSpecialist) | Implemented | `packages/agent/specialists` |
| Tool Layer (registry) | Implemented | `packages/tools` |
| SQL Query Tool | Implemented | `packages/tools/sql` |
| Approval Tool | Implemented | `packages/tools/approval` |
| Audit Log Tool | Implemented | `packages/tools/audit` |
| State Store (repositories) | Implemented | `packages/state` |
| Audit Log (hash chain) | Implemented | `packages/state/audit_log_repo` |
| Evaluator (rule-based) | Implemented | `packages/agent/specialists/evaluator` |
| Human Approval (state machine + UI) | Implemented | `packages/state/approvals` + `apps/web` |
| UI (minimal) | Implemented | `apps/web` |
| Forecast Tool | Stub (28-day MA, NULL-aware) | `packages/tools/forecast` |
| Simulation Tool | `JobRunner` + `InventorySimulator` | `packages/tools/simulation` → `packages/simulation` |
| Optimization Tool | `JobRunner` + `ReplenishmentOptimizer` (OR-Tools) | `packages/tools/optimization` → `packages/optimization` |
| MemoryStore | Stub (write-only) | `packages/memory` |
| JobRunner | InProcess (sync) + AcaJobsRunner (prod) | `packages/agent/job_runner` |
| KPI domain | Implemented | `packages/domain/kpi.py` |

**Deferred:** Python Analysis Tool, Report Tool (LLM + SQL Tool covers ad-hoc analysis; Chat GFM Markdown covers report rendering).

## Monorepo Layout

```
apps/
  web/                   # Next.js (npm)
  api/                   # FastAPI (uv)
packages/
  agent/                 # Orchestrator + Specialists + LLMClient + JobRunner
  tools/                 # Schema-driven Tool registry + concrete tools
  domain/                # KPI formulas, safety stock, reorder point
  simulation/            # Simulator implementations behind Simulator interface
  optimization/          # Optimizer implementations behind Optimizer interface
  prediction/            # Predictor implementations behind Predictor interface
  memory/                # MemoryStore (pgvector) behind MemoryStore interface
  state/                 # Repositories over all DB tables
  schemas/               # Pydantic (source of truth)
  schemas-ts/            # Zod (generated from Pydantic; CI equivalence)
infra/
  terraform/
    image-build/         # Build container images
    acr-push/            # Tag + push to ACR
    aca/                 # Azure Container Apps deployment
    shared/              # Postgres / Key Vault / OpenAI / Monitor / networking
    modules/             # Reusable modules
  compose/               # Docker Compose V2 (no version: field)
data/
  sample/                # Operational CSVs (agent-accessible)
  sample/ground_truth/   # Generator parameters (agent-FORBIDDEN)
  fixtures/              # Test fixtures + vcrpy cassettes
config/
  risk_thresholds.yaml
  kpi_weights.csv
  kpi_weights_overrides.csv
scripts/
  generate_sample_data.py
  seed_db.py
  seed_users.py
  seed_llm_pricing.py
  _db_url.py                 # shared DATABASE_URL resolution for seed scripts
tests/
.github/workflows/
docs/
```

### Workspace Tooling

- Python: `uv` workspace; root `pyproject.toml` declares `tool.uv.workspace.members = ["apps/api", "packages/*"]`.
- TypeScript: `npm workspaces` covering `apps/web` and `packages/schemas-ts`.
- Schema parity: `packages/schemas` (Pydantic) is the source of truth; `packages/schemas-ts` (Zod) is generated via codegen with a CI equivalence check.

### Local Docker Compose (`infra/compose/`)

- **API** and **web** images both use **monorepo root** as build context (not `apps/api` or `apps/web` alone).
- **Web** must run the Next.js `standalone` server from [`apps/web/Dockerfile`](apps/web/Dockerfile). A Phase 0 placeholder that returned only the text `ok` on port 3000 is **removed** and must not be reintroduced.
- Agent runbook with verification commands and forbidden patterns: **AGENTS.md § Web Docker image — anti-regression**.

## Phase Progression

Phases replace stub implementations behind stable interfaces. They never add new modules. Phases 2–9 are reorderable based on business priority and real-data availability. Phase 0 and Phase 1 ship as a single deliverable.

| Phase | Name | Primary Work | Interface |
|---|---|---|---|
| 0 | Repository Foundation | Monorepo scaffold, all interface contracts, migration 0001, ADRs, Terraform skeleton, Docker Compose, observability | Establishes interfaces |
| 1 | Decision Copilot (Vertical-Slice MVP) | Orchestrator + Specialists wired, SQL Tool, Evaluator, Approval + UI; Forecast / Sim / Opt / Memory stubbed | Fills in stubs |
| 2 | Real Simulator | Stub → real Python simulation; move to ACA Jobs | Unchanged |
| 3 | Real Optimizer | Stub → OR-Tools / PuLP; move to ACA Jobs | Unchanged |
| 4 | Approval Workflow Expansion | Revision-request loop, notifications, approver roles, budget ceilings | Unchanged |
| 5 | Job Orchestration | Sync → Celery + Redis on ACA | Unchanged |
| 6 | Real Predictor | Stub → scikit-learn / statsmodels + Databricks training | Unchanged |
| 7 | Memory & Learning Loop | Stub → pgvector retrieval; weight-vector learning loop | Unchanged |
| 8 | Semi-Autonomous Execution | Risk-classified auto-execution policy | Unchanged |
| 9 | Business Decision OS Completion | Domain Expert split into Forecast / Inventory / Procurement / Production / Cost | Unchanged |

## Trade-off Handling

| Component | Trade-off responsibility |
|---|---|
| Domain Expert | Surfaces domain-level tensions ("lowering safety stock saves cost but raises stockout risk for Critical SKUs") |
| Simulator / Optimizer | Produces ≥ 3 Pareto-feasible candidates; never a single forced winner |
| Evaluator | Scores each candidate against every KPI independently — `KpiScore[]` per candidate, no collapsed weighted total |
| Orchestrator | Applies weights and picks primary + alternatives at different trade-off positions |
| Human Approval | Reviews trade-off; can request revision with shifted weights |
| Memory Store | Persists user policy weight vectors (`memories.type = user_policy`) to learn user preferences over time |

**Five-step mechanism:**

1. Optimizer returns ≥ 3 feasible candidates under hard constraints (MOQ, Lead Time, Supplier Capacity, Budget, Critical SKU).
2. Evaluator produces per-KPI scores for each candidate.
3. Orchestrator applies weights in resolution order: `session_goal → memory (Phase 7+) → overrides CSV → global default`.
4. Orchestrator selects primary via weighted utility or Pareto-dominance filter, then picks 2 alternatives at different trade-off positions.
5. Recommendation payload includes primary, alternatives, per-KPI scores, weight vector used, rationale, and "what you give up" against each alternative.

## Public Interfaces (Normative Day 1)

All signatures below are locked. ADR required for any change.

### LLMClient

```python
class LLMMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    name: str | None = None
    tool_call_id: str | None = None

class LLMToolSpec(BaseModel):
    name: str
    description: str
    input_schema: dict

class LLMUsage(BaseModel):
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    total_cost_usd: Decimal

class LLMResponse(BaseModel):
    text: str
    tool_calls: list[dict]
    finish_reason: Literal["stop", "tool_use", "length", "error"]
    usage: LLMUsage
    model: str
    request_id: str
    latency_ms: int

class LLMClient(Protocol):
    async def complete(self, messages, tools=None, temperature=0.0, max_tokens=4096,
                       prompt_cache=True, agent_step_id=None, specialist_role=None) -> LLMResponse: ...
    async def stream(self, messages, tools=None, temperature=0.0, max_tokens=4096,
                     prompt_cache=True, agent_step_id=None, specialist_role=None) -> AsyncIterator[LLMStreamEvent]: ...
    async def embed(self, texts, model="text-embedding-3-small", agent_step_id=None) -> list[list[float]]: ...
```

Every call writes one `llm_usage` row in the same DB transaction as `agent_step_id` (when present). No bypass path — wrappers live inside `LLMClient`, not at the call site.

### Tool

```python
class ToolContext(BaseModel):
    session_id: UUID
    agent_step_id: UUID
    specialist_role: SpecialistRole
    actor: str
    correlation_id: UUID

class ToolResult(BaseModel):
    output: dict
    audit_payload: dict

class Tool(Protocol):
    name: str
    description: str
    input_schema: dict
    output_schema: dict
    requires_approval: bool
    async def handle(self, input: dict, ctx: ToolContext) -> ToolResult: ...
```

Tool registry: `ToolRegistry.register(tool) / get(name) / list_for_role(role)`. Each `handle` auto-writes one `tool_calls` + one `audit_log` row in the same transaction.

### JobRunner

```python
class JobSpec(BaseModel):
    kind: Literal["simulation", "optimization", "forecast_batch", "report"]
    payload: dict
    idempotency_key: str
    timeout_seconds: int = 300

class JobHandle(BaseModel):
    job_id: UUID
    status: Literal["queued", "running", "succeeded", "failed", "cancelled"]
    submitted_at: datetime

class JobResult(BaseModel):
    job_id: UUID
    status: Literal["succeeded", "failed", "cancelled"]
    output: dict | None
    error: str | None
    duration_ms: int

class JobRunner(Protocol):
    async def submit(self, spec: JobSpec, ctx: ToolContext) -> JobHandle: ...
    async def status(self, job_id: UUID) -> JobHandle: ...
    async def result(self, job_id: UUID, wait: bool = False) -> JobResult: ...
    async def cancel(self, job_id: UUID) -> None: ...
```

Phase 2: `InProcessJobRunner` (dev/CI, synchronous) and `AcaJobsRunner` (production, manual ACA Job trigger). Phase 5: `CeleryJobRunner`. Callers never change. `JobSpec` / `JobHandle` / `JobResult` live in `packages/schemas/job.py`.

### Simulator

```python
class SimulationInput(BaseModel):
    sku_id: str
    order_qty: float
    horizon_days: int = 90

class SimulationOutput(BaseModel):
    sku_id: str
    ending_on_hand: float
    stockout_days: int
    mean_lead_time_days: int
    daily_on_hand: list[float] | None = None

class SimulationContext(BaseModel):
    session_id: UUID | None = None
    db_session: AsyncSession | None = None   # injected at runtime

class Simulator(Protocol):
    async def run(self, input: SimulationInput, ctx: SimulationContext) -> SimulationOutput: ...
```

Phase 2 implementation: `InventorySimulator` in `packages/simulation/inventory.py`. `SimulationTool` delegates to `JobRunner` (`kind=simulation`); tool JSON output matches Phase 1 (`to_tool_dict()`).

### Optimizer

```python
class OptimizationInput(BaseModel):
    sku_id: str
    horizon_days: int = 90
    max_stockout_days: int = 30

class CandidatePlan(BaseModel):
    action: dict
    simulation: dict
    total_supply_chain_cost: float
    constraints_satisfied: list[str]
    constraints_violated: list[str]

class OptimizationOutput(BaseModel):
    candidates: list[CandidatePlan]

class OptimizationContext(BaseModel):
    session_id: UUID | None = None
    agent_step_id: UUID | None = None
    db_session: AsyncSession | None = None
    job_runner: JobRunner | None = None

class Optimizer(Protocol):
    async def run(self, input: OptimizationInput, ctx: OptimizationContext) -> OptimizationOutput: ...
```

Phase 3 implementation: `ReplenishmentOptimizer` in `packages/optimization/replenishment.py` (OR-Tools CP-SAT over MOQ multiples, nested `kind=simulation` jobs). `OptimizationTool` delegates to `JobRunner` (`kind=optimization`).

### MemoryStore

```python
class Memory(BaseModel):
    id: UUID
    scope: str                # "global" | f"sku:{sku}" | f"user:{user_id}"
    type: Literal["decision", "forecast_error", "user_policy", "failure_case"]
    content: str
    embedding: list[float] | None       # 1536d
    metadata: dict
    created_at: datetime

class MemoryQuery(BaseModel):
    scope: str | None = None
    type: Literal["decision", "forecast_error", "user_policy", "failure_case"] | None = None
    query_text: str | None = None
    k: int = 5
    min_similarity: float = 0.0

class MemoryStore(Protocol):
    async def write(self, memory: Memory) -> UUID: ...
    async def search(self, query: MemoryQuery) -> list[tuple[Memory, float]]: ...
    async def get(self, id: UUID) -> Memory | None: ...
```

Day 1: write-only; `search` returns `[]`. Phase 7 enables pgvector retrieval.

### Orchestrator + Specialist

```python
class SessionGoal(BaseModel):
    text: str
    weight_override_json: dict | None = None

class SpecialistTask(BaseModel):
    task_id: UUID
    instruction: str
    context_payload: dict
    allowed_tools: list[str]

class SpecialistResult(BaseModel):
    task_id: UUID
    output: dict
    tool_calls_made: list[UUID]
    status: Literal["completed", "failed", "needs_input"]
    error: str | None = None

class Specialist(Protocol):
    name: str
    role: SpecialistRole  # orchestrator | domain_expert | data_engineer | sim_opt | evaluator
    async def run(self, task: SpecialistTask, ctx: ToolContext) -> SpecialistResult: ...

class Orchestrator(Protocol):
    async def run(self, session_id: UUID, goal: SessionGoal) -> Recommendation: ...
    async def resume(self, session_id: UUID, approval_id: UUID) -> Recommendation: ...
```

### Approval State Machine

```
pending        → approved | rejected | needs_revision | expired
needs_revision → (terminal; spawns NEW approvals row in pending, linked via parent_approval_id)
rejected       → (terminal)
approved       → (terminal)
expired        → (terminal; sweep job sets when pending exceeds approval_ttl_seconds, default 86400)
```

A revision loop never mutates a closed row. It creates a new `approvals` row with `parent_approval_id` set, preserving the audit chain.

### Recommendation Schema

```python
class KpiScore:
    name: str
    value: float
    unit: str
    direction: Literal["higher_better", "lower_better"]

class Candidate:
    id: str
    action: dict
    kpi_scores: list[KpiScore]
    constraints_satisfied: list[str]
    constraints_violated: list[str]    # always [] for feasible candidates

class TradeoffExplanation:
    weight_vector: dict[str, float]
    weight_source: Literal["default", "user_policy", "session_goal", "critical_sku"]
    primary_vs_alternative: list[dict]

class Recommendation:
    primary: Candidate
    alternatives: list[Candidate]      # ≥ 2 at different trade-off positions
    tradeoff: TradeoffExplanation
    rationale: str
    risk_level: Literal["low", "medium", "high"]
    requires_approval: bool
```

## Data Flow

A single session's lifecycle:

```
1. User opens /chat/[sessionId] → POST /api/v1/sessions returns session_id.
2. User submits prompt → POST /api/v1/sessions/{id}/messages.
3. FastAPI invokes Orchestrator.run(session_id, goal). One transaction per agent_step.
4. Orchestrator dispatches Specialists sequentially (PromptBasedSpecialist) — role prompt + tool subset.
5. Each tool invocation writes tool_calls + audit_log rows (hash chained) and emits SSE tool_called / tool_completed events.
6. LLMClient writes llm_usage rows inside its middleware, never at the call site.
7. Orchestrator collects candidates (≥ 3) → Evaluator scores per-KPI → Orchestrator selects primary + 2 alternatives → emits SSE recommendation_ready.
8. If requires_approval, awaiting_approval event fires; UI surfaces in Approval Queue.
9. Human approves / rejects / requests revision. Revision → new approvals row → Orchestrator.resume() re-runs with shifted weights.
10. Outcome persisted; memory writes record weight vector for Phase 7+ learning.
```

## API Design

FastAPI v1 endpoints (skeletons return 501 in Phase 0 where logic is not ready):

```
# Sessions
POST   /api/v1/sessions
GET    /api/v1/sessions
GET    /api/v1/sessions/{id}
POST   /api/v1/sessions/{id}/messages
GET    /api/v1/sessions/{id}/stream                # SSE

# Recommendations
GET    /api/v1/recommendations/{id}
GET    /api/v1/sessions/{id}/recommendations

# Approvals
GET    /api/v1/approvals                           # ?status=pending by default
GET    /api/v1/approvals/{id}
POST   /api/v1/approvals/{id}/decision             # {decision, reason?, weight_override?}

# Scenarios
GET    /api/v1/sessions/{id}/scenarios
GET    /api/v1/scenarios/{id}

# Audit
GET    /api/v1/audit                               # filters: session_id, agent, tool, status, from, to

# KPI Dashboard
GET    /api/v1/kpi/trends                          # filters: sku, warehouse, kpi, from, to
GET    /api/v1/kpi/llm-cost                        # daily/weekly cost rollup

# Settings (Phase 4+ for PATCH)
GET    /api/v1/settings/weights
PATCH  /api/v1/settings/weights
GET    /api/v1/settings/budgets
PATCH  /api/v1/settings/budgets

# Health
GET    /healthz
GET    /readyz
```

Auth: `X-Dev-User` header in MVP; OIDC bearer token after Entra ID bolt-on.

### SSE Event Payloads

Defined in `packages/schemas` (Pydantic) and `packages/schemas-ts` (Zod):

```typescript
type SseEvent =
  | { type: "step_started";        step_id; specialist_role; step_type; started_at }
  | { type: "step_completed";      step_id; specialist_role; duration_ms; output_preview; tokens; cost_usd }
  | { type: "tool_called";         tool_call_id; step_id; tool_name; input; specialist_role }
  | { type: "tool_completed";      tool_call_id; tool_name; duration_ms; output; executed_query?; status; error? }
  | { type: "recommendation_ready"; recommendation_id; risk_level; requires_approval }
  | { type: "awaiting_approval";   approval_id; recommendation_id; expires_at }
  | { type: "done";                session_id; reply }               // chat reply delivery
  | { type: "error";               code; message; recoverable }
```

- `type: "done"` carries the final assistant reply in `reply`. The Chat UI subscribes to the stream after POST `/messages` and appends the reply when this event arrives.
- `type: "error"` is displayed directly in the Chat UI as a red error bubble. Errors must never be swallowed silently — they must propagate to the user.

SSE reconnect: client sends `Last-Event-ID`; server replays from `audit_log` by `session_id` after that ID.

## Storage Design

### Strategy

Single PostgreSQL + pgvector store for all transactional system data. Large analytics data is separated to **Databricks Lakehouse** from Day 1 architecture (planned, Phase 8+ implementation).

### Migration 0001 — Column-Level DDL

System tables (all with `CHECK` constraints enforcing state enums, FK cascades, and indexes; full DDL maintained in `packages/state/migrations/0001_initial.sql`):

- `users` (PK `id`, `handle UNIQUE`)
- `decision_sessions` (FK `user_id`, `status CHECK IN ('active','awaiting_approval','completed','failed','cancelled')`, `weight_vector_json JSONB`)
- `agent_steps` (FK `session_id` cascade, `specialist_role`, `step_type`, `status`)
- `tool_calls` (FK `session_id` + `step_id` cascade, `audit_hash` denormalized pointer)
- `recommendations` (FK `session_id`, `primary_candidate_id`, `alternative_candidate_ids UUID[]`, `weight_source CHECK`, `risk_level CHECK IN ('low','medium','high')`)
- `approvals` (FK `recommendation_id`, `status CHECK`, `parent_approval_id` self-FK, `expires_at`)
- `candidates`, `kpi_scores`, `scenarios`, `simulation_results`, `evaluations`
- `memories` (`embedding vector(1536)` with ivfflat cosine index)
- `prediction_errors`
- `audit_log` (`audit_hash TEXT UNIQUE`, `prev_audit_hash`)
- `llm_pricing` (versioned per-1k rates with `effective_from` / `effective_to`)
- `llm_usage` (FK `pricing_version → llm_pricing(id)`)

Operational domain tables:

- `sku_master` (PK `sku`, `is_critical BOOLEAN`, `parent_sku` self-FK, supplier / MOQ / lot / cost, lifecycle dates)
- `inventory` (PK `(sku, warehouse, as_of_date)`)
- `demand_history` (PK `(sku, date)`, `units INT NULL` for missing-data injection)
- `supply` (PK `(sku, supplier_id)`, lead-time + capacity)
- `cost` (PK `sku`, holding / stockout / order)
- `customers` (PK `customer_id`, `type CHECK IN ('large','small','spot')`)

**SQL Tool allowlist:** `sku_master`, `inventory`, `demand_history`, `supply`, `cost`, `customers`. No other table is readable by the SQL Tool. Ground-truth tables never exist in the database.

### Access Layer

- ORM: SQLAlchemy 2.x async + Alembic for migrations.
- Driver: asyncpg with connection pool.
- Repository pattern in `packages/state/` for swap-in optionality.
- Transaction boundary: one Orchestrator step = one transaction. `session_id` is the FK spine.

### Analytics Data Path (Phase 8+)

| Layer | Tool |
|---|---|
| Storage | Azure Data Lake Storage Gen2 (Delta Lake) |
| Compute | Databricks workspace (US East 2) |
| Ingestion | Scheduled CDC export from PostgreSQL (Debezium or Azure DMS) |
| Schema | Bronze (raw) → Silver (cleaned) → Gold (analytics-ready) |
| Access | Predictor / training jobs read Gold; production agent reads PostgreSQL only |

Phase 6 Predictor (real) reads pre-computed features written **back** from Databricks into PostgreSQL. The production agent never queries Databricks directly.

## KPI Reference

Single source of truth: `packages/domain/kpi.py`. Operates over horizon `H = 90 days`. Used by both Evaluator and Simulator — never duplicated.

| KPI | Formula | Unit | Direction |
|---|---|---|---|
| Service Level | `days(on_hand >= demand) / H` | % | higher_better |
| Fill Rate | `Σ units_filled / Σ units_demanded` | % | higher_better |
| Stockout Rate | `days(on_hand=0 AND demand>0) / H` | % | lower_better |
| Inventory Turnover | `Σ units_sold / avg(on_hand) * 365/H` | turns/year | higher_better |
| Days of Inventory | `avg(on_hand) / avg(daily_demand)` | days | lower_better |
| Excess Inventory | `max(0, avg(on_hand) - safety_stock - lead_time_demand)` | units | lower_better |
| Working Capital | `avg(on_hand) * unit_cost_usd` | USD | lower_better |
| Total Supply Chain Cost | `Σ (holding + stockout + order_cost)` | USD | lower_better |

### Default KPI Weight Vectors

Two CSVs in `config/`:

- `config/kpi_weights.csv` — global default (single row).
- `config/kpi_weights_overrides.csv` — per-SKU sparse overrides.

Initial global defaults (sum = 1.0): `service_level=0.25`, `fill_rate=0.10`, `stockout_rate=0.15`, `inventory_turnover=0.05`, `days_of_inventory=0.05`, `excess_inventory=0.10`, `working_capital=0.15`, `total_cost=0.15`. Critical SKU overrides seed with `service_level=0.50` (others renormalized). Runtime resolution: session_goal → memory (Phase 7+) → overrides CSV → global default.

## Risk Classification

Three tiers; all thresholds live in `config/risk_thresholds.yaml` and are swappable per environment.

- **high:** any of — purchase amount > $10,000 / order qty > 3× avg monthly demand / `is_critical=true`.
- **medium:** any of — purchase amount > $2,000 / order qty > 1.5× avg monthly demand / lead time > 30 days / supplier concentration > 80% for the SKU.
- **low:** otherwise.

## Stub Behavior (Day 1)

| Component | Behavior |
|---|---|
| Forecast Tool | 28-day moving average over `demand_history`, NULL-aware (skipped, not zeroed). `model_version="moving_avg_v1"`. |
| Simulation Tool | Same deterministic projection via `InventorySimulator` / `JobRunner`; mean lead time only. |
| Optimization Tool | MOQ multiples `{0,…,5×MOQ}` via nested simulation jobs; OR-Tools CP-SAT picks min-cost feasible; return top 3 by `total_supply_chain_cost` (relax if &lt;3). |
| MemoryStore | `write` persists; `search` returns `[]`. |

Tests assert schema conformance, not numerical accuracy. Smart stubs hide schema mismatches; trivial stubs force the contract to be exercised on every code path from Day 1.

## Orchestrator Runtime

### Error Handling

**Design principle: errors are visible, never hidden.**

- Missing config (API keys, packages, required env vars) raises `RuntimeError` immediately at call site — no silent fallback to stubs or no-ops.
- Fail-silent fallbacks are prohibited. Code must never degrade silently to a stub when a real implementation was expected. See `AGENTS.md § Prohibitions`.
- Errors always propagate to the user: SSE `type: "error"` events are displayed as red error bubbles in the Chat UI. The Reasoning Panel is supplemental, not the primary error surface.

Runtime error flows:
- Specialist failure: 2 retries with exponential backoff (1s, 4s). On 3rd, fail step + session, emit SSE `error`, display in Chat.
- Tool failure: bubble to Specialist (retry / alternative / fail upward).
- LLM 429: respect `Retry-After`, retry once.
- Phase 4+ budget hard ceiling: no retry, fail immediately with `budget_exceeded`.

### Concurrency / Idempotency

- One transaction per `agent_step`.
- `JobSpec.idempotency_key = f"{session_id}:{agent_step_id}:{kind}"` — duplicate submits return existing `JobHandle`.
- `decision_sessions` uses optimistic concurrency; conflicting writes raise and the orchestrator retries the step idempotently.

## Sample Data Generation

### Composition

30 SKUs over 24 months of daily history, with overlapping buckets:

| Bucket | Count |
|---|---|
| Best-seller | 5 |
| Normal | 10 |
| Slow mover | 5 |
| Strong seasonal | 5 |
| Critical SKU (`is_critical=true`) | 5 |
| Series parent + derivative | 6 |
| Customizable variant | 3 |
| New (cold-start, < 6mo) | 3 |
| EOL (declining) | 2 |
| Overstock at t=now | 4 |
| Stockout at t=now | 3 |
| Spot-purchase customers | 4 |
| Large account dominant | 3 |

### Demand Model

```
daily_demand = max(0, round(base_demand * seasonality * trend * promo_spike + noise))
```

| Term | Definition |
|---|---|
| `base_demand` | bucket-driven: best=80, normal=15, slow=2, seasonal=20, EOL=linearly decaying, new=NULL before `lifecycle_start_day` |
| `seasonality` | `1 + amplitude * sin(2π * (t - phase_days) / 365) + holiday_spike(t)`. Amplitude: seasonal=0.6, others=0.05. Holiday spike: +50% in last 2 weeks of Dec for seasonal SKUs |
| `trend` | EOL: `max(0, 1 - 0.001 * (t - trend_start_day))`. Others: 1.0 |
| `promo_spike` | spot-customer-dominant SKUs: probability 0.02/day, multiplier `Uniform(5,10)`; else 1.0 |
| `noise` | Negative Binomial centered at 0 with dispersion = `base_demand * 0.3` |

Lead time: `LogNormal(μ = ln(mean_lt), σ = 0.3)`. Bucket means: domestic=7d, overseas=21d, customizable=45d.

Initial inventory: `overstock` = `daily_demand * 150`; `stockout` = 0 on-hand + 1–3 backorder rows; `normal` = `daily_demand * (lead_time_mean_days + 14)`.

### Generation Workflow

```
data/sample/ground_truth/sku_parameters.csv         # generator inputs (FORBIDDEN to agent)
data/sample/ground_truth/customer_parameters.csv
data/sample/ground_truth/README.md
scripts/generate_sample_data.py                      # ground_truth → operational CSVs
data/sample/{sku_master,inventory,demand_history,supply,cost,customers}.csv
scripts/seed_db.py                                   # operational CSVs → Postgres
scripts/seed_users.py                                # dev-user row (MVP auth header)
scripts/seed_llm_pricing.py                          # llm_pricing rates (see ADR)
```

One-command local bootstrap: `make seed-all` (migrate + generate/load CSVs + users + llm_pricing). Operational CSV reload only: `make seed`. Idempotent reload of sample tables only; never loads `ground_truth/`.

### Random Seed

`random.seed(42)` and `numpy.random.seed(42)` fixed at module load. CLI flag `--seed N` overrides for alternate datasets. ADR `docs/adr/2026-05-17-sample-data-generation.md` records rationale.

### Missing Data Injection

3 SKUs (deterministic under seed 42) receive intentional NULLs in `demand_history`:
- 2% of rows per target SKU at random positions.
- One target SKU additionally has a 7-day consecutive NULL block, simulating a system outage.
- Ground-truth retains complete values; NULL mask applied only when writing operational `demand_history.csv`.

### Ground-Truth Access Prevention

Two-layer enforcement:
1. **Path convention:** `data/sample/ground_truth/` is excluded from the agent's working corpus. Documented in `AGENTS.md` and `data/sample/ground_truth/README.md`.
2. **SQL Tool allowlist:** SQL Tool only accepts queries against operational tables. Ground-truth never enters PostgreSQL.

## Web UI Design

### Stack

| Layer | Choice |
|---|---|
| Framework | Next.js (App Router) + TypeScript + `npm` |
| Components | shadcn/ui + Radix + Tailwind CSS |
| Charts | Recharts (radar + parallel coordinates) |
| Server state | TanStack Query |
| Client state | Zustand |
| URL state | search params (filters / sort / pagination / tab / search) |
| Form state | React Hook Form + Zod |
| LLM streaming | Vercel AI SDK with Anthropic Claude provider |
| Realtime | SSE for Approval queue + Audit timeline + Chat reasoning panel |
| Theme | Light only at launch; dark theme tokens defined |
| Accessibility | WCAG 2.1 AA |
| Currency display | `Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' })` |
| Markdown | `react-markdown` + `remark-gfm` + `rehype-sanitize` + KaTeX + Mermaid (lazy-loaded) |

### Day-1 Screens

| Screen | Purpose |
|---|---|
| Chat | English UI and English GFM Markdown agent responses; side Reasoning Panel |
| Scenario Comparison | Radar + parallel coordinates for ≥ 3 candidates; primary highlighted |
| Recommendation Detail | Primary + alternatives + TradeoffExplanation + rationale + risk badge |
| Approval Queue | Risk-badged list with trade-off summary; approve / reject / revise with weight-vector editor |
| Audit Timeline | session_id / agent / tool / status filters; JSON diff; token+cost summary; replay link (Phase 5+) |
| KPI Dashboard | Service Level / Inventory Cost / Stockout / Working Capital trends + LLM Cost Trend panel |
| Settings / Policies | Weight defaults, Critical SKU flags, budget thresholds (Phase 4+) |

### Engineer Debug Visibility (permanent, first-class)

- Built into end-user screens behind `Cmd/Ctrl + .` toggle; never a separate dev tool. Collapsed by default in production; never removed.
- **Reasoning Panel** beside Chat: Active Specialist banner, Orchestrator routing log, Step timeline, live status pill.
- **Tool Call Inspector** per tool: input JSON, executed SQL (syntax-highlighted), output JSON, copy / open-in-audit actions, error + stack trace on failure.
- **Audit Timeline enhancements:** agent / tool / status filters, JSON diff, token+cost summary.

## LLM Cost & Token Tracking

Every LLM call recorded at the `LLMClient` interface boundary — no bypass path.

- **`llm_usage` table:** `session_id`, `agent_step_id`, `specialist_role`, `provider`, `model`, `operation`, tokens (input / output / cache read / cache write), per-axis costs and `total_cost_usd`, `pricing_version`, `latency_ms`, `request_id`, `created_at`.
- **`llm_pricing` table:** versioned per-1k-token rates (`effective_from` / `effective_to`); `pricing_version` recorded on each `llm_usage` so historical rows survive pricing changes.
- Cost computed at write time, stored in the same DB transaction as the parent `agent_step`. Failed calls still record consumed tokens. Anthropic prompt-cache fields populated from response headers.

### UI Surfaces

| Surface | Behavior |
|---|---|
| Reasoning Panel header | Live "tokens · USD" counter via SSE |
| Tool Call Inspector | Per-step token + cost line |
| Audit Timeline | Tokens (in/out/cached) + cost columns; filter by model and Specialist |
| KPI Dashboard | LLM Cost Trend panel — daily/weekly USD by Specialist and model vs prior period |
| Settings / Policies | Per-session / daily / monthly budget thresholds (Phase 4+) |

### Budget Enforcement

- Day 1: observation only.
- Phase 4+: soft ceiling (warning + UI notification) and hard ceiling (refuse new LLM calls with clear error in Chat). Per-session / per-day / per-month independent.

### Cost-Saving Defaults (Day 1)

- Anthropic prompt caching for stable system prompts.
- `temperature=0` everywhere (deterministic + cacheable).
- Specialist prompts segmented for high cache hit rate.
- Aggregation / summarization before LLM (no raw rows).
- `vcrpy` cassettes block real API calls in unit / integration tiers.

### `llm_pricing` Seed Strategy

Migration 0001 inserts rows for `claude-sonnet-4-6`, `claude-opus-4-7`, `text-embedding-3-small` with `effective_from = 2026-05-17`, `effective_to = NULL`. Verified per-1k USD rates and source URLs recorded in ADR `docs/adr/2026-05-17-llm-pricing-seed.md`.

## Compute Platform for Heavy Workloads

| Workload | Platform | Phase |
|---|---|---|
| Day-1 lightweight sync (< 5s) | FastAPI container (ACA), async in-process | Phase 1 |
| Mid-weight simulation / optimization | Azure Container Apps Jobs (manual / event / scheduled) | Phase 2–3 |
| Background job queue | Celery + Redis (Azure Cache for Redis) on ACA | Phase 5 |
| Predictor batch training | Databricks Jobs (MLflow) | Phase 6 |
| Predictor batch inference | Databricks Jobs writing features back to PostgreSQL | Phase 6 |
| Predictor realtime (lightweight) | FastAPI in-process | Phase 6 |
| Heavy ETL / analytics | Databricks Jobs / Databricks SQL | Phase 8+ |

All compute platforms share **ACR + Key Vault + Managed Identity** boundary in Terraform `shared/`. `JobRunner` interface unchanged across phases — only the implementation swaps.

## Security Design

- TLS enforced on all DB connections (`sslmode=require`).
- DB firewall restricted to GitHub Actions OIDC ranges + developer IPs.
- `audit_log` hash chain (`audit_hash` references `prev_audit_hash`) for tamper-evidence.
- LLM context sanitizer ensures raw rows never sent to Claude — summaries / aggregates only.
- Secrets via Azure Key Vault + Managed Identity at runtime; `.env.example` only in repo.
- SQL Tool allowlist enforced at the tool boundary.
- HTML output sanitized via `rehype-sanitize` before rendering.
- No PII in sample data; synthetic IDs.

### MVP Authentication

- Phase 1: `X-Dev-User` header middleware injects `user_id = "dev-user"`; seeded user row.
- Bolt-on later: Microsoft Entra ID OIDC bearer tokens behind the same middleware; `dev-user` becomes fallback only when `APP_ENV=dev`.
- Multi-session per user supported Day 1; left sidebar lists sessions; URL `/chat/[sessionId]`.

### CORS

- `allow_origins`: `["http://localhost:3000"]` in dev; deployed Container App FQDN in prod (env-injected).
- `allow_credentials=True`; methods `GET/POST/PATCH/DELETE/OPTIONS`; headers `*`.
- SSE endpoint excluded from credential requirement; session token in query param.

## Observability Design

- `structlog` JSON logs (app) + OpenTelemetry traces + Langfuse generation events (LLM).
- Sink: Azure Monitor / Application Insights provisioned by Terraform `shared/`.
- OTel span attributes per LLM call: `llm.provider`, `llm.model`, `llm.input_tokens`, `llm.output_tokens`, `llm.total_cost_usd`. LLM spans linked to parent `agent_step` span.
- Engineer-debug visibility on screen complements logs — both are first-class.

## Deployment Design

### Infrastructure Policy

- Azure region: **US East 2** for all resources.
- Backup disabled for MVP (explicit cost optimization; reversible; re-enable triggered by regulatory / DR requirement).
- Easy teardown: all Terraform resources `prevent_destroy = false`; no resource locks; `terraform destroy` works cleanly.

### Terraform Pipeline Split

| Stage | Path | Purpose |
|---|---|---|
| 1 | `infra/terraform/image-build/` | Build container images |
| 2 | `infra/terraform/acr-push/` | Tag + push to ACR |
| 3 | `infra/terraform/aca/` | Azure Container Apps deployment; receives image tag |
| Cross-stage | `infra/terraform/shared/` | Postgres / Key Vault / OpenAI / Monitor / networking (stateful) |
| Library | `infra/terraform/modules/` | Reusable modules |

Each stage has independent state and lifecycle.

### CI/CD

- GitHub Actions under `.github/workflows/`: `lint-test.yml`, `terraform-plan.yml`, `deploy.yml`.
- Azure OIDC federated credentials (no long-lived secrets):
  - `repo:eimamura/<repo>:ref:refs/heads/main` for prod deploys.
  - `repo:eimamura/<repo>:pull_request` for PR plans.
  - `repo:eimamura/<repo>:environment:prod` for environment-gated deploys.
- Least-privilege RBAC: `Contributor` on RG, `AcrPush` on ACR, `Key Vault Secrets User` granted to runtime Managed Identity (not the GHA SP).
- `azure/login@v2` with `client-id` + `tenant-id` + `subscription-id` only.
- Pipeline: lint/test → image-build → acr-push → terraform plan/apply (shared) → terraform plan/apply (aca).
- PRs run lint/test + terraform plan; merges to `main` run full deploy chain.

### Branch Protection (`main`)

- Required reviewers: 1 (single-developer mode; tightened on team expansion).
- Required status checks: `lint-test`, `terraform-plan`.
- No force-push, no direct push, linear history required.

### Conventional Commits

Allowed scopes: `agent`, `api`, `web`, `schemas`, `tools`, `domain`, `simulation`, `optimization`, `prediction`, `memory`, `state`, `infra`, `data`, `docs`, `ci`, `deps`.

## Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Backup disabled — data loss on incident | Lose all decisions, audit, memory | Acceptable for MVP (synthetic data, no users); re-enable trigger recorded |
| Single PostgreSQL store hits scale ceiling | Latency degradation across all surfaces | Phase 9+ triggers documented; repository pattern preserves swap-in |
| Anthropic outage | Service unavailable | LLMClient interface allows provider swap; nightly real-API E2E catches regressions |
| LLM cost overrun in MVP | Unexpected spend | Observation Day 1; soft/hard ceilings Phase 4+ |
| Sample data does not reflect real distributions | Stub behavior misleads early validation | Negative Binomial + lognormal + bucket overlap models real shape; ADR documents choices |
| Engineer-debug surface leaks sensitive data in prod | Confidentiality breach | LLM context sanitizer; Tool Call Inspector shows agent-visible data only (no ground truth) |
| Ground-truth leak via SQL Tool | Evaluation invalidated | Two-layer defense (path convention + allowlist + tables never loaded into DB) |
| Schema drift between Pydantic and Zod | Frontend / backend desync | CI equivalence check; codegen from Pydantic |

### Phase 9+ Future Considerations

| Trigger | Action | Affected Component |
|---|---|---|
| `audit_log` exceeds ~10⁹ rows | Move cold partitions to Azure Blob with archival policy | `packages/state/audit_log_repo` |
| Cross-decision analytics queries slow | Move analytics workload to Databricks Gold | Reporting / Predictor reads |
| pgvector latency degrades at memory scale | Replace with Azure AI Search or Qdrant | `packages/memory/MemoryStore` |
| Real-time inventory write throughput exceeded | Redis as write-through cache | `packages/state/inventory_repo` |
| Specialist count > 10 | Distributed Specialist execution + Azure Service Bus | `packages/agent/orchestrator` |
| Job queue load growth beyond Celery | Migrate to Temporal | `packages/agent/job_runner` |
| Multi-tenancy requirement | Row-level security + tenant scoping | `packages/state/*` |
| Regulatory compliance (SOX / GDPR) | Enable PITR + geo-redundant backup + soft-delete | Terraform `shared/` |
| Cost optimization at scale | Move to managed Citus / Cosmos PG | Terraform `shared/` |
| Disaster recovery requirement | Re-enable backup, geo-replication, RTO/RPO | Terraform `shared/` |

## Documentation Language

- `SPEC.md`, `DESIGN.md`, `TASKS.md`, `DECISIONS.md`, `ARCHITECTURE.md`, `AGENTS.md`, all `docs/adr/*.md` → **English**.
- Existing Japanese reference docs (`docs/business_decision_os_spec.md`, `docs/domain.md`) → kept as-is, source notes only; English official docs supersede on conflict.
- Code / comments / identifiers / log messages / commit messages / PR titles & bodies → English.
- All user-visible strings in the UI and terminal (chrome, chat bodies, agent narrative) → English.
