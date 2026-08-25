"""E2E test conftest — configured-port probe, loud failures, driver guard.

D-024: the API reachability probe reads API_PORT (Makefile default 8002) and a
dedicated e2e session fails loudly instead of silently skipping when the API
is unreachable.

D-026: an autouse session fixture proves the served API runs the deterministic
LLM_DRIVER=scripted model before any test executes. Job-flow outcomes are only
deterministic under that driver, so a live-model API must fail with setup
instructions rather than produce run-to-run flakiness.
"""

from __future__ import annotations

import socket
import time
from typing import Generator

import pytest

from tests.conftest import API_BASE_URL, api_base_url, configured_api_port

# llm_usage.model value written for every ScriptedDriverModel call (see
# packages/agent/scripted_model.py response_metadata).
_SCRIPTED_MODEL_NAME = "scripted-driver"
_DRIVER_PROBE_TIMEOUT_S = 30.0


def _api_is_up() -> bool:
    try:
        with socket.create_connection(("localhost", configured_api_port()), timeout=1):
            return True
    except OSError:
        return False


def pytest_collection_modifyitems(items: list) -> None:
    """Refuse to silently skip a dedicated e2e session (D-024).

    When the collected session consists exclusively of tests/e2e items and no
    API is reachable at the configured port, abort collection with setup
    guidance. Mixed-repo sessions (`make test`) keep the root-conftest
    convenience skip so unit-only workflows stay hermetic.
    """
    if _api_is_up():
        return
    e2e_items = [item for item in items if item.nodeid.startswith("tests/e2e")]
    if e2e_items and len(e2e_items) == len(items):
        raise pytest.UsageError(
            f"e2e tier requires a live API but none is reachable at "
            f"{api_base_url()} — refusing to silently skip.\n"
            "Setup:\n"
            "  1. Start the stack: make dev-up (or serve the API alone with\n"
            "     LLM_DRIVER=scripted uv run uvicorn apps.api.main:app "
            "--port $API_PORT).\n"
            "  2. For deterministic job-flow runs the API MUST be started with\n"
            "     LLM_DRIVER=scripted (the guard below enforces this).\n"
            "  3. If the API listens on a non-default port, export API_PORT=<port>\n"
            f"     (Makefile default: {8002})."
        )


@pytest.fixture(scope="session", autouse=True)
def served_api_runs_scripted_driver() -> Generator[None, None]:
    """Fail loudly unless the served API provably runs LLM_DRIVER=scripted.

    Creates one probe session and posts a neutral message (any message forces
    at least one LLM call), then polls GET /api/v1/admin/llm-usage until this
    session's first usage row appears and requires its model to be
    'scripted-driver'. The row is matched by session_id, so stale usage rows
    from earlier live-model runs cannot false-pass the check.
    """
    import httpx

    headers = {"X-Dev-User": "dev-user", "Content-Type": "application/json"}
    res = httpx.post(
        f"{API_BASE_URL}/api/v1/sessions",
        json={"goal": "e2e driver probe"},
        headers=headers,
        timeout=10,
    )
    assert res.status_code == 200, (
        f"Driver guard could not create a probe session on {API_BASE_URL}: "
        f"{res.status_code} {res.text}"
    )
    sid = str(res.json()["session_id"])
    try:
        msg = httpx.post(
            f"{API_BASE_URL}/api/v1/sessions/{sid}/messages",
            json={
                "content": (
                    "Driver probe: summarize today's inventory posture in one sentence."
                )
            },
            headers=headers,
            timeout=30,
        )
        assert msg.status_code == 200, (
            f"Driver guard probe message failed: {msg.status_code} {msg.text}"
        )

        deadline = time.monotonic() + _DRIVER_PROBE_TIMEOUT_S
        last_usage_status: int | None = None
        while time.monotonic() < deadline:
            usage_res = httpx.get(
                f"{API_BASE_URL}/api/v1/admin/llm-usage",
                params={"limit": 50},
                headers=headers,
                timeout=10,
            )
            last_usage_status = usage_res.status_code
            if usage_res.status_code == 200:
                rows = usage_res.json()
                match = next(
                    (r for r in rows if str(r.get("session_id")) == sid), None
                )
                if match is not None:
                    model = str(match.get("model", ""))
                    if model == _SCRIPTED_MODEL_NAME:
                        yield
                        return
                    pytest.fail(
                        f"Served API is NOT running LLM_DRIVER=scripted: probe "
                        f"session {sid} recorded model={model!r}. Job-flow e2e "
                        f"assertions are only deterministic under the scripted "
                        f"driver. Restart the API with LLM_DRIVER=scripted "
                        f"(e.g. add it to the api service env in your compose "
                        f"override, or 'LLM_DRIVER=scripted uvicorn "
                        f"apps.api.main:app') and re-run."
                    )
            time.sleep(1.0)

        pytest.fail(
            f"Could not verify the served API's LLM driver within "
            f"{_DRIVER_PROBE_TIMEOUT_S:.0f}s. "
            + (
                f"GET /api/v1/admin/llm-usage returned HTTP {last_usage_status}; "
                "admin routes require APP_ENV=dev or APP_ENV=test on the API."
                if last_usage_status != 200
                else "No llm_usage row appeared for the probe session — the "
                "message run may not have reached the model. Check API logs."
            )
            + " The e2e tier refuses to run against an unverifiable driver."
        )
    finally:
        try:
            httpx.delete(
                f"{API_BASE_URL}/api/v1/sessions/{sid}", headers=headers, timeout=10
            )
        except Exception:
            pass


@pytest.fixture(autouse=True)
def cleanup_test_sessions() -> Generator[list[str], None, None]:
    """Collect session IDs created during the test; delete them all on teardown."""
    created: list[str] = []
    yield created
    if not _api_is_up():
        return
    import httpx

    for sid in created:
        try:
            httpx.delete(f"{API_BASE_URL}/api/v1/sessions/{sid}", timeout=5)
        except Exception:
            pass
