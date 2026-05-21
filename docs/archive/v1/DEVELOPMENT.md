# Development Guide

Operational reference for setting up and running the local stack. Normative for any agent session — do not rely on chat history.

## First-time setup

1. Copy env template: `cp .env.example .env` (gitignored). Set `ANTHROPIC_API_KEY` only if exercising real LLM calls; the stack starts without it.
2. Install deps: `uv sync` at repo root; `npm install` when working on `apps/web`.
3. `uv.lock` is **committed** (reproducible `uv sync --frozen` in Docker and CI).

## Stack (`make dev`)

```bash
make dev   # docker compose -f infra/compose/compose.yaml up -d
```

| Service | Notes |
|---|---|
| **postgres** | Image `pgvector/pgvector:pg16` (not plain `postgres:16`) — migration `0001` runs `CREATE EXTENSION vector`. |
| **api** | Build **context = monorepo root**; `dockerfile: apps/api/Dockerfile`. Copies `pyproject.toml`, `uv.lock`, `apps/api`, `packages/`, `config/`. Sets `PYTHONPATH=/app/packages`. |
| **web** | Build **context = monorepo root**; `dockerfile: apps/web/Dockerfile` (Next.js `standalone`, port 3000). |

Root `.dockerignore` trims build context; it is versioned (not gitignored).

Smoke checks (API + web):

```bash
curl -s http://localhost:8000/healthz
curl -s http://localhost:8000/readyz   # requires DB reachable
curl -s http://localhost:3000/chat | head -c 200 | grep -q Decision && echo "web UI ok"
```

## Makefile targets

| Target | What it does |
|---|---|
| `make dev` | Docker Compose: postgres (pgvector), api, web |
| `make migrate` | Alembic upgrade head (`MIGRATE_DATABASE_URL`, async) |
| `make seed` | Regenerate `data/sample/*.csv` + load operational tables |
| `make seed-all` | `migrate` + `seed` + `seed_users.py` + `seed_llm_pricing.py` |

Prefer **`make seed-all`** on a fresh database. Use `make seed` alone when schema is already migrated and only CSV data should be refreshed.

## Database migrate + seed

Run **after** Postgres is healthy (`make dev`):

```bash
make seed-all  # recommended first time: migrate + CSVs + dev-user + llm_pricing
# or stepwise:
make migrate
make seed
```

**Alembic import path:** `packages/state/alembic.ini` sets `prepend_sys_path = ..` so `from state.models import Base` resolves with `packages/` on `sys.path` (same as pytest `pythonpath = ["packages"]`).

## `DATABASE_URL` conventions

| Consumer | URL shape | Default when unset |
|---|---|---|
| **API** (compose / `.env`) | `postgresql+asyncpg://dev:dev@postgres:5432/...` (in compose) or `...@localhost:5432/...` (host) | See `.env.example` |
| **`make migrate`** | Async — `MIGRATE_DATABASE_URL` in Makefile | `postgresql+asyncpg://dev:dev@localhost:5432/business_decision_os` |
| **`make seed`** | Sync — `DATABASE_URL` in Makefile; `scripts/seed_db.py` strips `+asyncpg` | `postgresql://dev:dev@localhost:5432/business_decision_os` |
| **`make seed-all`** | Same sync URL for `scripts/seed_users.py` and `scripts/seed_llm_pricing.py` | Same as `make seed` |

Seed scripts load `.env` via `python-dotenv` when available (`scripts/_db_url.py`), then apply Makefile/env defaults.

`CORS_ORIGINS` in `.env` is a comma-separated string or JSON list; API settings normalize it (do not pass a bare list format pydantic cannot parse).

## Web (host dev, optional)

When iterating on UI without the web container:

```bash
npm install   # repo root (workspaces)
npm run dev   # http://localhost:3000 — apps/web
```

Set `NEXT_PUBLIC_API_URL` in `.env` for browser calls to the API. Compose injects the same value into the web service.

## Compute worker (`simulation-worker`) — Phase 2+

- Local / CI default: `JOB_RUNNER_BACKEND=in_process` (no Azure required).
- Production: `JOB_RUNNER_BACKEND=aca` with `ACA_SIMULATION_JOB_RESOURCE_ID` and `ACA_OPTIMIZATION_JOB_RESOURCE_ID` (Terraform `aca/` outputs).
- Image `apps/simulation-worker/Dockerfile` runs both `JOB_KIND=simulation` and `JOB_KIND=optimization` via `apps/simulation-worker/run_job.py`.
- After changing `packages/simulation/`, `packages/optimization/`, or worker entrypoint: rebuild and push `simulation-worker`, not only the API image.

## Common failures

| Symptom | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: No module named 'state'` on migrate | `prepend_sys_path` still `.` | Set `prepend_sys_path = ..` in `alembic.ini`. |
| `extension "vector" is not available` | Plain Postgres image | Use `pgvector/pgvector:pg16` in compose. |
| `make seed` asks for `DATABASE_URL` | No env / dotenv | Use `make seed-all` (Makefile default) or set `.env`. |
| `KeyError: DATABASE_URL` in `seed_users.py` | Script run without Makefile env | Use `make seed-all` or rely on `_db_url.py` defaults + `.env`. |
| API exits on startup (CORS / logging) | Invalid `CORS_ORIGINS` or structlog before configure | See `apps/api/app/config.py`, `logging_config.py`. |
| Docker build `COPY apps/api/app not found` | API build context is `apps/api` only | Context must be **repo root**; see compose `api.build`. |
| Web cannot reach API | Wrong `NEXT_PUBLIC_API_URL` | Host dev: `http://localhost:8000` in `.env` / `.env.example`. |
| Browser shows only `ok` or blank | Web container is a stub or stale image | Use real Next.js standalone build; `docker compose build web --no-cache`. |
| `GET /api/v1/sessions` returns **501** | Stale API image | Rebuild `api` with `--no-cache`; verify `COPY config` and `PYTHONPATH` in Dockerfile. |
| `FileNotFoundError: config/risk_thresholds.yaml` in API logs | API image missing `COPY config` | Rebuild `api`; verify `test -f /app/config/risk_thresholds.yaml` in container. |
| `ModuleNotFoundError: No module named 'agent'` on API startup | Missing `PYTHONPATH=/app/packages` in Dockerfile | Add `ENV PYTHONPATH="/app/packages"` in `apps/api/Dockerfile`; rebuild. |
