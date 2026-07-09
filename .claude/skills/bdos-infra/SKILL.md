---
name: bdos-infra
description: Infra/DevOps agent for Business Decision OS. Use when working on Terraform, Docker Compose, GitHub Actions CI/CD, Dockerfiles, Makefile, or seed scripts. Never touches application business logic.
---

# Infra / DevOps — SKILL

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
- `docs/DESIGN.md §Deployment Design` — Terraform pipeline and Azure layout
- `docs/DESIGN.md §Compute Platform for Heavy Workloads` — which workload runs where per phase

## Outputs

- Updated infrastructure files in `infra/`, `.github/workflows/`, `Makefile`, `apps/*/Dockerfile`, `scripts/`
- Updated `docs/TASKS.md` task statuses
- Smoke check results confirming local stack is operational

## Process

1. Read assigned tasks in `docs/TASKS.md`
2. Make infrastructure change
3. Run smoke checks (see below) before marking task Done
4. Update `docs/TASKS.md` status
5. Hand off to **Test/Review** for final phase sign-off

## Required Reading (before every session)

Always read:
1. `AGENTS.md` — working rules and prohibitions
2. `docs/TASKS.md` — current infra tasks

Read only when relevant:

| Task type | Also read |
|---|---|
| Terraform / Azure changes | `docs/DESIGN.md §Deployment Design` |
| Worker / heavy workloads | `docs/DESIGN.md §Compute Platform for Heavy Workloads` |

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

Compose/Dockerfile conventions (multi-stage, healthchecks, build context, secrets-via-env) are owned by `.claude/rules/docker.md`. Current service topology, ports, and the Postgres image are owned by `docs/DESIGN.md §Deployment Design §Local Development Stack` / `§Database Conventions`. Do not restate either here.

- `apps/api/Dockerfile` (and `.dev` variant): must include `COPY config config` and `ENV PYTHONPATH="/app/packages"` — the app imports `packages/` and `config/` at runtime; a Dockerfile change that drops either breaks the container silently.
- `apps/web/Dockerfile`: must be a real multi-stage Next.js standalone build — never a plain HTTP stub.
- After any Dockerfile change: `docker compose build --no-cache <service>` then recreate the container before smoke-checking.

## Terraform Rules

Region, freeze status, module layout, and the secrets/OIDC convention are owned by `docs/DESIGN.md §Deployment Design §Azure / Terraform (Frozen Target State)`. Do not restate here.

- This infra is frozen per the P69 decision — do not run `terraform apply` against `shared`/`aca`, and do not uncomment the Postgres skeleton, without explicit Orchestrator + user sign-off.
- Always run `terraform plan` after a module change and confirm it produces no unexpected destroys before proceeding.

## CI/CD Rules

Current workflow/job shape is owned by `docs/DESIGN.md §Deployment Design §CI/CD Pipeline`. Do not restate here.

- Never force-push to `main`.
- If a GitHub Actions failure is unrelated to your infra change, note it in `docs/TASKS.md` but do not block your task on it (see Failure Handling below).

## Scripts Rules

The `DATABASE_URL` convention (async vs. sync) is owned by `docs/DESIGN.md §Deployment Design §Database Conventions`. Do not restate here.

- `make seed-all` = migrate + seed + seed_users + seed_llm_pricing
- `seed_db.py` reads `data/sample/*.csv` only — never `ground_truth/` (universal prohibition, `AGENTS.md §Prohibitions`)

## Constraints

> Universal prohibitions (secrets, ground_truth, public interfaces without ADR, web.build.context, etc.) → **AGENTS.md §Prohibitions**

- Never edit files in `apps/api/app/`, `apps/web/app/`, `packages/` (application logic)

## Quality Gates

Smoke checks (required before closing any infra task):

> Before running curl checks, run `docker compose ps`. If no services are `Up`, note "stack not running — smoke checks skipped" in `docs/TASKS.md` and proceed to the remaining checklist items below. Skip conditions apply in CI contexts and pure-file-edit tasks.

```bash
make dev-smoke                                                   # API healthz on $(API_PORT) (default 8002)
curl -sf "http://localhost:${WEB_PORT:-3002}/chat" | grep -q Decision
curl -s -H "X-Dev-User: dev-user" "http://localhost:${API_PORT:-8002}/api/v1/sessions"
```

Additional checks:
- [ ] `make seed-all` completes without error
- [ ] `terraform plan` produces no unexpected destroys for any changed module
- [ ] No hardcoded credentials: `grep -r "AKIA\|password\s*=" infra/ scripts/`
- [ ] GitHub Actions `lint-test` workflow passes on the PR

## Done Criteria

A phase is done when:
- [ ] All infra tasks for the phase are marked `Done` in `docs/TASKS.md`
- [ ] All Quality Gates above pass
- [ ] All changes committed locally with a Conventional Commit message (`git add` + `git commit`)
- [ ] Push to remote and PR creation are left to the human — never run `git push` or `gh pr create`

## Handoff Rules

### Accepting work from Orchestrator
- Expect: infra task IDs from `docs/TASKS.md`, phase scope, relevant docs/DESIGN.md sections
- Reject and escalate to Orchestrator if: task IDs are missing, phase dependencies are unmet, or the task would require editing application logic

### Handing off to Test/Review
- Trigger: all Quality Gates pass (smoke checks, seed-all, terraform plan clean)
- Write a handoff summary as a block comment in `docs/TASKS.md` under the last completed task:
  ```
  ## Infra Handoff — Phase N
  Changed files: <list>
  Smoke checks: PASS / SKIPPED (reason)
  New env vars: <list or "none">
  ```
- Set the individual task rows to `Done`. Orchestrator updates batch-level status once Test/Review sign-off is received.

### Failure handling
- If a smoke check fails after changes: run `git diff --stat` to identify changed files, then `git checkout -- <file>` to revert, identify the regression, and fix before re-running
- If `terraform plan` shows unexpected destroys: stop, document, and escalate to Orchestrator before applying
- If a GitHub Actions failure is unrelated to infra changes: note it but do not block the infra task; create a separate task entry

