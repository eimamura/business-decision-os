# Codemaps — Business Decision OS

Architecture navigation guide. Each section lists the module's purpose, key files, and the public interface it exposes or depends on.

> Source of truth for interfaces: `docs/DESIGN.md §Public Interfaces`
> Source of truth for phase ownership: `docs/TASKS.md`

---

## apps/api — FastAPI Backend

Entry point for all browser and agent traffic.

```
apps/api/
  app/
    main.py              FastAPI application factory; lifespan hooks
    config.py            Settings (pydantic-settings); reads env vars
    middleware.py        X-Dev-User header → request.state.user injection
    routers/
      sessions.py        POST /sessions, GET /sessions/{id}/stream (SSE)
      approvals.py       POST /approvals/{id}/decide
      audit.py           GET /audit/{session_id}
      health.py          GET /healthz → 200
    deps.py              FastAPI dependency injection (DB session, services)
  Dockerfile             Multi-stage; build context = monorepo root
  pyproject.toml
```

**Exposes:** REST + SSE API  
**Depends on:** `packages/agent`, `packages/state`, `packages/schemas`

---

## apps/web — Next.js Frontend

Browser UI with SSE-based Reasoning Panel.

```
apps/web/
  app/
    layout.tsx           Root layout; providers
    chat/page.tsx        Main chat surface
    scenarios/page.tsx   Scenario comparison (radar + parallel coordinates)
    approvals/page.tsx   Approval queue
    audit/page.tsx       Audit timeline
    kpi/page.tsx         KPI dashboard
  components/
    reasoning-panel/     Tool Call Inspector; Cmd/Ctrl+. toggle
    recommendation/      Primary + alternatives display
    approval/            Decision submit form
  lib/
    sse.ts               SSE client wrapper
    api.ts               Typed fetch helpers
  Dockerfile             Next.js standalone; build context = monorepo root
  package.json
```

**Exposes:** Browser UI  
**Depends on:** `packages/schemas-ts`

---

## packages/agent — Orchestrator, Specialists, LLMClient, JobRunner

Core multi-agent runtime.

```
packages/agent/
  llm/
    client.py            LLMClient (ClaudeClient) — all text completion + embed
    models.py            LLMMessage, LLMUsage, LLMResponse, LLMStreamEvent
  orchestrator/
    orchestrator.py      Orchestrator.run / resume — dispatches to Specialists
    loop.py              Agent turn loop; tool-call dispatch
  specialists/
    base.py              PromptBasedSpecialist (Phase 1) / AgentBasedSpecialist (Phase 9)
    domain_expert.py     Supply chain reasoning; KPI tension surfacing
    data_engineer.py     SQL-heavy data assembly
    sim_opt.py           Simulation + Optimization coordination
    evaluator.py         Per-KPI scoring; never collapses to weighted total
  job_runner/
    base.py              JobRunner Protocol
    inprocess.py         InProcessJobRunner (dev/CI; synchronous)
    aca.py               AcaJobsRunner (production; Phase 2+)
    celery.py            CeleryJobRunner (Phase 5+)
```

**Public interfaces:** `LLMClient`, `Orchestrator`, `Specialist` — see `docs/DESIGN.md §Public Interfaces`  
**Depends on:** `packages/tools`, `packages/state`, `packages/schemas`

---

## packages/tools — Tool Registry + Concrete Tools

Schema-driven tool layer; each tool auto-writes `tool_calls` + `audit_log`.

```
packages/tools/
  registry.py            ToolRegistry.register / get / list_for_role
  base.py                Tool Protocol; ToolContext; ToolResult
  sql.py                 SQL Query Tool — allowlist-enforced table access
  approval.py            Approval Tool — initiates human approval state machine
  audit.py               Audit Tool — queries audit_log for timeline display
  forecast.py            Forecast Tool (stub → real in Phase 6)
  simulation.py          Simulation Tool — delegates to JobRunner
  optimization.py        Optimization Tool — delegates to JobRunner
```

**Public interface:** `Tool.handle(input, ctx) → ToolResult`  
**Depends on:** `packages/schemas`, `packages/state`, `packages/agent/job_runner`

---

## packages/domain — KPI Formulas, Risk, Weights

Pure business logic; no DB access.

```
packages/domain/
  kpi.py                 8 KPI formulas (fill_rate, stockout_days, etc.)
  risk.py                3-tier risk classification (risk_thresholds.yaml)
  weights.py             Weight resolution: session_goal → memory → overrides → default
```

**Public interface:** Pure functions; no Protocol  
**Depends on:** `config/risk_thresholds.yaml`, `config/kpi_weights*.csv`

---

## packages/state — Repositories + DB Models

Repository pattern over all PostgreSQL tables.

```
packages/state/
  db.py                  Async SQLAlchemy engine; session factory
  models.py              ORM models (all tables from migration 0001)
  migrations/
    alembic.ini
    versions/
      0001_initial.py    Single migration covering Phases 0–9 schema
  repos/
    sessions.py          sessions + agent_steps
    tool_calls.py        tool_calls
    audit_log.py         audit_log (hash chain verification)
    recommendations.py   recommendations + candidates + kpi_scores
    approvals.py         approvals (state machine; new row per revision)
    memories.py          memories (pgvector)
    llm_usage.py         llm_usage
    domain.py            sku_master, inventory, demand_history, supply, cost, customers
```

**Public interface:** Repository classes (findAll / findById / create / update)  
**Depends on:** `packages/schemas`

---

## packages/schemas — Pydantic Schemas (Source of Truth)

All shared data contracts. `packages/schemas-ts/` (Zod) is generated from here.

```
packages/schemas/
  agent.py               LLMMessage, LLMUsage, LLMResponse, SpecialistRole
  tool.py                ToolContext, ToolResult, ToolSpec
  job.py                 JobSpec, JobHandle, JobResult
  recommendation.py      Recommendation, Candidate, KpiScore, Approval
  session.py             Session, AgentStep, ToolCall, AuditLog, LlmUsage
  domain.py              SkuMaster, InventoryRecord, DemandHistory, etc.
  simulation.py          SimulationInput, SimulationOutput, SimulationContext
  optimization.py        OptimizationInput, OptimizationOutput
  forecast.py            ForecastInput, ForecastOutput, DailyForecast
  memory.py              MemoryRecord, MemorySearchResult
```

**Codegen:** `make codegen` → writes `packages/schemas-ts/`  
**Depends on:** nothing (leaf package)

---

## packages/simulation — Simulator Implementations

```
packages/simulation/
  base.py                Simulator Protocol: run(SimulationInput) → SimulationOutput
  stub.py                Stub (Phase 0–1): schema-conformant, trivially simple
  inventory.py           InventorySimulator (Phase 2): real day-by-day simulation
```

**Public interface:** `Simulator.run`  
**Depends on:** `packages/schemas`

---

## packages/optimization — Optimizer Implementations

```
packages/optimization/
  base.py                Optimizer Protocol: run(OptimizationInput) → OptimizationOutput
  stub.py                Stub (Phase 0–2): returns 3 trivial candidates
  replenishment.py       ReplenishmentOptimizer (Phase 3): OR-Tools CP-SAT
```

**Public interface:** `Optimizer.run`  
**Depends on:** `packages/schemas`

---

## packages/prediction — Predictor Implementations

```
packages/prediction/
  base.py                Predictor Protocol: run(ForecastInput) → ForecastOutput
  stub.py                Stub (Phase 0–5): 28-day MA, NULL-aware
  sklearn.py             ScikitLearnPredictor (Phase 6): scikit-learn / statsmodels
```

**Public interface:** `Predictor.run`  
**Depends on:** `packages/schemas`

---

## packages/memory — MemoryStore Implementations

```
packages/memory/
  base.py                MemoryStore Protocol: write / search
  stub.py                Stub (Phase 0–6): write-only, search returns []
  pgvector.py            PgvectorMemoryStore (Phase 7): real vector retrieval
```

**Public interface:** `MemoryStore.write / search`  
**Depends on:** `packages/schemas`, `packages/state`

---

## infra — Terraform + Docker Compose

```
infra/
  terraform/
    image-build/         Build Docker images in CI
    acr-push/            Tag + push to Azure Container Registry
    aca/                 Azure Container Apps: api, web, simulation-worker
    shared/              Postgres Flexible Server, Key Vault, Monitor, networking
    modules/             Reusable modules (e.g., aca-app, keyvault-secret)
  compose/
    compose.yaml         Local dev: postgres + api + web
```

**Key rules:** build contexts = monorepo root; postgres image = `pgvector/pgvector:pg16`  
**See:** `agents/infra/SPEC.md`, `docs/DEVELOPMENT.md`

---

## data + config

```
data/
  sample/                Operational CSVs (agent-accessible): sku_master.csv, etc.
  sample/ground_truth/   Generator parameters — FORBIDDEN to agents
  fixtures/
    scenarios/           YAML input/expected-output pairs
    cassettes/           vcrpy HTTP recordings (committed; never deleted)

config/
  risk_thresholds.yaml   Low/Medium/High thresholds per KPI
  kpi_weights.csv        Global default weight vector
  kpi_weights_overrides.csv  Per-session overrides
```

---

## Cross-Cutting Rules

| Concern | Rule |
|---|---|
| LLM context | No raw DB rows — summaries / aggregates only |
| `llm_usage` | Written inside `LLMClient`, never at call site |
| `tool_calls` + `audit_log` | Same DB transaction as tool invocation |
| `temperature` | `0` everywhere |
| Schema parity | `packages/schemas` (Pydantic) → `packages/schemas-ts` (Zod) via codegen |
| Ground truth | `data/sample/ground_truth/` — no agent may read this |
| SQL allowlist | Only: `sku_master`, `inventory`, `demand_history`, `supply`, `cost`, `customers` |
