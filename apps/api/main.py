from __future__ import annotations

import os

from fastapi import FastAPI

from apps.api.observability import configure_logging, configure_otel

configure_logging()
configure_otel()
from fastapi.middleware.cors import CORSMiddleware

from apps.api.middleware import DevUserMiddleware
from apps.api.routers import (
    approvals,
    audit,
    health,
    kpi,
    recommendations,
    scenarios,
    sessions,
    settings,
)

app = FastAPI(title="Business Decision OS API", version="0.1.0")

_dev_origins = ["http://localhost:3000"]
_prod_origins_raw = os.environ.get("CORS_ALLOWED_ORIGINS", "")
_prod_origins = [o.strip() for o in _prod_origins_raw.split(",") if o.strip()]
_allowed_origins = _prod_origins if _prod_origins else _dev_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)
app.add_middleware(DevUserMiddleware)

app.include_router(health.router)
app.include_router(sessions.router)
app.include_router(recommendations.router)
app.include_router(approvals.router)
app.include_router(scenarios.router)
app.include_router(audit.router)
app.include_router(kpi.router)
app.include_router(settings.router)
