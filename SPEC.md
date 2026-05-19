# Project Specification

## Goal

Build the **Business Decision OS** — an agent with a simulatable learning model. The LLM acts as control tower (context, planning, tool selection, explanation), while business data, prediction, simulation, optimization, evaluation, human approval, and audit logs are integrated into a structured decision loop:

```
Observe → Understand State → Predict → Simulate → Optimize → Recommend → Approve → Execute → Evaluate → Record → Learn / Update
```

## Problem

Operational supply chain decisions (forecast, inventory policy, replenishment, procurement) require simultaneous reasoning across multiple trade-off KPIs under hard constraints. Existing tools force users to pick one of: a forecasting model, a BI dashboard, a workflow tool, or a chat assistant. None of them close the loop — observe → decide → approve → execute → evaluate → learn. The Business Decision OS integrates these as parts of a single auditable loop.

## Users

- **Primary:** supply chain operators making daily / weekly inventory and replenishment decisions.
- **Secondary:** engineers maintaining the system (engineer-debug visibility is a first-class product surface).
- **Tertiary:** future enterprise tenants once auth and multi-tenancy are bolted on.

## Scope

### In Scope

- Inventory / demand / replenishment decisions on synthetic supply chain data (30 SKUs, 24 months).
- Trade-off KPI reasoning: Service Level × Inventory Cost × Supply Constraint (simultaneously, not single-axis).
- Multi-agent architecture from Day 1: Orchestrator + 4 Specialists (Domain Expert, Data Engineer, Simulator/Optimizer, Evaluator).
- Recommendation with primary + ≥ 2 alternatives at different trade-off positions.
- Human-in-the-loop approval with revision-request loop.
- Full audit trail with tamper-evident hash chain.
- LLM cost tracking and budget enforcement (observation Day 1, ceilings Phase 4+).
- Engineer debug visibility as a permanent, in-product feature.
- Multi-session per user via the chat UI.

### Out of Scope

- Real ERP / customer data integration (synthetic data only).
- Real-time model training in production (analytics path reserved for Phase 8+).
- Multi-tenancy (deferred until requirement appears).
- Disaster recovery / regulatory compliance (backups disabled for MVP).
- Mobile / native apps.

## Core Features

- **Decision Copilot:** natural-language requests answered with data-grounded analysis, multi-candidate recommendations, and explicit trade-off explanations.
- **Scenario Comparison:** radar / parallel-coordinates visualization of per-KPI scores across candidates.
- **Approval Queue:** risk-tiered review with weight-vector revision-request flow.
- **Audit Timeline:** filterable history of agent steps, tool calls, recommendations, approvals, evaluations.
- **KPI Dashboard:** Service Level / Inventory Cost / Stockout / Working Capital trends + LLM Cost Trend panel.
- **Engineer Debug Surface:** Reasoning Panel (active Specialist, routing log, step timeline) + Tool Call Inspector (input / executed SQL / output) embedded in user-facing screens, toggled via `Cmd/Ctrl + .`.

## Tech Stack

### Frontend

- Next.js (App Router) + TypeScript + `npm`.
- shadcn/ui + Radix + Tailwind CSS (copy-in, no lock-in).
- Recharts for radar and parallel coordinates.
- TanStack Query + Zustand + React Hook Form + Zod.
- Vercel AI SDK with Anthropic Claude provider for chat streaming.
- SSE for Approval queue / Audit timeline / Chat reasoning panel.
- GFM Markdown with KaTeX + Mermaid Day 1.

### Backend

- FastAPI (Python 3.12+, `uv` workspace).
- SQLAlchemy 2.x async + Alembic + asyncpg.
- Repository pattern in `packages/state/`.
- `X-Dev-User` middleware in MVP; Entra ID OIDC after bolt-on.

### Database

- PostgreSQL 16 + pgvector single store for all transactional system data.
- Local dev: `pgvector/pgvector:pg16` in Docker Compose V2 (pgvector required for migration 0001).
- Azure: Azure Database for PostgreSQL Flexible Server (Burstable SKU).
- Migration 0001 covers Phase 0–9 fields — no additive schema migrations for new features.

### AI / LLM

- Anthropic Claude Sonnet 4.6 (default) via provider-agnostic `LLMClient` interface.
- Azure OpenAI `text-embedding-3-small` (1536d) for embeddings.
- Prompt caching enabled by default; `temperature=0` everywhere.
- `vcrpy` cassettes block real API calls in unit / integration tests.
- Langfuse for LLM tracing; OpenTelemetry for spans.

### Infrastructure

- Azure region: US East 2 for all resources.
- Terraform pipeline split: `image-build/` → `acr-push/` → `aca/` (Azure Container Apps), with `shared/` for stateful infra (Postgres, Key Vault, OpenAI, Monitor / App Insights).
- Docker Compose V2 for local development.
- GitHub Actions CI/CD with Azure OIDC federated credentials (no long-lived secrets).
- Secrets via Azure Key Vault + Managed Identity at runtime.

## Non-Functional Requirements

### Security

- TLS enforced on all DB connections (`sslmode=require`).
- DB firewall restricted to GitHub Actions OIDC ranges + developer IPs (no `0.0.0.0/0`).
- No PII in sample data (synthetic SKU / customer IDs only).
- LLM never receives raw row data — only summaries / aggregates.
- `audit_log` tamper-evident hash chain (`audit_hash` references `prev_audit_hash`).
- No secrets in repo (`.env.example` only).
- SQL Tool allowlist: `sku_master`, `inventory`, `demand_history`, `supply`, `cost`, `customers`.
- Ground-truth data files (`data/sample/ground_truth/`) excluded from agent corpus and never loaded into the DB.

### Performance

- Frontend (Core Web Vitals): LCP < 2.5s, INP < 200ms, CLS < 0.1.
- Frontend JS budget (app page, gzipped): < 300 kB.
- Backend agent step: synchronous in MVP; mid-weight work moves to ACA Jobs in Phase 2–3; async queue in Phase 5.

### Cost

- Backup disabled for MVP (explicit, reversible).
- PostgreSQL on Burstable SKU.
- Every LLM call recorded with tokens + per-axis cost in USD (`llm_usage` table).
- Cost-saving defaults Day 1: prompt caching, `temperature=0`, prompt segmentation for cache hits, aggregation before LLM, cassette-blocked test calls.
- Budget enforcement: observation only Day 1; soft / hard ceilings Phase 4+ (per-session / per-day / per-month independent).

### Observability

- `structlog` JSON logs + OpenTelemetry traces + Langfuse LLM tracing wired Day 1.
- Sink: Azure Monitor / Application Insights provisioned by Terraform `shared/`.
- Every LLM call linked as a Langfuse generation event with OTel span attributes (`llm.provider`, `llm.model`, `llm.input_tokens`, `llm.output_tokens`, `llm.total_cost_usd`).

## Constraints

- **Final-form-first development.** All 10 architectural components exist Day 1 with production-grade interfaces. Phases fill in implementations behind stable interfaces — they never add new modules. Authentication is the only documented exception.
- **Currency:** USD throughout (data, KPI, UI, recommendations).
- **Language policy:** English for all user-visible text (UI chrome, chat dialogue, agent narrative in the UI). English for source code, documentation, comments, identifiers, log messages, commit messages, PR titles & bodies.
- **Multi-agent from Day 1.** Single-agent simplifications are forbidden — the Specialist split is a load-bearing architectural commitment.
- **No raw rows to LLM.** Summaries / aggregates only.
- **All decisions persisted with rationale and inputs.** No input-less decisions, no rationale-less recommendations, no history-less executions.
- **Approval state machine non-mutating on closed rows.** Revisions create a new `approvals` row with `parent_approval_id` set; original row is preserved for audit.
- **Cost tracking inside `LLMClient` middleware.** No call-site logging path that bypasses recording.
