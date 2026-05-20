from __future__ import annotations

import pytest

from packages.agent.job_runner.celery_runner import _STATUS_MAP, _require_celery


def test_require_celery_raises_without_broker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CELERY_BROKER_URL", raising=False)
    with pytest.raises(RuntimeError, match="CELERY_BROKER_URL"):
        _require_celery()


def test_require_celery_passes_with_broker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    _require_celery()


def test_status_map_pending_is_queued() -> None:
    assert _STATUS_MAP["PENDING"] == "queued"


def test_status_map_received_is_queued() -> None:
    assert _STATUS_MAP["RECEIVED"] == "queued"


def test_status_map_started_is_running() -> None:
    assert _STATUS_MAP["STARTED"] == "running"


def test_status_map_success_is_succeeded() -> None:
    assert _STATUS_MAP["SUCCESS"] == "succeeded"


def test_status_map_failure_is_failed() -> None:
    assert _STATUS_MAP["FAILURE"] == "failed"


def test_status_map_revoked_is_cancelled() -> None:
    assert _STATUS_MAP["REVOKED"] == "cancelled"


def test_status_map_retry_is_running() -> None:
    assert _STATUS_MAP["RETRY"] == "running"


def test_celery_runner_exported() -> None:
    from packages.agent.job_runner import CeleryJobRunner

    assert CeleryJobRunner is not None


def test_celery_runner_init_raises_without_broker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CELERY_BROKER_URL", raising=False)
    from packages.agent.job_runner import CeleryJobRunner

    with pytest.raises(RuntimeError, match="CELERY_BROKER_URL"):
        CeleryJobRunner()
