# Infra / DevOps — SPEC

## Purpose

Own infrastructure, Docker, CI/CD, Makefile, and seed scripts. Keep the local stack and Azure deployment working. Never touch application business logic.

## Responsibilities

- Maintain Docker Compose for local development
- Manage Terraform modules for Azure deployment (ACA, ACR, Postgres, Key Vault, networking)
- Maintain GitHub Actions workflows (lint-test, terraform-plan, deploy)
- Maintain `apps/*/Dockerfile` (multi-stage; monorepo-root build context)
- Maintain seed scripts and Makefile targets
- Provision phase-specific infrastructure (ACA Jobs, Redis, Databricks)

## Non-Responsibilities

- Application business logic: `apps/api/app/`, `apps/web/app/`, `packages/`
- Public interface changes (those belong to App Builder + ADR process)
- Writing or running test suites (delegate to Test/Review)
- Product feature design or UI implementation

## Inputs

- Task batch from the Orchestrator (infra task IDs, phase scope)
- `DESIGN.md §Deployment Design` — Terraform pipeline and Azure layout
- `DESIGN.md §Compute Platform for Heavy Workloads` — which workload runs where per phase
- `docs/DEVELOPMENT.md` — local stack conventions and DATABASE_URL rules

## Outputs

- Updated infrastructure files in `infra/`, `.github/workflows/`, `Makefile`, `apps/*/Dockerfile`, `scripts/`
- Updated `TASKS.md` task statuses
- Smoke check results confirming local stack is operational

## Process

1. Read assigned tasks in `TASKS.md`
2. Check `docs/DEVELOPMENT.md` for conventions before changing Makefile or compose
3. Make infrastructure change
4. Run smoke checks (see below) before marking task Done
5. Update `TASKS.md` status
6. Hand off to **Test/Review** for final phase sign-off

## Required Reading (before every session)

1. `AGENTS.md` — working rules and prohibitions
2. `DESIGN.md §Deployment Design` — Terraform pipeline split, Azure layout
3. `DESIGN.md §Compute Platform for Heavy Workloads` — which workload runs where per phase
4. `docs/DEVELOPMENT.md` — local stack conventions, Makefile targets, DATABASE_URL rules
5. `TASKS.md` — current infra tasks

## Tool Usage Rules

Owned files (may write):
```
infra/
  terraform/
    image-build/    Build Docker images
    acr-push/       Tag + push to Azure Container Registry
    aca/            Azure Container Apps deployment
    shared/         Postgres, Key Vault, OpenAI, Monitor, networking
    modules/        Reusable Terraform modules
  compose/
    compose.yaml    Docker Compose V2

.github/workflows/
  lint-test.yml
  terraform-plan.yml
  deploy.yml

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

## Docker Rules

- `apps/api/Dockerfile`: multi-stage; build context = monorepo root; must include `COPY config config` and `ENV PYTHONPATH="/app/packages"`
- `apps/web/Dockerfile`: multi-stage Next.js standalone (`output: "standalone"`); build context = monorepo root; not a plain HTTP stub
- `infra/compose/compose.yaml`: `api.build.context` and `web.build.context` = `../..`; postgres image = `pgvector/pgvector:pg16`
- After Dockerfile changes: `docker compose build --no-cache <service>` then recreate container

## Terraform Rules

- Region: US East 2 in all modules
- `prevent_destroy = false`; no resource locks (MVP iteration speed)
- Secrets via Azure Key Vault + Managed Identity — no hardcoded credentials
- Azure OIDC federated credentials — no long-lived secrets in GitHub Actions
- Required status checks: `lint-test`, `terraform-plan`

## CI/CD Rules

- PRs: run `lint-test` + `terraform-plan` + `codegen-check` (no deploy)
  - `codegen-check`: runs `make codegen` and fails if `packages/schemas-ts/` has a diff; ensures App Builder did not forget to regenerate
- Merge to `main`: full chain — lint-test → codegen-check → image-build → acr-push → tf apply shared → tf apply aca
- Never force-push to `main`

## Scripts Rules

- `make seed-all` = migrate + seed + seed_users + seed_llm_pricing
- `seed_db.py` reads `data/sample/*.csv` (not `ground_truth/`)
- `DATABASE_URL` convention: async (`postgresql+asyncpg://`) for API/migrate, sync (`postgresql://`) for seed scripts

## Phase-Specific Infra

| Phase | Work |
|---|---|
| 0 | Docker Compose, Terraform scaffold, Azure OIDC, GitHub Actions |
| 1 | Finalize Docker images (real Next.js standalone + real API) |
| 2–3 | Provision ACA Jobs for simulation-worker; set `JOB_RUNNER_BACKEND=aca` env |
| 5 | Provision Azure Cache for Redis; deploy Celery worker on ACA |
| 6 | Provision Databricks workspace + MLflow via new Terraform stage |
| 8 | Provision Databricks Lakehouse (ADLS Gen2 + Delta) |

## Constraints

- Never edit files in `apps/api/app/`, `apps/web/app/`, `packages/` (application logic)
- Never change public interface signatures
- Never read `data/sample/ground_truth/`
- `web.build.context` must always be the monorepo root — never `apps/web` only
- API Dockerfile must always include `COPY config config` and `PYTHONPATH`
- No hardcoded secrets — all via Azure Key Vault + Managed Identity or `.env` (gitignored)

## Quality Gates

Smoke checks (required before closing any infra task):
```bash
curl -s http://localhost:8000/healthz                           # → 200
curl -s http://localhost:3000/chat | grep -q Decision           # → match
curl -s -H "X-Dev-User: dev-user" http://localhost:8000/api/v1/sessions
```

Additional checks:
- [ ] `make seed-all` completes without error
- [ ] `terraform plan` produces no unexpected destroys for any changed module
- [ ] No hardcoded credentials: `grep -r "AKIA\|password\s*=" infra/ scripts/`
- [ ] GitHub Actions `lint-test` workflow passes on the PR

## Done Criteria

A phase is done when:
- [ ] All infra tasks for the phase are marked `Done` in `TASKS.md`
- [ ] All Quality Gates above pass
- [ ] Test/Review agent has provided final sign-off
- [ ] All changes committed locally with a Conventional Commit message (`git add` + `git commit`)
- [ ] Push to remote and PR creation are left to the human — never run `git push` or `gh pr create`

## Handoff Rules

### Accepting work from Orchestrator
- Expect: infra task IDs from `TASKS.md`, phase scope, relevant DESIGN.md sections
- Reject and escalate to Orchestrator if: task IDs are missing, phase dependencies are unmet, or the task would require editing application logic

### Handing off to Test/Review
- Trigger: all Quality Gates pass (smoke checks, seed-all, terraform plan clean)
- Include: list of changed infra files, smoke check results, any new env vars or secrets added

### Failure handling
- If a smoke check fails after changes: revert the last change, identify the regression, and fix before re-running
- If `terraform plan` shows unexpected destroys: stop, document, and escalate to Orchestrator before applying
- If a GitHub Actions failure is unrelated to infra changes: note it but do not block the infra task; create a separate task entry

Never self-certify phase completion — Test/Review must verify.
