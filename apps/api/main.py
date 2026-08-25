from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI

load_dotenv()

from apps.api.observability import configure_logging, configure_otel  # noqa: E402

configure_logging()
configure_otel()
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from apps.api.middleware import DevUserMiddleware  # noqa: E402
from apps.api.routers import (  # noqa: E402
    admin,
    approvals,
    audit,
    decisions,
    health,
    jobs,
    kpi,
    notifications,
    policies,
    recommendations,
    scenarios,
    screenings,
    sessions,
    settings,
)


class _HealthCheckFilter(logging.Filter):
    """Drop uvicorn access-log records for health-check endpoints.

    Only active in development (``ENV=development``).  Prevents repeated
    ``GET /health`` lines from drowning out real application logs during
    local development while leaving production logs untouched.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        if "GET /health" in msg or "GET /api/v1/health" in msg:
            return False
        return True


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    from packages.tools.schema_context import load_schema_context

    if os.environ.get("ENV") == "development":
        logging.getLogger("uvicorn.access").addFilter(_HealthCheckFilter())

    await load_schema_context()

    # MLflow tracing is optional: only activated when MLFLOW_TRACKING_URI is set.
    # Missing URI is the approved silent-skip case for this codebase (optional observability).
    mlflow_uri = os.environ.get("MLFLOW_TRACKING_URI")
    if mlflow_uri:
        from apps.api.tracing import setup_mlflow_tracing

        experiment_name = os.environ.get("MLFLOW_EXPERIMENT_NAME", "business-decision-os")
        setup_mlflow_tracing(mlflow_uri, experiment_name)

    # Create LangGraph checkpoint tables (checkpoints, checkpoint_writes, checkpoint_blobs)
    # idempotently on every startup. Skipped when DATABASE_URL is absent (e.g. unit tests).
    database_url = os.environ.get("DATABASE_URL", "")
    if database_url:
        # psycopg v3 uses plain postgresql:// — strip the SQLAlchemy +asyncpg driver prefix.
        psycopg_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
        async with AsyncPostgresSaver.from_conn_string(psycopg_url) as saver:
            await saver.setup()

    from apps.api import state
    from apps.api.screening import start_screening_scheduler

    await state.init_shared_pool()

    screening_task = start_screening_scheduler()

    yield

    if screening_task is not None:
        screening_task.cancel()
        try:
            await screening_task
        except asyncio.CancelledError:
            pass

    await state.close_shared_pool()


app = FastAPI(title="Business Decision OS API", version="0.1.0", lifespan=lifespan)

# Operational routes (debug + admin) are registered only when APP_ENV explicitly
# names development or test execution. Unset, production ("prod"/"production"),
# or unknown values are safe by default and expose neither surface.
# ADR: docs/adr/2026-08-24-local-only-operational-routes.md
_OPERATIONAL_ENVS = frozenset({"dev", "test"})


def _operational_routes_enabled(app_env: str | None) -> bool:
    """Return True only when *app_env* explicitly identifies dev or test execution."""
    return app_env in _OPERATIONAL_ENVS


_operational_routes_enabled_flag = _operational_routes_enabled(os.environ.get("APP_ENV"))

_dev_origins = ["http://localhost:3000"]
_prod_origins_raw = os.environ.get("CORS_ALLOWED_ORIGINS", "")
_prod_origins = [o.strip() for o in _prod_origins_raw.split(",") if o.strip()]
_allowed_origins = _prod_origins if _prod_origins else _dev_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    max_age=3600,
)
app.add_middleware(DevUserMiddleware)

if _operational_routes_enabled_flag:

    @app.get("/api/v1/debug")
    async def debug_info() -> dict[str, object]:
        import os as _os

        try:
            import anthropic as _anthropic

            anthropic_version: str | None = _anthropic.__version__
            anthropic_installed = True
        except ImportError:
            anthropic_version = None
            anthropic_installed = False
        return {
            "anthropic_installed": anthropic_installed,
            "anthropic_version": anthropic_version,
            "api_key_set": bool(_os.environ.get("ANTHROPIC_API_KEY")),
        }


app.include_router(health.router)
if _operational_routes_enabled_flag:
    app.include_router(admin.router)
app.include_router(sessions.router)
app.include_router(jobs.router)
app.include_router(decisions.router)
app.include_router(recommendations.router)
app.include_router(approvals.router)
app.include_router(scenarios.router)
app.include_router(audit.router)
app.include_router(kpi.router)
app.include_router(settings.router)
app.include_router(notifications.router)
app.include_router(policies.router)
app.include_router(screenings.router)
