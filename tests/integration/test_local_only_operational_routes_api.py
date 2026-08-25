"""T-755 — Integration-tier environment-matrix API tests for local-only routes.

Proves over the real HTTP layer (httpx ASGI transport) what ADR
docs/adr/2026-08-local-only-operational-routes.md requires:

- ``/api/v1/debug`` and ``/api/v1/admin/*`` are ABSENT in production mode and
  in default-safe mode (APP_ENV unset or unknown) — D-022 acceptance: route
  inspection returns an empty list.
- Both surfaces are PRESENT when APP_ENV explicitly names dev or test.
- The debug diagnostics response never returns secret material (no API-key
  substring, prefix, or derived hash material).

Each test imports ``apps.api.main`` fresh with the target APP_ENV applied
*before* registration, following the module-reload precedent of
tests/unit/test_local_only_operational_routes.py. dotenv loading and
observability setup are patched out so the repo's committed ``.env`` cannot
leak ambient APP_ENV values into the matrix.

These endpoints do not touch the database and ASGITransport does not run the
lifespan, so no DATABASE_URL is required.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from contextlib import contextmanager
from types import ModuleType
from unittest.mock import patch

import httpx
import pytest
from httpx import ASGITransport

DEBUG_PATH = "/api/v1/debug"
ADMIN_PROBE_PATH = "/api/v1/admin/registry"
ADMIN_PREFIX = "/api/v1/admin"
_FABRICATED_KEY = "sk-ant-integration-fabricated0123456789"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _operational_route_paths(module: ModuleType) -> list[str]:
    """Route paths on *module*'s app matching the operational surfaces."""
    return sorted(
        str(route.path)
        for route in module.app.routes
        if route.path == DEBUG_PATH or str(route.path).startswith(ADMIN_PREFIX)
    )


@contextmanager
def _fresh_main(
    monkeypatch: pytest.MonkeyPatch, app_env: str | None
) -> Iterator[ModuleType]:
    """Import apps.api.main fresh with *app_env* fixed before registration."""
    if app_env is None:
        monkeypatch.delenv("APP_ENV", raising=False)
    else:
        monkeypatch.setenv("APP_ENV", app_env)

    saved = {k: v for k, v in sys.modules.items() if k.startswith("apps.api.main")}
    for k in saved:
        del sys.modules[k]
    try:
        with (
            patch("dotenv.load_dotenv"),
            patch("apps.api.observability.configure_logging"),
            patch("apps.api.observability.configure_otel"),
        ):
            import apps.api.main as main_module

            yield main_module
    finally:
        for k in [k for k in sys.modules if k.startswith("apps.api.main")]:
            del sys.modules[k]
        sys.modules.update(saved)


# ---------------------------------------------------------------------------
# Absent: production and default-safe modes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("app_env", "label"),
    [
        ("production", "explicit production"),
        ("prod", "unknown 'prod' alias"),
        ("staging", "unknown staging value"),
        ("", "empty value (committed .env default)"),
        (None, "unset / default-safe"),
    ],
)
async def test_operational_routes_absent_in_safe_modes(
    monkeypatch: pytest.MonkeyPatch, app_env: str | None, label: str
) -> None:
    """Safe modes expose neither surface: HTTP 404 and empty route inspection."""
    with _fresh_main(monkeypatch, app_env) as main_module:
        paths = _operational_route_paths(main_module)
        async with httpx.AsyncClient(
            transport=ASGITransport(app=main_module.app), base_url="http://test"
        ) as client:
            debug_resp = await client.get(DEBUG_PATH)
            registry_resp = await client.get(ADMIN_PROBE_PATH)

    assert paths == [], f"{label}: operational routes must not be registered"
    assert debug_resp.status_code == 404, f"{label}: /api/v1/debug must be absent"
    assert registry_resp.status_code == 404, f"{label}: admin routes must be absent"


async def test_d022_repro_production_route_inspection_returns_empty_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exact D-022 repro semantics through a freshly imported production app."""
    with _fresh_main(monkeypatch, "production") as main_module:
        paths = [
            route.path
            for route in main_module.app.routes
            if route.path == DEBUG_PATH or str(route.path).startswith(ADMIN_PREFIX)
        ]
    assert sorted(paths) == []


# ---------------------------------------------------------------------------
# Present: explicit dev / test modes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("app_env", ["dev", "test"])
async def test_operational_routes_present_in_explicit_dev_test_modes(
    monkeypatch: pytest.MonkeyPatch, app_env: str
) -> None:
    """Explicit dev/test registers both surfaces and serves debug over HTTP."""
    with _fresh_main(monkeypatch, app_env) as main_module:
        paths = _operational_route_paths(main_module)
        async with httpx.AsyncClient(
            transport=ASGITransport(app=main_module.app), base_url="http://test"
        ) as client:
            debug_resp = await client.get(DEBUG_PATH)
            openapi = (await client.get("/openapi.json")).json()

    assert DEBUG_PATH in paths, f"APP_ENV={app_env}: debug route must be registered"
    assert any(p.startswith(ADMIN_PREFIX) for p in paths), (
        f"APP_ENV={app_env}: admin router must be registered"
    )
    assert debug_resp.status_code == 200
    assert DEBUG_PATH in openapi["paths"], (
        f"APP_ENV={app_env}: debug route missing from OpenAPI schema"
    )
    assert ADMIN_PROBE_PATH in openapi["paths"], (
        f"APP_ENV={app_env}: admin registry route missing from OpenAPI schema"
    )


# ---------------------------------------------------------------------------
# Diagnostics never return secret material
# ---------------------------------------------------------------------------


async def test_debug_response_never_contains_api_key_material_over_http(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Debug endpoint response carries no API-key substring/prefix/hash material."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", _FABRICATED_KEY)

    with _fresh_main(monkeypatch, "dev") as main_module:
        async with httpx.AsyncClient(
            transport=ASGITransport(app=main_module.app), base_url="http://test"
        ) as client:
            resp = await client.get(DEBUG_PATH)

    assert resp.status_code == 200
    payload = resp.json()
    body = resp.text
    assert set(payload) == {"anthropic_installed", "anthropic_version", "api_key_set"}
    assert payload["api_key_set"] is True
    assert "api_key_prefix" not in payload
    for fragment in (_FABRICATED_KEY, _FABRICATED_KEY[:12], "sk-ant-"):
        assert fragment not in body, f"debug response leaked secret fragment: {fragment!r}"
