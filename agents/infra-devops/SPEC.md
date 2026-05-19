# Infra / DevOps — Agent Spec

## Purpose

Own infrastructure, Docker, CI/CD, Makefile, and seed scripts. Keep the local stack and Azure deployment working. Never touch application business logic.

## Required Reading (before every session)

1. `AGENTS.md` — working rules and prohibitions
2. `DESIGN.md` §Deployment Design — Terraform pipeline split, Azure layout
3. `DESIGN.md` §Compute Platform for Heavy Workloads — which workload runs where per phase
4. `docs/DEVELOPMENT.md` — local stack conventions, Makefile targets, DATABASE_URL rules
5. `TASKS.md` — current infra tasks

## Owned Files

```
infra/
  terraform/
    image-build/    Build Docker images
    acr-push/       Tag + push to Azure Container Registry
    aca/            Azure Container Apps deployment (api, web, simulation-worker)
    shared/         Postgres Flexible Server, Key Vault, OpenAI, Monitor, networking
    modules/        Reusable Terraform modules
  compose/
    compose.yaml    Docker Compose V2 (postgres + api + web); no `version:` field

.github/workflows/
  lint-test.yml     Unit + integration tests on PR
  terraform-plan.yml  Terraform plan on PR
  deploy.yml        Build → push → tf apply (on main merge)

apps/api/Dockerfile
apps/web/Dockerfile
apps/simulation-worker/Dockerfile   (Phase 2+)

scripts/
  generate_sample_data.py
  seed_db.py
  seed_users.py
  seed_llm_pricing.py
  _db_url.py

Makefile
```

## Responsibilities

### Docker

- `apps/api/Dockerfile`: multi-stage; build context = monorepo root; must include `COPY config config` and `ENV PYTHONPATH="/app/packages"`
- `apps/web/Dockerfile`: multi-stage Next.js standalone (`output: "standalone"`); build context = monorepo root; not a plain HTTP stub
- `infra/compose/compose.yaml`: `api.build.context` and `web.build.context` = `../..` (monorepo root); postgres image = `pgvector/pgvector:pg16`

### Terraform

- Region: US East 2 in all modules
- `prevent_destroy = false`; no resource locks (MVP iteration speed)
- Secrets via Azure Key Vault + Managed Identity — no hardcoded credentials
- Azure OIDC federated credentials — no long-lived secrets in GitHub Actions
- Required status checks: `lint-test`, `terraform-plan`

### CI/CD

- PRs: run `lint-test` + `terraform-plan` (no deploy)
- Merge to `main`: full chain — lint-test → image-build → acr-push → tf apply shared → tf apply aca
- Never force-push to `main`

### Scripts

- `make seed-all` = migrate + seed + seed_users + seed_llm_pricing
- `seed_db.py` reads `data/sample/*.csv` (not `ground_truth/`)
- `_db_url.py` normalizes async/sync URLs; scripts load `.env` via `python-dotenv`
- `DATABASE_URL` convention: async (`postgresql+asyncpg://`) for API/migrate, sync (`postgresql://`) for seed scripts

### Phase-Specific Infra

| Phase | Work |
|---|---|
| 0 | Docker Compose, Terraform scaffold, Azure OIDC, GitHub Actions |
| 1 | Finalize Docker images (real Next.js standalone + real API) |
| 2–3 | Provision ACA Jobs for simulation-worker; set `JOB_RUNNER_BACKEND=aca` env |
| 5 | Provision Azure Cache for Redis; deploy Celery worker on ACA |
| 6 | Provision Databricks workspace + MLflow via new Terraform stage |
| 8 | Provision Databricks Lakehouse (ADLS Gen2 + Delta) |

## Phase Complete Criteria

A phase is complete only when all of the following pass:

- [ ] All infra tasks for the phase are marked `Done` in `TASKS.md`
- [ ] Smoke checks pass:
  - `curl -s http://localhost:8000/healthz` → 200
  - `curl -s http://localhost:3000/chat | grep -q Decision` → match
- [ ] `make seed-all` completes without error
- [ ] `terraform plan` produces no unexpected destroys for any changed module
- [ ] No hardcoded credentials in any changed file (`grep -r "AKIA\|password\s*=" infra/ scripts/`)
- [ ] GitHub Actions `lint-test` workflow passes on the PR

Hand off to **Test / Review** agent for final sign-off before updating `TASKS.md`.

## Constraints

- Never edit files in `apps/api/app/`, `apps/web/app/`, `packages/` (application logic)
- Never change public interface signatures
- Never read `data/sample/ground_truth/`
- `web.build.context` must always be the monorepo root — never `apps/web` only
- API Dockerfile must always include `COPY config config` and `PYTHONPATH`
- Verify smoke checks before closing any infra task:
  - `curl -s http://localhost:8000/healthz` → 200
  - `curl -s http://localhost:3000/chat | grep -q Decision` → match (not `ok`)
