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
| M0+1 | Phase 0 foundation + Phase 1 vertical-slice MVP shipped together | Not Started |
| M2 | Real Simulator on ACA Jobs | Not Started |
| M3 | Real Optimizer on ACA Jobs | Not Started |
| M4 | Approval Workflow Expansion + LLM budget enforcement | Not Started |
| M5 | Celery + Redis job queue | Not Started |
| M6 | Real Predictor on Databricks (training + batch inference) | Not Started |
| M7 | Memory & Learning Loop (pgvector retrieval) | Not Started |
| M8 | Semi-Autonomous Execution + Databricks Lakehouse | Not Started |
| M9 | Domain Expert specialist split | Not Started |

## Phase 0 — Repository Foundation

### Repository scaffold

| ID | Task | Priority | Status |
|---|---|---|---|
| T-0001 | Initialize Git repo; push to GitHub; configure branch protection on `main`; Conventional Commits config | High | Not Started |
| T-0002 | Author `.gitignore` covering Python / Node / Terraform / Docker / IDE / secrets / logs / coverage | High | Not Started |
| T-0003 | Scaffold `apps/{web,api}` + `packages/*` + `infra/{terraform,compose}` + `data/` + `config/` + `scripts/` + `tests/` + `docs/` | High | Not Started |
| T-0004 | Configure `uv` workspace (`tool.uv.workspace.members = ["apps/api", "packages/*"]`) | High | Not Started |
| T-0005 | Configure `npm workspaces` (`apps/web`, `packages/schemas-ts`) | High | Not Started |
| T-0006 | Set up commitlint / `cz-conventional-changelog` with 16-scope allowlist | Medium | Not Started |

### Interfaces and schemas

| ID | Task | Priority | Status |
|---|---|---|---|
| T-0010 | `packages/agent/llm/__init__.py` — `LLMClient` Protocol + `ClaudeClient` stub | High | Not Started |
| T-0011 | `packages/tools/base.py` — `Tool` Protocol + `ToolRegistry` | High | Not Started |
| T-0012 | `packages/agent/job_runner/__init__.py` — `JobRunner` Protocol + `InProcessJobRunner` | High | Not Started |
| T-0013 | `packages/memory/__init__.py` — `MemoryStore` Protocol + write-only stub | High | Not Started |
| T-0014 | `packages/agent/orchestrator/__init__.py` — `Orchestrator` Protocol | High | Not Started |
| T-0015 | `packages/agent/specialists/base.py` — `Specialist` Protocol + `PromptBasedSpecialist` | High | Not Started |
| T-0016 | Define `KpiScore`, `Candidate`, `TradeoffExplanation`, `Recommendation` in `packages/schemas` (Pydantic) | High | Not Started |
| T-0017 | Define SSE event union in `packages/schemas` (Pydantic) + `packages/schemas-ts` (Zod); CI equivalence check | High | Not Started |
| T-0018 | Define `evaluations.criteria_json` / `result_json` schemas in `packages/schemas` | High | Not Started |
| T-0019 | Implement `packages/domain/kpi.py` with the 8 KPI formulas (horizon = 90 days) | High | Not Started |

### Database

| ID | Task | Priority | Status |
|---|---|---|---|
| T-0020 | Write Alembic migration `0001_initial.sql` with column-level DDL: 16 system tables + 6 operational domain tables; CHECK constraints; FK cascades; indexes; ivfflat on `memories.embedding` | High | Not Started |
| T-0021 | Implement repository-pattern interfaces in `packages/state/` for all tables | High | Not Started |
| T-0022 | Implement `audit_log` hash chain in repository writes (`audit_hash`, `prev_audit_hash`) | High | Not Started |
| T-0023 | Seed `users` table with `dev-user` row | High | Not Started |
| T-0024 | Seed `llm_pricing` with verified rates for `claude-sonnet-4-6`, `claude-opus-4-7`, `text-embedding-3-small`; ADR `docs/adr/2026-05-17-llm-pricing-seed.md` records source URLs | High | Not Started |
| T-0025 | Enforce SQL Tool allowlist on `sku_master / inventory / demand_history / supply / cost / customers` | High | Not Started |

### Sample data

| ID | Task | Priority | Status |
|---|---|---|---|
| T-0030 | Hand-author `data/sample/ground_truth/sku_parameters.csv` (30 rows, bucket composition per DESIGN) | High | Not Started |
| T-0031 | Hand-author `data/sample/ground_truth/customer_parameters.csv` (large / small / spot mix, `sku_affinity_json`) | High | Not Started |
| T-0032 | Author `data/sample/ground_truth/README.md` explaining no-access rule; cross-link from `AGENTS.md` | High | Not Started |
| T-0033 | Implement `scripts/generate_sample_data.py` — demand formula (NegBin noise), lognormal lead time, initial inventory rules, seed=42 default, `--seed N` override | High | Not Started |
| T-0034 | Implement missing-data injection: 3 SKUs (deterministic), 2% NULL rate, one 7-day contiguous gap | High | Not Started |
| T-0035 | Implement `scripts/seed_db.py` — reads `data/sample/*.csv` (not `ground_truth/`) via SQLAlchemy | High | Not Started |
| T-0036 | Add `uv run seed` / `make seed` one-command regeneration target | Medium | Not Started |
| T-0037 | Author ADR `docs/adr/2026-05-17-sample-data-generation.md` — distribution choices, seed policy, missing-data pattern | Medium | Not Started |
| T-0038 | Generator unit tests: deterministic output under seed 42; NULL injection rate; seasonal SKUs show > 0.3 amplitude in autocorrelation | Medium | Not Started |

### Configuration

| ID | Task | Priority | Status |
|---|---|---|---|
| T-0040 | `config/risk_thresholds.yaml` — three-tier thresholds (high / medium / low) | High | Not Started |
| T-0041 | `config/kpi_weights.csv` — global default (single row, sums to 1.0) | High | Not Started |
| T-0042 | `config/kpi_weights_overrides.csv` — Critical SKU overrides (service_level=0.50) | High | Not Started |
| T-0043 | `.env.example` with all required keys (no real values) | High | Not Started |

### API

| ID | Task | Priority | Status |
|---|---|---|---|
| T-0050 | FastAPI app skeleton (`apps/api`) with `X-Dev-User` middleware; default `dev-user` when `APP_ENV=dev` | High | Not Started |
| T-0051 | Implement REST endpoint skeletons per DESIGN §API Design (501 where logic is not ready; `/healthz` and `/readyz` real) | High | Not Started |
| T-0052 | Configure FastAPI `CORSMiddleware` — dev (`localhost:3000`) and prod (env-injected); SSE exception for credential | High | Not Started |

### Approvals

| ID | Task | Priority | Status |
|---|---|---|---|
| T-0060 | Approval state-machine logic with `parent_approval_id` chain (revisions create new row) | High | Not Started |
| T-0061 | Sweep job for `expired` (default `approval_ttl_seconds=86400`) | Medium | Not Started |

### Infrastructure

| ID | Task | Priority | Status |
|---|---|---|---|
| T-0070 | Scaffold `infra/terraform/{image-build,acr-push,aca,shared,modules}/` with independent state | High | Not Started |
| T-0071 | Set Azure region = US East 2 in all Terraform modules | High | Not Started |
| T-0072 | Set `prevent_destroy = false`; no resource locks | High | Not Started |
| T-0073 | Provision Azure Key Vault + Managed Identity in `shared/` | High | Not Started |
| T-0074 | Scaffold `infra/compose/` with Docker Compose V2 (no `version:` field): postgres + api + web | High | Not Started |
| T-0075 | Configure Azure OIDC federated credentials with subject claims for `main`, `pull_request`, `environment:prod`; least-privilege RBAC | High | Not Started |

### CI/CD

| ID | Task | Priority | Status |
|---|---|---|---|
| T-0080 | `.github/workflows/lint-test.yml` | High | Not Started |
| T-0081 | `.github/workflows/terraform-plan.yml` (runs on PR) | High | Not Started |
| T-0082 | `.github/workflows/deploy.yml` (runs on `main`): build → acr-push → tf apply shared → tf apply aca | High | Not Started |

### Observability

| ID | Task | Priority | Status |
|---|---|---|---|
| T-0090 | Configure `structlog` JSON output + OpenTelemetry SDK + Langfuse SDK | High | Not Started |
| T-0091 | Provision Azure Monitor / Application Insights in Terraform `shared/`; wire as OTel sink | High | Not Started |

### ADRs (Phase 0)

| ID | Task | Priority | Status |
|---|---|---|---|
| T-0099 | Author initial ADRs for each tech choice: Claude provider, FastAPI, Next.js, Postgres+pgvector, Azure region, Terraform pipeline split, Azure OIDC, backup off | High | Not Started |

## Phase 1 — Decision Copilot (Vertical-Slice MVP)

### Agent runtime

| ID | Task | Priority | Status |
|---|---|---|---|
| T-1001 | Implement `ClaudeClient` with prompt caching enabled; `temperature=0` default | High | Not Started |
| T-1002 | Instrument `LLMClient` to write `llm_usage` rows inside the same DB transaction as the parent `agent_step` | High | Not Started |
| T-1003 | Implement Orchestrator sequential single-LLM loop with role switching (Plan → Tool → Evaluate → Recommend) | High | Not Started |
| T-1004 | Implement 4 `PromptBasedSpecialist` instances (Domain Expert, Data Engineer, Simulator/Optimizer, Evaluator) with role prompts + tool subsets | High | Not Started |
| T-1005 | Implement Orchestrator error handling: 2 retries with backoff (1s, 4s); SSE `error` event; `decision_sessions.status = failed` on terminal failure | High | Not Started |
| T-1006 | Implement Orchestrator trade-off resolution: config defaults + Critical SKU overrides; user policy and session goal hooks present but no-op in MVP | High | Not Started |
| T-1007 | Implement primary + 2 alternatives selection in Recommendation generation | High | Not Started |
| T-1008 | Wire `decision_sessions.status` state machine with optimistic-retry on conflict | High | Not Started |

### Tools

| ID | Task | Priority | Status |
|---|---|---|---|
| T-1010 | SQL Query Tool: read-only on operational tables; allowlisted | High | Not Started |
| T-1011 | Approval Tool: full state machine integration | High | Not Started |
| T-1012 | Audit Log Tool: hash-chained writes | High | Not Started |
| T-1013 | Forecast Tool stub: 28-day moving average over `demand_history`, NULL-aware; `model_version="moving_avg_v1"` | High | Not Started |
| T-1014 | Simulation Tool stub: deterministic projection (`on_hand[t+1] = max(0, on_hand[t] + arrivals[t] - demand[t])`); mean lead time only | High | Not Started |
| T-1015 | Optimizer Tool stub: enumerate `order_qty ∈ {0, MOQ, 2MOQ, …, 5MOQ}`; run Simulator stub; return first 3 feasible by ascending `total_supply_chain_cost` | High | Not Started |
| T-1016 | Evaluator (rule-based) producing `KpiScore[]` per candidate (no collapsed scoring); apply three-tier risk classification | High | Not Started |
| T-1017 | LLM context sanitizer: raw rows never sent to Claude; only summaries / aggregates | High | Not Started |

### Web UI

| ID | Task | Priority | Status |
|---|---|---|---|
| T-1020 | Chat screen: English UI and English agent responses; GFM Markdown rendering (`react-markdown` + `remark-gfm` + `rehype-sanitize` + syntax highlighter + KaTeX + Mermaid lazy load) | High | Not Started |
| T-1021 | Chat session list sidebar; URL `/chat/[sessionId]`; multi-session navigation | High | Not Started |
| T-1022 | Reasoning Panel with SSE consumer; Active Specialist banner; Orchestrator routing log; Step timeline; live status pill; `Cmd/Ctrl + .` toggle | High | Not Started |
| T-1023 | Tool Call Inspector: input / output JSON; executed-SQL syntax-highlighted display; table preview; copy / open-in-audit actions | High | Not Started |
| T-1024 | Scenario Comparison screen: radar chart + parallel coordinates (Recharts) | High | Not Started |
| T-1025 | Recommendation Detail: primary + alternatives + `TradeoffExplanation` + rationale + risk badge | High | Not Started |
| T-1026 | Approval Queue: risk badges + trade-off summary + revision-request weight-vector editor | High | Not Started |
| T-1027 | Audit Timeline: session_id filter + agent / tool / status filters + JSON diff + token / cost summary | High | Not Started |
| T-1028 | KPI Dashboard skeleton with LLM Cost Trend panel | High | Not Started |
| T-1029 | Wire Vercel AI SDK with Claude provider for chat streaming | High | Not Started |
| T-1030 | SSE reconnect with `Last-Event-ID` replay from `audit_log` | High | Not Started |

### Memory and tests

| ID | Task | Priority | Status |
|---|---|---|---|
| T-1040 | MemoryStore stub: `write` persists; `search` returns `[]` | High | Not Started |
| T-1041 | Pytest fixtures: YAML scenarios + `vcrpy` cassettes for LLM calls | High | Not Started |
| T-1042 | Playwright E2E suite covering chat → recommendation → approval → audit | High | Not Started |
| T-1043 | Document English-only convention for code, docs, UI, and chat in `AGENTS.md` | Medium | Not Started |

## Phase 2 — Real Simulator

| ID | Task | Priority | Status |
|---|---|---|---|
| T-2001 | Provision Azure Container Apps Jobs via Terraform `aca/` extension | High | Not Started |
| T-2002 | Implement real Python simulation behind `Simulator` interface | High | Not Started |
| T-2003 | Move Simulator invocation to ACA Jobs trigger | High | Not Started |

## Phase 3 — Real Optimizer

| ID | Task | Priority | Status |
|---|---|---|---|
| T-3001 | Implement OR-Tools / PuLP optimizer behind `Optimizer` interface | High | Not Started |
| T-3002 | Move Optimizer invocation to ACA Jobs trigger | High | Not Started |

## Phase 4 — Approval Workflow Expansion + Budget Enforcement

| ID | Task | Priority | Status |
|---|---|---|---|
| T-4001 | Notifications for new pending approvals | Medium | Not Started |
| T-4002 | Approver roles + permission checks | Medium | Not Started |
| T-4003 | Settings / Policies screen with budget threshold editors | High | Not Started |
| T-4004 | LLM budget soft / hard ceiling interceptor in `LLMClient` | High | Not Started |

## Phase 5 — Job Orchestration

| ID | Task | Priority | Status |
|---|---|---|---|
| T-5001 | Provision Azure Cache for Redis via Terraform `shared/` | High | Not Started |
| T-5002 | Deploy Celery worker on ACA via Terraform `aca/` extension | High | Not Started |
| T-5003 | Swap `JobRunner` sync implementation for Celery implementation; callers unchanged | High | Not Started |

## Phase 6 — Real Predictor

| ID | Task | Priority | Status |
|---|---|---|---|
| T-6001 | Provision Databricks workspace + MLflow via new Terraform stage | High | Not Started |
| T-6002 | Databricks Job for predictor training | High | Not Started |
| T-6003 | Databricks Job for batch inference writing features back to PostgreSQL | High | Not Started |
| T-6004 | Implement lightweight realtime inference in FastAPI in-process | Medium | Not Started |

## Phase 7 — Memory & Learning Loop

| ID | Task | Priority | Status |
|---|---|---|---|
| T-7001 | Swap MemoryStore stub for pgvector retrieval | High | Not Started |
| T-7002 | Memory-write hooks in Orchestrator (record weight vector on approval / rejection / revision) | High | Not Started |
| T-7003 | Wire `user_policy` memory back into Orchestrator's default weight selection | High | Not Started |

## Phase 8 — Semi-Autonomous Execution + Databricks Lakehouse

| ID | Task | Priority | Status |
|---|---|---|---|
| T-8001 | Risk-classified auto-execution policy in Approval flow | High | Not Started |
| T-8002 | Provision Databricks Lakehouse (ADLS Gen2 + Delta + workspace) in US East 2 | High | Not Started |
| T-8003 | Set up CDC ingestion from PostgreSQL to Bronze layer | High | Not Started |
| T-8004 | Define Silver / Gold transformation pipelines | High | Not Started |

## Phase 9 — Business Decision OS Completion

| ID | Task | Priority | Status |
|---|---|---|---|
| T-9001 | Split Domain Expert into Forecast / Inventory / Procurement / Production / Cost specialists | High | Not Started |
| T-9002 | Swap `PromptBasedSpecialist` for `AgentBasedSpecialist` (independent context, independent tool registry, parallel execution) | High | Not Started |
| T-9003 | Orchestrator becomes pure coordinator dispatching to parallel Specialist agents | High | Not Started |
