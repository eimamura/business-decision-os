from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

import pytest

from packages.agent.runner.celery_runner import _STATUS_MAP, _require_celery


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
    from packages.agent.runner import CeleryJobRunner

    assert CeleryJobRunner is not None


def test_celery_runner_init_raises_without_broker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CELERY_BROKER_URL", raising=False)
    from packages.agent.runner import CeleryJobRunner

    with pytest.raises(RuntimeError, match="CELERY_BROKER_URL"):
        CeleryJobRunner()


def test_submit_train_forecast_sends_to_training_queue(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CELERY_BROKER_URL", "redis://localhost:6379/0")

    from packages.agent.runner import CeleryJobRunner, JobSpec
    from packages.tools.base import ToolContext

    sent: dict[str, Any] = {}

    class _FakeResult:
        def __init__(self, task_id: str) -> None:
            self.id = task_id

    def fake_send_task(name: str, args: Any, task_id: str, **kwargs: Any) -> _FakeResult:
        sent["name"] = name
        sent["queue"] = kwargs.get("queue")
        return _FakeResult(task_id)

    runner = CeleryJobRunner()
    monkeypatch.setattr(runner._app, "send_task", fake_send_task)

    ctx = ToolContext(
        session_id=uuid4(),
        agent_step_id=uuid4(),
        specialist_role="orchestrator",
        actor="test",
        correlation_id=uuid4(),
    )
    spec = JobSpec(kind="train_forecast", payload={"sku_id": "SKU001"}, idempotency_key="k")
    asyncio.run(runner.submit(spec, ctx))

    assert sent["name"] == "bdos.train_predictor"
    assert sent["queue"] == "training"


def test_submit_simulation_uses_default_queue(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CELERY_BROKER_URL", "redis://localhost:6379/0")

    from packages.agent.runner import CeleryJobRunner, JobSpec
    from packages.tools.base import ToolContext

    sent: dict[str, Any] = {}

    class _FakeResult:
        def __init__(self, task_id: str) -> None:
            self.id = task_id

    def fake_send_task(name: str, args: Any, task_id: str, **kwargs: Any) -> _FakeResult:
        sent["name"] = name
        sent["queue"] = kwargs.get("queue")
        return _FakeResult(task_id)

    runner = CeleryJobRunner()
    monkeypatch.setattr(runner._app, "send_task", fake_send_task)

    ctx = ToolContext(
        session_id=uuid4(),
        agent_step_id=uuid4(),
        specialist_role="orchestrator",
        actor="test",
        correlation_id=uuid4(),
    )
    spec = JobSpec(kind="simulation", payload={"sku_id": "SKU001", "order_qty": 100}, idempotency_key="k2")
    asyncio.run(runner.submit(spec, ctx))

    assert sent["name"] == "bdos.run_simulation"
    assert sent["queue"] is None
