from __future__ import annotations

import os

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
    kpi,
    notifications,
    policies,
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

@app.get("/api/v1/debug")
async def debug_info() -> dict[str, object]:
    import os as _os
    api_key = _os.environ.get("ANTHROPIC_API_KEY", "")
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
        "api_key_set": bool(api_key),
        "api_key_prefix": api_key[:12] + "..." if api_key else None,
    }


app.include_router(health.router)
app.include_router(admin.router)
app.include_router(sessions.router)
app.include_router(decisions.router)
app.include_router(recommendations.router)
app.include_router(approvals.router)
app.include_router(scenarios.router)
app.include_router(audit.router)
app.include_router(kpi.router)
app.include_router(settings.router)
app.include_router(notifications.router)
app.include_router(policies.router)
