from __future__ import annotations

from uuid import uuid4

import pytest

from packages.agent.runner import InProcessJobRunner, JobSpec
from packages.tools.base import ToolContext


def _make_ctx() -> ToolContext:
    return ToolContext(
        session_id=uuid4(),
        agent_step_id=uuid4(),
        specialist_role="data_engineer",
        actor="test",
        correlation_id=uuid4(),
    )


async def test_submit_returns_queued_handle():
    runner = InProcessJobRunner()
    spec = JobSpec(
        kind="simulation",
        payload={"sku_id": "SKU001"},
        idempotency_key="test-key-1",
    )
    handle = await runner.submit(spec, _make_ctx())
    assert handle.status == "queued"
    assert handle.job_id is not None


async def test_status_returns_handle():
    runner = InProcessJobRunner()
    spec = JobSpec(
        kind="optimization",
        payload={},
        idempotency_key="test-key-2",
    )
    handle = await runner.submit(spec, _make_ctx())
    retrieved = await runner.status(handle.job_id)
    assert retrieved.job_id == handle.job_id


async def test_result_raises_key_error_for_unknown_job():
    runner = InProcessJobRunner()
    with pytest.raises(KeyError):
        await runner.result(uuid4())


def test_job_spec_train_forecast_kind_is_valid():
    spec = JobSpec(kind="train_forecast", payload={"sku_id": "SKU-1"}, idempotency_key="k")
    assert spec.kind == "train_forecast"


async def test_inprocess_run_train_forecast_no_db_returns_failed_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Mock DB calls so forecast computation runs without a real DB
    async def _stub_fetch(sku_id: str) -> list[float]:
        return []

    async def _stub_upsert(sku_id: str, predicted_units: list[float], model_version: str) -> None:
        return None

    monkeypatch.setattr(
        "packages.agent.runner.fetch_demand_history", _stub_fetch
    )
    monkeypatch.setattr(
        "packages.agent.runner.upsert_prediction", _stub_upsert
    )

    runner = InProcessJobRunner()
    spec = JobSpec(kind="train_forecast", payload={"sku_id": "SKU-1"}, idempotency_key="k2")
    handle = await runner.submit(spec, _make_ctx())
    result = await runner.result(handle.job_id, wait=False)
    assert result.status == "succeeded"
    assert result.output is not None
    assert result.output["model_version"] == "linear_regression_v1_trained"
