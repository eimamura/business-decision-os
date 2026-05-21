# Tasks

## Notes for AI Agent

- Read `docs/PRODUCT_SPEC.md` and `docs/DESIGN.md` before starting any task.
- Make the smallest useful change. Do not over-engineer.
- Mark tasks `In Progress` when starting, `Done` when complete.
- Update docs (`docs/PRODUCT_SPEC.md` / `docs/DESIGN.md` / `docs/DECISIONS.md`) when design changes.
- Add or update tests when appropriate.
- Final-form-first applies: phases fill in implementations behind stable interfaces; never add new modules.
- Stubs must be schema-conformant and intentionally trivial. Smart stubs hide schema mismatches.

## Milestones

| Milestone | Goal | Status |
|---|---|---|
| M0+1 | Phase 0 foundation + Phase 1 vertical-slice MVP shipped together | Done |
| M2 | Real Simulator on ACA Jobs | Done |
| M3 | Real Optimizer on ACA Jobs | Done |
| M4 | Approval Workflow Expansion + LLM budget enforcement | Done |
| M5 | Celery + Redis job queue | Done |
| M6 | Real Predictor on Databricks (training + batch inference) | Done |
| M7 | Memory & Learning Loop (pgvector retrieval) | Done |
| M8 | Semi-Autonomous Execution + Databricks Lakehouse | Done |
| M9 | Domain Expert specialist split | Done |
| M10 | Chat Quality Features — history summarization, rate limiting, feedback, LLM tracking, rich UI | Done |
| M11 | Single-Page Chat Shell — unified sidebar + chat layout, no two-page navigation | Done |
| M12 | Agent Trace Panel — full visibility: DB trace, routing decision, per-agent timeline, tool I/O, BRT timestamps | In Progress |
| M13 | SQL Intelligence Tools — NlQueryTool (text-to-SQL via Haiku) + SqlQueryTool real DB connection | Done |

## Phase 0 — Repository Foundation

Batch execution order: B01 → B02 → B03 → B04 → B05 (B05 can run in parallel with B03/B04).
Each batch is one Orchestrator turn. Orchestrator records active lease in `docs/STATE.md` before spawning a specialist.

### B01 — Repo Scaffold (Agent: Infra)

Dependencies: none

| ID | Task | Priority | Status |
|---|---|---|---|
| T-0001 | Initialize Git repo; push to GitHub; configure branch protection on `main`; Conventional Commits config | High | Done |
| T-0002 | Author `.gitignore` covering Python / Node / Terraform / Docker / IDE / secrets / logs / coverage | High | Done |
| T-0003 | Scaffold `apps/{web,api}` + `packages/*` + `infra/{terraform,compose}` + `data/` + `config/` + `scripts/` + `tests/` + `docs/` | High | Done |
| T-0004 | Configure `uv` workspace (`tool.uv.workspace.members = ["apps/api", "packages/*"]`) | High | Done |
| T-0005 | Configure `npm workspaces` (`apps/web`, `packages/schemas-ts`) | High | Done |
| T-0006 | Set up commitlint / `cz-conventional-changelog` with 16-scope allowlist | Medium | Done |
| T-0043 | `.env.example` with all required keys (no real values) | High | Done |

<!-- ## Infra Handoff — Phase 0 / B01
Changed files:
  .gitignore
  .env.example
  pyproject.toml (root uv workspace)
  package.json (npm workspaces)
  commitlint.config.js
  .husky/commit-msg
  apps/api/pyproject.toml, __init__.py, README.md
  apps/web/package.json, README.md
  packages/agent/pyproject.toml, __init__.py, README.md
  packages/tools/pyproject.toml, __init__.py, README.md
  packages/domain/pyproject.toml, __init__.py, README.md
  packages/simulation/pyproject.toml, __init__.py, README.md
  packages/optimization/pyproject.toml, __init__.py, README.md
  packages/prediction/pyproject.toml, __init__.py, README.md
  packages/memory/pyproject.toml, __init__.py, README.md
  packages/state/pyproject.toml, __init__.py, README.md
  packages/schemas/pyproject.toml, __init__.py, README.md
  packages/schemas-ts/package.json, README.md
  infra/terraform/image-build/main.tf, README.md
  infra/terraform/acr-push/main.tf, README.md
  infra/terraform/aca/main.tf, README.md
  infra/terraform/shared/main.tf, README.md
  infra/terraform/modules/main.tf, README.md
  infra/compose/compose.yaml
  config/.gitkeep, scripts/.gitkeep, tests/.gitkeep
  data/sample/.gitkeep, data/fixtures/.gitkeep, data/sample/ground_truth/.gitkeep
  docs/adr/ (directory)
Smoke checks: SKIPPED (stack not running — pure file-edit scaffold task, no running services)
New env vars: DATABASE_URL, ANTHROPIC_API_KEY, APP_ENV, AZURE_CLIENT_ID, AZURE_TENANT_ID,
  AZURE_SUBSCRIPTION_ID, AZURE_KEY_VAULT_URL, LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY,
  LANGFUSE_HOST, OTEL_EXPORTER_OTLP_ENDPOINT, APPLICATIONINSIGHTS_CONNECTION_STRING,
  NEXT_PUBLIC_API_URL, CORS_ALLOWED_ORIGINS, APPROVAL_TTL_SECONDS, LOG_LEVEL
-->

### B02 — Backend Scaffold (Agent: App Builder)

Dependencies: B01

> Code only the interfaces needed for Phase 1 vertical slice. Future boundaries stay in `docs/DESIGN.md` — do not pre-implement unused stubs.

| ID | Task | Priority | Status |
|---|---|---|---|
| T-0010 | `packages/agent/llm/__init__.py` — `LLMClient` Protocol + `ClaudeClient` stub | High | Done |
| T-0011 | `packages/tools/base.py` — `Tool` Protocol + `ToolRegistry` | High | Done |
| T-0012 | `packages/agent/job_runner/__init__.py` — `JobRunner` Protocol + `InProcessJobRunner` | High | Done |
| T-0013 | `packages/memory/__init__.py` — `MemoryStore` Protocol + write-only stub | High | Done |
| T-0014 | `packages/agent/orchestrator/__init__.py` — `Orchestrator` Protocol | High | Done |
| T-0015 | `packages/agent/specialists/base.py` — `Specialist` Protocol + `PromptBasedSpecialist` | High | Done |
| T-0016 | Define `KpiScore`, `Candidate`, `TradeoffExplanation`, `Recommendation` in `packages/schemas` (Pydantic) | High | Done |
| T-0017 | Define SSE event union in `packages/schemas` (Pydantic) + `packages/schemas-ts` (Zod); CI equivalence check | High | Done |
| T-0018 | Define `evaluations.criteria_json` / `result_json` schemas in `packages/schemas` | High | Done |
| T-0019 | Implement `packages/domain/kpi.py` with the 8 KPI formulas (horizon = 90 days) | High | Done |
| T-0040 | `config/risk_thresholds.yaml` — three-tier thresholds (high / medium / low) | High | Done |
| T-0041 | `config/kpi_weights.csv` — global default (single row, sums to 1.0) | High | Done |
| T-0042 | `config/kpi_weights_overrides.csv` — Critical SKU overrides (service_level=0.50) | High | Done |
| T-0050 | FastAPI app skeleton (`apps/api`) with `X-Dev-User` middleware; default `dev-user` when `APP_ENV=dev` | High | Done |
| T-0051 | Implement REST endpoint skeletons per DESIGN §API Design (501 where logic is not ready; `/healthz` and `/readyz` real) | High | Done |
| T-0052 | Configure FastAPI `CORSMiddleware` — dev (`localhost:3000`) and prod (env-injected); SSE exception for credential | High | Done |
| T-0060 | Approval state-machine logic with `parent_approval_id` chain (revisions create new row) | High | Done |
| T-0061 | Sweep job for `expired` (default `approval_ttl_seconds=86400`) | Medium | Done |

### B03 — Database Migration (Agent: App Builder)

Dependencies: B02

| ID | Task | Priority | Status |
|---|---|---|---|
| T-0020 | Write Alembic migration `0001_initial.sql` with column-level DDL: 16 system tables + 6 operational domain tables; CHECK constraints; FK cascades; indexes; ivfflat on `memories.embedding` | High | Done |
| T-0021 | Implement repository-pattern interfaces in `packages/state/` for all tables | High | Done |
| T-0022 | Implement `audit_log` hash chain in repository writes (`audit_hash`, `prev_audit_hash`) | High | Done |
| T-0023 | Seed `users` table with `dev-user` row | High | Done |
| T-0024 | Seed `llm_pricing` with verified rates for `claude-sonnet-4-6`, `claude-opus-4-7`, `text-embedding-3-small`; ADR `docs/adr/2026-05-17-llm-pricing-seed.md` records source URLs | High | Done |
| T-0025 | Enforce SQL Tool allowlist on `sku_master / inventory / demand_history / supply / cost / customers` | High | Done |

### B04 — Sample Data (Agent: App Builder)

Dependencies: B03

| ID | Task | Priority | Status |
|---|---|---|---|
| T-0030 | Hand-author `data/sample/ground_truth/sku_parameters.csv` (30 rows, bucket composition per DESIGN) | High | Done |
| T-0031 | Hand-author `data/sample/ground_truth/customer_parameters.csv` (large / small / spot mix, `sku_affinity_json`) | High | Done |
| T-0032 | Author `data/sample/ground_truth/README.md` explaining no-access rule; cross-link from `AGENTS.md` | High | Done |
| T-0033 | Implement `scripts/generate_sample_data.py` — demand formula (NegBin noise), lognormal lead time, initial inventory rules, seed=42 default, `--seed N` override | High | Done |
| T-0034 | Implement missing-data injection: 3 SKUs (deterministic), 2% NULL rate, one 7-day contiguous gap | High | Done |
| T-0035 | Implement `scripts/seed_db.py` — reads `data/sample/*.csv` (not `ground_truth/`) via SQLAlchemy | High | Done |
| T-0036 | Add `uv run seed` / `make seed` one-command regeneration target | Medium | Done |
| T-0037 | Author ADR `docs/adr/2026-05-17-sample-data-generation.md` — distribution choices, seed policy, missing-data pattern | Medium | Done |
| T-0038 | Generator unit tests: deterministic output under seed 42; NULL injection rate; seasonal SKUs show > 0.3 amplitude in autocorrelation | Medium | Done |

### B05 — Infra & CI (Agent: Infra)

Dependencies: B01 (can run in parallel with B03/B04)

| ID | Task | Priority | Status |
|---|---|---|---|
| T-0070 | Scaffold `infra/terraform/{image-build,acr-push,aca,shared,modules}/` with independent state | High | Done |
| T-0071 | Set Azure region = US East 2 in all Terraform modules | High | Done |
| T-0072 | Set `prevent_destroy = false`; no resource locks | High | Done |
| T-0073 | Provision Azure Key Vault + Managed Identity in `shared/` | High | Done |
| T-0074 | Scaffold `infra/compose/` with Docker Compose V2 (no `version:` field): postgres + api + web | High | Done |
| T-0075 | Configure Azure OIDC federated credentials with subject claims for `main`, `pull_request`, `environment:prod`; least-privilege RBAC | High | Done |
| T-0080 | `.github/workflows/lint-test.yml` | High | Done |
| T-0081 | `.github/workflows/terraform-plan.yml` (runs on PR) | High | Done |
| T-0082 | `.github/workflows/deploy.yml` (runs on `main`): build → acr-push → tf apply shared → tf apply aca | High | Done |
| T-0090 | Configure `structlog` JSON output + OpenTelemetry SDK + Langfuse SDK | High | Done |
| T-0091 | Provision Azure Monitor / Application Insights in Terraform `shared/`; wire as OTel sink | High | Done |
| T-0099 | Author initial ADRs for each tech choice: Claude provider, FastAPI, Next.js, Postgres+pgvector, Azure region, Terraform pipeline split, Azure OIDC, backup off | High | Done |

<!--
## Infra Handoff — Phase 0 (B05)
Changed files:
  infra/terraform/shared/main.tf — Resource Group, Key Vault, Managed Identity, OIDC federated creds, App Insights, Log Analytics workspace
  infra/terraform/shared/variables.tf — NEW
  infra/terraform/shared/outputs.tf — NEW
  infra/terraform/aca/main.tf — Container Apps Environment + api + web Container Apps
  infra/terraform/aca/variables.tf — NEW
  infra/terraform/aca/outputs.tf — NEW
  infra/terraform/image-build/main.tf — Azure Container Registry (Basic)
  infra/terraform/image-build/variables.tf — NEW
  infra/terraform/image-build/outputs.tf — NEW
  infra/terraform/acr-push/main.tf — null_resource az acr build local-exec
  infra/terraform/acr-push/variables.tf — NEW
  infra/terraform/modules/main.tf — placeholder comment
  infra/compose/compose.yaml — Docker Compose V2 (no version:), explicit env vars
  apps/api/Dockerfile — NEW multi-stage, COPY config config, ENV PYTHONPATH
  apps/api/observability.py — NEW structlog + OTel + Langfuse setup
  apps/api/pyproject.toml — added structlog, opentelemetry-sdk, opentelemetry-exporter-otlp, langfuse
  apps/api/main.py — calls configure_logging() + configure_otel() at startup
  apps/web/Dockerfile — NEW multi-stage Next.js standalone
  apps/web/package.json — added Next.js / React dependencies and scripts
  apps/web/next.config.js — NEW output: standalone
  apps/web/app/page.tsx — NEW placeholder page
  .github/workflows/lint-test.yml — NEW
  .github/workflows/terraform-plan.yml — NEW
  .github/workflows/deploy.yml — NEW
Smoke checks: SKIPPED — stack not running (pure file-edit task; no Azure credentials provisioned yet)
New env vars: ANTHROPIC_API_KEY (from host), OTEL_EXPORTER_OTLP_ENDPOINT (optional), AZURE_CLIENT_ID, AZURE_TENANT_ID, AZURE_SUBSCRIPTION_ID, ACR_LOGIN_SERVER (GitHub secrets)
-->


## Defects

| ID | Task | Priority | Status | Root Cause |
|---|---|---|---|---|
| D-0001 | `make build` / `uv sync` failed — hatchling wheel discovery error | High | Done | `apps/api/pyproject.toml` lacked `[tool.hatch.build.targets.wheel] packages = ["."]`; hatchling searched for a subdirectory named `api` but source lives at the project root. Fixed by adding the explicit wheel target. |
| D-0002 | `make lint` fails — `ruff` not installed | High | Done | Added `ruff>=0.4.0` to `[tool.uv] dev-dependencies` in root `pyproject.toml`; changed Makefile `lint` target to `uv run ruff check`; fixed 18 lint errors (7 auto-fixed, 11 manual: E501 via `per-file-ignores` for alembic migrations, E402 noqa for post-observability imports, F841 unused var, code reformats). |
| D-0003 | `make typecheck` fails — target missing, `mypy` not installed | High | Done | Added `mypy>=1.10.0` to `[tool.uv] dev-dependencies`; added `typecheck` target to Makefile using `uv run --with mypy mypy packages/ apps/api/`; added `explicit_package_bases=true` and `ignore_missing_imports=true` to `[tool.mypy]` config; fixed 24 type errors (`dict→dict[str,Any]` in 10 files, `no-any-return` in middleware.py, `dict[str,str]` in health.py). |
| D-0004 | `make dev-compose` fails — port 8000 already in use | Medium | Done | `infra/compose/compose.yaml` had hardcoded `8000:8000`; no way to override without editing the file. Fixed by replacing with `${API_PORT:-8000}:8000` (and `${WEB_PORT:-3000}:3000` for web). Added `dev-up`/`dev-down`/`dev-smoke`/`dev-logs`/`dev-ps` targets to Makefile for harness-friendly detached operation. Added Runtime Gate Rule to `docs/ACCEPTANCE.md`. |
| D-0005 | Chat runtime: `GET /api/v1/sessions/undefined/messages 405 Method Not Allowed` | High | Done | Two-part defect. (1) `Session` TypeScript interface in both chat pages used `id: string` but backend `POST /api/v1/sessions` and `GET /api/v1/sessions` return objects with `session_id` field, not `id`. Sidebar links used `s.id` (undefined) producing `/chat/undefined` URLs. (2) Backend only defines `POST /{session_id}/messages`; a GET to the same path returns 405. Fixed by updating `Session` interface and all `s.id` references in both pages to `session_id`. Added Chat Runtime Smoke Gate to `docs/ACCEPTANCE.md`. Files changed: `apps/web/app/chat/page.tsx`, `apps/web/app/chat/[sessionId]/page.tsx`, `docs/ACCEPTANCE.md`. |
| D-0006 | `make dev-compose` / `make dev-up` warns `ANTHROPIC_API_KEY` not set despite `.env` existing at repo root | Medium | Done | Docker Compose V2 with `-f path/to/compose.yaml` searches for `.env` relative to the compose file directory (`infra/compose/`), not the current working directory. Root-level `.env` was silently ignored. Fixed by adding `--env-file .env` to all five `docker compose` targets in `Makefile` (`dev-compose`, `dev-up`, `dev-down`, `dev-logs`, `dev-ps`). Files changed: `Makefile`. |

## Phase 1 — Decision Copilot (Vertical-Slice MVP)

### Agent runtime

| ID | Task | Priority | Status |
|---|---|---|---|
| T-1001 | Implement `ClaudeClient` with prompt caching enabled; `temperature=0` default | High | Done |
| T-1002 | Instrument `LLMClient` to write `llm_usage` rows inside the same DB transaction as the parent `agent_step` | High | Done |
| T-1003 | Implement Orchestrator sequential single-LLM loop with role switching (Plan → Tool → Evaluate → Recommend) | High | Done |
| T-1003b | Add LLM-based specialist routing to `PhaseOrchestrator`: single routing call selects which specialists to invoke per goal; falls back to full sequence on error; enforces `sim_opt`↔`evaluator` pairing; emits `step_type: "routing"` SSE events | High | Done |
| T-1003c | Add conversational path: `["none"]` routing option bypasses all specialists; Orchestrator calls LLM directly; `Recommendation.direct_reply` carries reply text; `sessions.py` short-circuits `_format_recommendation()` on `direct_reply` | High | Done |
| T-1004 | Implement 4 `PromptBasedSpecialist` instances (Domain Expert, Data Engineer, Simulator/Optimizer, Evaluator) with role prompts + tool subsets | High | Done |
| T-1005 | Implement Orchestrator error handling: 2 retries with backoff (1s, 4s); SSE `error` event; `decision_sessions.status = failed` on terminal failure | High | Done |
| T-1005b | Wire SSE `error`/`done` events to Chat UI: reply displayed in chat bubble; errors displayed as red error bubble; Fail-silent fallbacks eliminated across codebase | High | Done |
| T-1006 | Implement Orchestrator trade-off resolution: config defaults + Critical SKU overrides; user policy and session goal hooks present but no-op in MVP | High | Done |
| T-1007 | Implement primary + 2 alternatives selection in Recommendation generation | High | Done |
| T-1008 | Wire `decision_sessions.status` state machine with optimistic-retry on conflict | High | Done |

### Tools

| ID | Task | Priority | Status |
|---|---|---|---|
| T-1010 | SQL Query Tool: read-only on operational tables; allowlisted | High | Done |
| T-1011 | Approval Tool: full state machine integration | High | Done |
| T-1012 | Audit Log Tool: hash-chained writes | High | Done |
| T-1013 | Forecast Tool stub: 28-day moving average over `demand_history`, NULL-aware; `model_version="moving_avg_v1"` | High | Done |
| T-1014 | Simulation Tool stub: deterministic projection (`on_hand[t+1] = max(0, on_hand[t] + arrivals[t] - demand[t])`); mean lead time only | High | Done |
| T-1015 | Optimizer Tool stub: enumerate `order_qty ∈ {0, MOQ, 2MOQ, …, 5MOQ}`; run Simulator stub; return first 3 feasible by ascending `total_supply_chain_cost` | High | Done |
| T-1016 | Evaluator (rule-based) producing `KpiScore[]` per candidate (no collapsed scoring); apply three-tier risk classification | High | Done |
| T-1017 | LLM context sanitizer: raw rows never sent to Claude; only summaries / aggregates | High | Done |

### Web UI

| ID | Task | Priority | Status |
|---|---|---|---|
| T-1020 | Chat screen: English UI and English agent responses; GFM Markdown rendering (`react-markdown` + `remark-gfm` + `rehype-sanitize` + syntax highlighter + KaTeX + Mermaid lazy load) | High | Done |
| T-1021 | Chat session list sidebar; URL `/chat/[sessionId]`; multi-session navigation | High | Done |
| T-1022 | Reasoning Panel with SSE consumer; Active Specialist banner; Orchestrator routing log; Step timeline; live status pill; `Cmd/Ctrl + .` toggle | High | Done |
| T-1023 | Tool Call Inspector: input / output JSON; executed-SQL syntax-highlighted display; table preview; copy / open-in-audit actions | High | Done |
| T-1024 | Scenario Comparison screen: radar chart + parallel coordinates (Recharts) | High | Done |
| T-1025 | Recommendation Detail: primary + alternatives + `TradeoffExplanation` + rationale + risk badge | High | Done |
| T-1026 | Approval Queue: risk badges + trade-off summary + revision-request weight-vector editor | High | Done |
| T-1027 | Audit Timeline: session_id filter + agent / tool / status filters + JSON diff + token / cost summary | High | Done |
| T-1028 | KPI Dashboard skeleton with LLM Cost Trend panel | High | Done |
| T-1029 | Wire Vercel AI SDK with Claude provider for chat streaming | High | Done |
| T-1030 | SSE reconnect with `Last-Event-ID` replay from `audit_log` | High | Done |

### Memory and tests

| ID | Task | Priority | Status |
|---|---|---|---|
| T-1040 | MemoryStore stub: `write` persists; `search` returns `[]` | High | Done |
| T-1041 | Pytest fixtures: YAML scenarios + `vcrpy` cassettes for LLM calls | High | Done |
| T-1042 | Playwright E2E suite covering chat → recommendation → approval → audit | High | Done |
| T-1043 | Document English-only convention for code, docs, UI, and chat in `AGENTS.md` | Medium | Done |

## Phase 2 — Real Simulator

| ID | Task | Priority | Status |
|---|---|---|---|
| T-2001 | Provision Azure Container Apps Jobs via Terraform `aca/` extension | High | Done |
| T-2002 | Implement real Python simulation behind `Simulator` interface | High | Done |
| T-2003 | Move Simulator invocation to ACA Jobs trigger | High | Done |

<!--
## Infra Handoff — Phase 2 (Batch B2-02)
Changed files:
  - infra/terraform/aca/main.tf         — added azurerm_container_app_job.simulation_worker
  - infra/terraform/aca/variables.tf    — added database_url variable (sensitive)
  - infra/terraform/aca/outputs.tf      — added simulation_job_resource_id output
  - apps/simulation-worker/Dockerfile   — multi-stage Python 3.12 image
  - apps/simulation-worker/run_job.py   — job entry point (reads JOB_RUN_ID, JOB_PAYLOAD, DATABASE_URL)
  - apps/simulation-worker/pyproject.toml — uv workspace member
  - pyproject.toml                      — added apps/simulation-worker to workspace members
Smoke checks: SKIPPED (curl permission not available in agent context; docker compose ps shows stack Up)
terraform validate: SKIPPED (terraform init permission not available in agent context)
No hardcoded credentials in new files (database_url is sensitive var; env vars used at runtime)
New env vars: DATABASE_URL (simulation-worker container), JOB_RUN_ID (set per execution), JOB_PAYLOAD (set per execution)
-->


## Phase 3 — Real Optimizer

| ID | Task | Priority | Status |
|---|---|---|---|
| T-3001 | Implement OR-Tools / PuLP optimizer behind `Optimizer` interface | High | Done |
| T-3002 | Move Optimizer invocation to ACA Jobs trigger | High | Done |

<!--
## Infra Handoff — Phase 3 (T-3002 infra side)
Changed files:
  - apps/optimization-worker/pyproject.toml   — NEW uv workspace member (pulp>=2.7.0 dep)
  - apps/optimization-worker/run_job.py       — NEW ACA Job entry point (ReplenishmentOptimizer)
  - apps/optimization-worker/Dockerfile       — NEW multi-stage Python 3.12 image
  - pyproject.toml                            — added apps/optimization-worker to workspace members
  - infra/terraform/aca/main.tf               — added azurerm_container_app_job.optimization_worker
Smoke checks: SKIPPED (curl permission not available in agent context; docker compose ps shows stack Up)
terraform validate: SKIPPED (terraform init permission not available in agent context)
No hardcoded credentials in new files (database_url is sensitive var; env vars used at runtime)
New env vars: none (DATABASE_URL, JOB_RUN_ID, JOB_PAYLOAD already defined by Phase 2 simulation worker pattern)
-->

## Phase 4 — Approval Workflow Expansion + Budget Enforcement

| ID | Task | Priority | Status |
|---|---|---|---|
| T-4001 | Notifications for new pending approvals | Medium | Done |
| T-4002 | Approver roles + permission checks | Medium | Done |
| T-4003 | Settings / Policies screen with budget threshold editors | High | Done |
| T-4004 | LLM budget soft / hard ceiling interceptor in `LLMClient` | High | Done |

## Phase 5 — Job Orchestration

| ID | Task | Priority | Status |
|---|---|---|---|
| T-5001 | Provision Azure Cache for Redis via Terraform `shared/` | High | Done |
| T-5002 | Deploy Celery worker on ACA via Terraform `aca/` extension | High | Done |
| T-5003 | Swap `JobRunner` sync implementation for Celery implementation; callers unchanged | High | Done |

<!--
## Infra Handoff — Phase 5 (T-5001, T-5002)
Changed files:
  infra/terraform/shared/main.tf        — added azurerm_redis_cache.main (Basic C1, TLS 1.2, SSL only)
  infra/terraform/shared/outputs.tf     — added redis_hostname and redis_primary_connection_string outputs
  infra/terraform/aca/main.tf           — added azurerm_container_app.celery_worker (min 1, max 3 replicas)
  infra/terraform/aca/variables.tf      — added acr_login_server and redis_connection_string variables
  infra/compose/compose.yaml            — added redis service (redis:7-alpine); added celery-worker service; added Redis env vars + JOB_RUNNER_BACKEND to api; added redis to api depends_on
Smoke checks: SKIPPED (stack not running — docker compose ps returned empty)
New env vars: CELERY_BROKER_URL, CELERY_RESULT_BACKEND, JOB_RUNNER_BACKEND, REDIS_PORT
-->

## Phase 6 — Real Predictor

| ID | Task | Priority | Status |
|---|---|---|---|
| T-6001 | Provision Databricks workspace + MLflow via new Terraform stage | High | Done |
| T-6002 | Databricks Job for predictor training | High | Done |
| T-6003 | Databricks Job for batch inference writing features back to PostgreSQL | High | Done |
| T-6004 | Implement lightweight realtime inference in FastAPI in-process | Medium | Done |
| T-6005 | Separate offline training from realtime inference: add JobSpec.kind="train_forecast", implement TrainedModelPredictor | Medium | Done |

## Phase 7 — Memory & Learning Loop

| ID | Task | Priority | Status |
|---|---|---|---|
| T-7001 | Swap MemoryStore stub for pgvector retrieval | High | Done |
| T-7002 | Memory-write hooks in Orchestrator (record weight vector on approval / rejection / revision) | High | Done |
| T-7003 | Wire `user_policy` memory back into Orchestrator's default weight selection | High | Done |

## Phase 8 — Semi-Autonomous Execution + Databricks Lakehouse

| ID | Task | Priority | Status |
|---|---|---|---|
| T-8001 | Risk-classified auto-execution policy in Approval flow | High | Done |
| T-8002 | Provision Databricks Lakehouse (ADLS Gen2 + Delta + workspace) in US East 2 | High | Done |
| T-8003 | Set up CDC ingestion from PostgreSQL to Bronze layer | High | Done |
| T-8004 | Define Silver / Gold transformation pipelines | High | Done |

## Phase 9 — Business Decision OS Completion

| ID | Task | Priority | Status |
|---|---|---|---|
| T-9001 | Split Domain Expert into Forecast / Inventory / Procurement / Production / Cost specialists | High | Done |
| T-9002 | Swap `PromptBasedSpecialist` for `AgentBasedSpecialist` (independent context, independent tool registry, parallel execution) | High | Done |
| T-9003 | Orchestrator becomes pure coordinator dispatching to parallel Specialist agents | High | Done |

## Phase 10 — Chat Quality Features (Reference Port)

Port conversation history summarization, rate limiting, message feedback, LLM usage tracking,
rich MessageBubble rendering, typed API client, and useChat hook from the reference ecommerce-admin-chatbot.

Batch execution order: B1 → (B2 ∥ B3) → B4

### B1 — DB Foundation (Agent: bdos-infra → bdos-app-builder)

Dependencies: none

| ID | Task | Priority | Status |
|---|---|---|---|
| T-10001 | Alembic migration 0002: add `session_messages` and `rate_limit_counters` tables | High | Done |
| T-10002 | Implement `DecisionSessionRepository` and `LlmUsageRepository`; create `packages/state/db.py` pool factory; wire real `usage_writer` in `apps/api/state.py` | High | Done |

### B2 — Backend Features (Agent: bdos-app-builder) — parallel with B3

Dependencies: B1

| ID | Task | Priority | Status |
|---|---|---|---|
| T-10003 | Conversation history summarization: `packages/agent/history.py`; integrate into `sessions.py` `post_message` | High | Done |
| T-10004 | Per-user + global rate limiting: `packages/agent/rate_limiter.py`; integrate into `sessions.py`; add 429 handler in `main.py` | Medium | Done |
| T-10005 | Message feedback endpoint: `PATCH /api/v1/sessions/{sid}/messages/{mid}/feedback`; update `GET messages` to return `feedback` field | Medium | Done |

### B3 — Frontend API Client (Agent: bdos-app-builder) — parallel with B2

Dependencies: none (can start immediately)

| ID | Task | Priority | Status |
|---|---|---|---|
| T-10006 | Typed API client `apps/web/lib/api.ts` + type definitions `apps/web/types/chat.ts` | High | Done |

### B4 — Frontend UI Features (Agent: bdos-app-builder)

Dependencies: B3

| ID | Task | Priority | Status |
|---|---|---|---|
| T-10007 | `useChat` hook (`apps/web/hooks/useChat.ts`); refactor `chat/[sessionId]/page.tsx` to use hook | High | Done |
| T-10008 | `MessageBubble` component (`apps/web/components/MessageBubble.tsx`) with syntax highlighting + 👍👎 feedback UI | Medium | Done |
| T-10009 | Token usage display in `ReasoningPanel`: input/output/cost rows from `useChat` usage state | Low | Done |

## Phase 11 — Single-Page Chat Shell

Goal: Merge the two-page chat flow (`/chat` list + `/chat/[sessionId]` chat) into a single-page shell with a persistent sidebar.
The sidebar contains: logo/brand, "New Session" button, scrollable session history list (active session highlighted), and bottom nav links.
The main content area shows: empty state when no session is selected, full chat UI when a session is active.
No backend changes required. No public interface changes.

Batch execution order: B1

### B1 — Chat Shell Refactor (Agent: bdos-app-builder)

Dependencies: none

| ID | Task | Priority | Status |
|---|---|---|---|
| T-11001 | Extract `ChatSidebar` component (`apps/web/components/ChatSidebar.tsx`): brand link, "New Session" button (calls `createSession`, navigates to new sessionId), scrollable session list with active highlight, bottom nav links | High | Done |
| T-11002 | Rewrite `apps/web/app/chat/page.tsx` as single-page shell: renders `ChatSidebar` + empty-state main panel ("Select or create a session") — no redirect, no two-page navigation | High | Done |
| T-11003 | Refactor `apps/web/app/chat/[sessionId]/page.tsx` to use `ChatSidebar` (replacing its inline sidebar) while keeping all existing chat functionality intact | High | Done |

## Phase 12 — Agent Trace Panel

Goal: Full visibility into the agent pipeline for each session — DB trace, routing decision, per-agent timeline, tool I/O, and BRT timestamps.
Surfaces in the `ReasoningPanel` component on the chat page.

Batch execution order: B1 → B2

### B1 — DB & Infra Fixes (Agent: bdos-infra)

Dependencies: none

| ID | Task | Priority | Status |
|---|---|---|---|
| T-12001 | Fix alembic env.py to use asyncpg async engine (psycopg2 not installed) | High | Done |
| T-12002 | Migration 0004: rename `memories.metadata` → `memories.metadata_json` (column name mismatch) | High | Done |
| T-12003 | Migration 0005: make `decision_sessions.user_id` nullable, drop FK to users (dev env has no seeded users) | High | Done |
| T-12004 | Fix `create_session` to persist session to `decision_sessions` on creation (was in-memory only, causing FK violation on session_messages) | High | Done |
| T-12005 | Add `DATABASE_URL` to `.env` for local dev; wire up docker-compose DB service | Medium | Done |

### B2 — Agent Trace SSE + UI (Agent: bdos-app-builder)

Dependencies: B1

| ID | Task | Priority | Status |
|---|---|---|---|
| T-12006 | Extend SSE schema: add `RoutingDecisionEvent`; add `input_summary`, `output_summary`, `ended_at` fields to step/specialist events | High | Done |
| T-12007 | Wire `sse_queue` into `create_specialists`; emit trace events from `agent_based.py` and `base.py` during execution | High | Done |
| T-12008 | Orchestrator emits `routing_decision` SSE event with route list and rationale | High | Done |
| T-12009 | Rebuild `ReasoningPanel` with full trace UI: routing decision card, per-agent timeline, tool I/O accordion, BRT timestamps | High | Done |

## Phase 13 — SQL Intelligence Tools

Goal: Implement NlQueryTool (text-to-SQL via Claude Haiku with guardrails, caching, and retry) and fix SqlQueryTool to use a real DB connection via get_pool(). Ported from reference/ecommerce-admin-chatbot.

Batch execution order: B1

### B1 — SQL Tools Implementation (Agent: App Builder)

Dependencies: none

| ID | Task | Priority | Status |
|---|---|---|---|
| T-13001 | Create `packages/tools/nl_query_tool.py` — `NlQueryTool` (text-to-SQL via Claude Haiku; prompt caching; 60s TTL cache; MAX_RETRIES=2; sqlparse guardrail; dynamic few-shot from session_messages feedback=1) | High | Done |
| T-13002 | Fix `packages/tools/sql_tool.py` — replace SQLAlchemy `db_session` with `get_pool()` from `packages/state/db.py`; keep `__init__(db_session=None)` for backward compat | High | Done |
| T-13003 | Implement `packages/tools/sql_allowlist.py` `validate_query()` — reuse `_validate_sql` logic; raise `ValueError` on violation | Medium | Done |
| T-13004 | Update `packages/tools/base.py` `_ROLE_TOOL_ALLOWLIST` — add `"nl_query"` to domain_expert, forecast, inventory, procurement, production, cost, data_engineer | Medium | Done |
| T-13005 | Update `packages/tools/__init__.py` — import and register `NlQueryTool` in `create_tool_registry()` | Medium | Done |
| T-13006 | Add `sqlparse>=0.5` to `apps/api/pyproject.toml` dependencies | High | Done |
