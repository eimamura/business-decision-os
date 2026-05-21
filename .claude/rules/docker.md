# Docker Compose V2 Rules

## Compose File

- File name: `compose.yaml` (V2 convention; `docker-compose.yml` is legacy)
- No `version:` top-level key — it is deprecated and ignored in Compose V2
- Service names: lowercase, hyphen-separated

## Health Checks and Dependencies

- Every service must define a `healthcheck` block
- Use `depends_on` with `condition: service_healthy` — never bare `depends_on` without a condition

## Volumes and Ports

- Named volumes for all persistent data
- Host port bindings: use env var substitution (`"${PORT:-8000}:8000"`) — no hardcoded host ports

## Build Context

- `build.context` must be the monorepo root so Dockerfiles can `COPY` from any workspace member

## Secrets / Credentials

- All secrets via environment variables sourced from `.env`; never inline values in `compose.yaml`

## Dockerfiles (multi-stage)

- Stage 1 (`builder`): install all dependencies including dev tools
- Stage 2 (`runtime`): copy only the built artifacts; install production deps only
- Final image runs as a non-root user
- No `--privileged` containers

## Workers

- Separate Compose service per worker type; reuse the same image with a `command` override rather than building a duplicate image
