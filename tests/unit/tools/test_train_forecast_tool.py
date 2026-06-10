"""T-482: Unit tests for TrainForecastTool.handle().

Stubs the JobRunner so no DB or numpy calls occur. Tests cover:
- success path: output keys sku_id, model_version, horizon_days present
- failure path: RuntimeError raised when job status is not "succeeded"
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from packages.agent.runner import JobHandle, JobResult
from packages.tools.base import ToolContext
from packages.tools.train_forecast_tool import TrainForecastTool

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_ctx() -> ToolContext:
    return ToolContext(
        session_id=uuid4(),
        agent_step_id=uuid4(),
        specialist_role="control",
        actor="test",
        correlation_id=uuid4(),
    )


def make_runner(job_result: JobResult) -> MagicMock:
    """Return a fake JobRunner that always succeeds submit and returns job_result."""
    from datetime import datetime, timezone

    runner = AsyncMock()
    handle = JobHandle(
        job_id=uuid4(),
        status="succeeded",
        submitted_at=datetime.now(tz=timezone.utc),
    )
    runner.submit.return_value = handle
    runner.result.return_value = job_result
    return runner


# ---------------------------------------------------------------------------
# Success path
# ---------------------------------------------------------------------------


async def test_train_forecast_success_returns_expected_keys():
    """Successful job → ToolResult output has sku_id, model_version, horizon_days."""
    job_result = JobResult(
        job_id=uuid4(),
        status="succeeded",
        output={
            "sku_id": "SKU-X",
            "model_version": "linear_regression_v1_trained",
            "horizon_days": 90,
        },
        error=None,
        duration_ms=42,
    )
    runner = make_runner(job_result)

    tool = TrainForecastTool(runner=runner)
    result = await tool.handle({"sku_id": "SKU-X"}, make_ctx())

    assert result.output["sku_id"] == "SKU-X"
    assert result.output["model_version"] == "linear_regression_v1_trained"
    assert result.output["horizon_days"] == 90


async def test_train_forecast_success_uses_sku_from_input_when_output_missing():
    """When output dict omits sku_id the tool falls back to the input sku_id."""
    job_result = JobResult(
        job_id=uuid4(),
        status="succeeded",
        output={
            "model_version": "linear_regression_v1_trained",
            "horizon_days": 90,
        },
        error=None,
        duration_ms=10,
    )
    runner = make_runner(job_result)

    tool = TrainForecastTool(runner=runner)
    result = await tool.handle({"sku_id": "SKU-FALLBACK"}, make_ctx())

    assert result.output["sku_id"] == "SKU-FALLBACK"


async def test_train_forecast_success_default_horizon_when_output_missing():
    """When output dict omits horizon_days the tool defaults to 90."""
    job_result = JobResult(
        job_id=uuid4(),
        status="succeeded",
        output={"sku_id": "SKU-Y", "model_version": "v1"},
        error=None,
        duration_ms=10,
    )
    runner = make_runner(job_result)

    tool = TrainForecastTool(runner=runner)
    result = await tool.handle({"sku_id": "SKU-Y"}, make_ctx())

    assert result.output["horizon_days"] == 90


# ---------------------------------------------------------------------------
# Failure path
# ---------------------------------------------------------------------------


async def test_train_forecast_job_failed_raises_runtime_error():
    """Job status 'failed' → TrainForecastTool.handle raises RuntimeError."""
    job_result = JobResult(
        job_id=uuid4(),
        status="failed",
        output=None,
        error="prediction repo unavailable",
        duration_ms=5,
    )
    runner = make_runner(job_result)
    runner.result.return_value = job_result

    tool = TrainForecastTool(runner=runner)
    with pytest.raises(RuntimeError, match="train_forecast job failed"):
        await tool.handle({"sku_id": "SKU-ERR"}, make_ctx())


async def test_train_forecast_output_none_raises_runtime_error():
    """Job status 'succeeded' but output=None → RuntimeError (unexpected state)."""
    job_result = JobResult(
        job_id=uuid4(),
        status="succeeded",
        output=None,
        error=None,
        duration_ms=5,
    )
    runner = make_runner(job_result)
    runner.result.return_value = job_result

    tool = TrainForecastTool(runner=runner)
    with pytest.raises(RuntimeError, match="train_forecast job failed"):
        await tool.handle({"sku_id": "SKU-NULL"}, make_ctx())
