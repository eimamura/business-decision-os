# ADR-0002: FastAPI + Python + uv as Backend Stack

**Date:** 2026-05-17  
**Status:** Accepted  
**Deciders:** Engineering Team

## Context

The system requires a backend that can orchestrate multiple LLM-backed agents, expose a REST API with SSE streaming, and eventually integrate with simulation, optimization, and ML libraries. The backend must support async I/O to avoid blocking under concurrent LLM calls, and must work seamlessly in a monorepo alongside Python data-science packages.

## Decision

Use **FastAPI** as the web framework with **Python** as the language and **uv** as the package manager and workspace tool. The root `pyproject.toml` declares `tool.uv.workspace.members = ["apps/api", "packages/*"]`, unifying all Python packages under a single lockfile.

## Rationale

- **Async-native:** FastAPI is built on Starlette/asyncio. The LLM and DB calls are async throughout (`asyncpg`, `httpx`), which maps naturally to `async def` route handlers and avoids thread-pool overhead.
- **SSE streaming:** FastAPI's `StreamingResponse` and `EventSourceResponse` patterns integrate cleanly with the SSE endpoint (`GET /api/v1/sessions/{id}/stream`).
- **Python ecosystem alignment:** Simulation (NumPy/SciPy), optimization (OR-Tools/PuLP), ML (scikit-learn/statsmodels), and LLM SDKs (`anthropic`) are all Python-native. Using Python end-to-end avoids an FFI boundary.
- **uv speed:** `uv` resolves and installs dependencies an order of magnitude faster than `pip` and supports workspace mode for monorepo use.
- **Pydantic integration:** FastAPI uses Pydantic for request/response validation, consistent with the project's schema-first approach.

## Trade-offs

- **Python GIL:** CPU-bound work (heavy simulation, optimization) is blocked by the GIL. Mitigated by moving heavy compute to ACA Jobs (Phase 2–3) and Celery workers (Phase 5), which run in separate processes.
- **uv familiarity:** Developers accustomed to `pip` or `poetry` face a small learning curve. The speed and workspace benefits outweigh the transition cost.
- **Less mature than Node/Spring for some integrations:** Enterprise integrations (e.g., SAP connectors, LDAP) are more common in JVM or Node ecosystems. Not a concern for MVP scope.

## Consequences

- `apps/api` contains the FastAPI application; all Python packages in `packages/` are installed as editable workspace members.
- All LLM, DB, and external HTTP calls use `async`/`await`.
- Heavy compute (simulation, optimization) is dispatched via the `JobRunner` interface; Phase 1 uses `InProcessJobRunner` synchronously, replaced by `CeleryJobRunner` in Phase 5 without changing call sites.
- `uv run` is the standard entrypoint for scripts and the dev server.
- Docker images use `uv` for dependency installation to keep image build times fast.
