"""Unit tests for local-only operational route registration (T-754, D-022).

Covers the ADR docs/adr/2026-08-24-local-only-operational-routes.md contract:
`/api/v1/debug` and `/api/v1/admin/*` are registered only when APP_ENV
explicitly names development or test execution; unset/production/unknown values
are safe by default. The debug response never contains API-key material.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from contextlib import contextmanager
from types import ModuleType
from typing import Any
from unittest.mock import patch

import pytest

from apps.api.main import _operational_routes_enabled

DEBUG_PATH = "/api/v1/debug"
ADMIN_PREFIX = "/api/v1/admin"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _operational_route_paths(module: ModuleType) -> list[str]:
    """Route paths registered on *module*'s app matching operational surfaces."""
    return sorted(
        str(route.path)
        for route in module.app.routes
        if route.path == DEBUG_PATH or str(route.path).startswith(ADMIN_PREFIX)
    )


@contextmanager
def _fresh_main(monkeypatch: pytest.MonkeyPatch, app_env: str | None) -> Iterator[ModuleType]:
    """Import apps.api.main fresh with *app_env* set before registration.

    Follows the module-reload precedent of tests/unit/test_health_log_filter.py:
    heavy side-effectful imports (dotenv, logging/otel configuration) are patched
    out. The pre-test module objects are restored afterwards so later tests keep
    their original bindings.
    """
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
# Gating predicate (pure)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("app_env", "expected"),
    [
        ("dev", True),
        ("test", True),
        ("prod", False),
        ("production", False),
        ("staging", False),
        ("DEV", False),
        ("", False),
        (None, False),
    ],
)
def test_operational_routes_enabled_matrix(app_env: str | None, expected: bool) -> None:
    assert _operational_routes_enabled(app_env) is expected


# ---------------------------------------------------------------------------
# Route registration matrix (module reload per environment)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("app_env", "registered"),
    [
        ("dev", True),
        ("test", True),
        ("production", False),
        ("prod", False),
        (None, False),
    ],
)
def test_route_registration_follows_app_env(
    monkeypatch: pytest.MonkeyPatch, app_env: str | None, registered: bool
) -> None:
    with _fresh_main(monkeypatch, app_env) as main_module:
        paths = _operational_route_paths(main_module)
    if registered:
        assert DEBUG_PATH in paths
        assert any(p.startswith(ADMIN_PREFIX) for p in paths)
    else:
        # D-022 acceptance: production/default-safe inspection returns an empty list.
        assert paths == []


def test_d022_repro_production_mode_returns_empty_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exact D-022 repro semantics under APP_ENV=production."""
    with _fresh_main(monkeypatch, "production") as main_module:
        paths: list[Any] = [
            r.path
            for r in main_module.app.routes
            if r.path == DEBUG_PATH or r.path.startswith(ADMIN_PREFIX)
        ]
    assert sorted(paths) == []


# ---------------------------------------------------------------------------
# Debug response must not disclose API-key material
# ---------------------------------------------------------------------------


async def test_debug_response_never_contains_api_key_material(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fabricated = "sk-ant-supersecret0123456789"
    monkeypatch.setenv("ANTHROPIC_API_KEY", fabricated)

    with _fresh_main(monkeypatch, "dev") as main_module:
        payload = await main_module.debug_info()

    serialized = repr(payload)
    assert set(payload) == {"anthropic_installed", "anthropic_version", "api_key_set"}
    assert payload["api_key_set"] is True
    assert "api_key_prefix" not in payload
    assert fabricated not in serialized
    assert fabricated[:12] not in serialized


async def test_debug_response_without_api_key_reports_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    with _fresh_main(monkeypatch, "dev") as main_module:
        payload = await main_module.debug_info()

    assert payload["api_key_set"] is False
    assert "api_key_prefix" not in payload
