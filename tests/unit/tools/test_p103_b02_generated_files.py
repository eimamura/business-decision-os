from __future__ import annotations

import csv
import io
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from packages.tools.base import ToolContext


def make_ctx() -> ToolContext:
    return ToolContext(
        session_id=uuid4(),
        agent_step_id=uuid4(),
        specialist_role="data_engineer",
        actor="test",
        correlation_id=uuid4(),
    )


# ---------------------------------------------------------------------------
# SimulationTool — T-615
# ---------------------------------------------------------------------------

def _make_sim_runner(output: dict) -> MagicMock:
    """Build a mock runner that returns a succeeded JobResult with the given output."""
    from packages.agent.runner import JobHandle, JobResult
    from datetime import datetime, timezone

    handle = JobHandle(
        job_id=uuid4(),
        status="queued",
        submitted_at=datetime.now(tz=timezone.utc),
    )
    job_result = JobResult(
        job_id=handle.job_id,
        status="succeeded",
        output=output,
        error=None,
        duration_ms=1,
    )
    runner = MagicMock()
    runner.submit = AsyncMock(return_value=handle)
    runner.result = AsyncMock(return_value=job_result)
    return runner


async def test_simulation_tool_returns_generated_files_key():
    from packages.tools.simulation_tool import SimulationTool

    runner = _make_sim_runner({
        "sku_id": "SKU-A",
        "ending_on_hand": 150.0,
        "stockout_days": 2,
        "mean_lead_time_days": 14,
    })
    tool = SimulationTool(runner=runner)
    result = await tool.handle(
        {"sku_id": "SKU-A", "order_qty": 500, "horizon_days": 90},
        make_ctx(),
    )
    assert "generated_files" in result.output


async def test_simulation_tool_generated_files_non_empty_csv():
    from packages.tools.simulation_tool import SimulationTool

    runner = _make_sim_runner({
        "sku_id": "SKU-A",
        "ending_on_hand": 150.0,
        "stockout_days": 2,
        "mean_lead_time_days": 14,
    })
    tool = SimulationTool(runner=runner)
    result = await tool.handle(
        {"sku_id": "SKU-A", "order_qty": 500, "horizon_days": 90},
        make_ctx(),
    )
    files = result.output["generated_files"]
    assert len(files) == 1
    entry = files[0]
    assert entry["file_name"] == "simulation_result.csv"
    assert entry["mime_type"] == "text/csv"
    assert isinstance(entry["file_content"], bytes)
    assert len(entry["file_content"]) > 0


async def test_simulation_tool_csv_contains_expected_columns():
    from packages.tools.simulation_tool import SimulationTool

    runner = _make_sim_runner({
        "sku_id": "SKU-B",
        "ending_on_hand": 200.0,
        "stockout_days": 0,
        "mean_lead_time_days": 7,
    })
    tool = SimulationTool(runner=runner)
    result = await tool.handle(
        {"sku_id": "SKU-B", "order_qty": 100, "horizon_days": 30},
        make_ctx(),
    )
    csv_bytes = result.output["generated_files"][0]["file_content"]
    reader = csv.DictReader(io.StringIO(csv_bytes.decode("utf-8")))
    rows = list(reader)
    assert len(rows) == 1
    assert rows[0]["sku_id"] == "SKU-B"
    assert rows[0]["ending_on_hand"] == "200.0"
    assert rows[0]["stockout_days"] == "0"
    assert rows[0]["mean_lead_time_days"] == "7"


async def test_simulation_tool_existing_output_keys_unchanged():
    from packages.tools.simulation_tool import SimulationTool

    runner = _make_sim_runner({
        "sku_id": "SKU-C",
        "ending_on_hand": 50.0,
        "stockout_days": 5,
        "mean_lead_time_days": 21,
    })
    tool = SimulationTool(runner=runner)
    result = await tool.handle(
        {"sku_id": "SKU-C", "order_qty": 200, "horizon_days": 60},
        make_ctx(),
    )
    assert result.output["sku_id"] == "SKU-C"
    assert result.output["ending_on_hand"] == 50.0
    assert result.output["stockout_days"] == 5
    assert result.output["mean_lead_time_days"] == 21


async def test_simulation_tool_file_size_bytes_matches_content():
    from packages.tools.simulation_tool import SimulationTool

    runner = _make_sim_runner({
        "sku_id": "SKU-D",
        "ending_on_hand": 0.0,
        "stockout_days": 10,
        "mean_lead_time_days": 14,
    })
    tool = SimulationTool(runner=runner)
    result = await tool.handle(
        {"sku_id": "SKU-D", "order_qty": 50, "horizon_days": 45},
        make_ctx(),
    )
    entry = result.output["generated_files"][0]
    assert entry["file_size_bytes"] == len(entry["file_content"])


# ---------------------------------------------------------------------------
# OptimizerTool — T-616
# ---------------------------------------------------------------------------

def _make_opt_ctx_with_runner(candidates: list) -> tuple:
    """Return (tool_input, ctx) for OptimizerTool with a mock runner on ctx."""
    from datetime import datetime, timezone
    from packages.agent.runner import JobHandle, JobResult

    job_id = uuid4()
    handle = JobHandle(
        job_id=job_id,
        status="queued",
        submitted_at=datetime.now(tz=timezone.utc),
    )
    job_result = JobResult(
        job_id=job_id,
        status="succeeded",
        output={"candidates": candidates},
        error=None,
        duration_ms=1,
    )
    mock_runner = MagicMock()
    mock_runner.submit = AsyncMock(return_value=handle)
    mock_runner.result = AsyncMock(return_value=job_result)

    ctx = ToolContext(
        session_id=uuid4(),
        agent_step_id=uuid4(),
        specialist_role="data_engineer",
        actor="test",
        correlation_id=uuid4(),
    )
    # Attach runner to ctx so OptimizerTool picks it up
    object.__setattr__(ctx, "runner", mock_runner)
    return ctx


async def test_optimizer_tool_returns_generated_files_key():
    from packages.tools.optimizer_tool import OptimizerTool

    candidates = [
        {"order_qty": 100.0, "total_cost": 5000.0, "stockout_days": 3},
        {"order_qty": 200.0, "total_cost": 4500.0, "stockout_days": 1},
    ]
    ctx = _make_opt_ctx_with_runner(candidates)
    tool = OptimizerTool()
    result = await tool.handle(
        {"sku_id": "SKU-A", "moq": 100.0, "horizon_days": 90},
        ctx,
    )
    assert "generated_files" in result.output


async def test_optimizer_tool_candidates_key_unchanged():
    from packages.tools.optimizer_tool import OptimizerTool

    candidates = [
        {"order_qty": 100.0, "total_cost": 5000.0, "stockout_days": 3},
    ]
    ctx = _make_opt_ctx_with_runner(candidates)
    tool = OptimizerTool()
    result = await tool.handle(
        {"sku_id": "SKU-A", "moq": 100.0, "horizon_days": 90},
        ctx,
    )
    assert result.output["candidates"] == candidates


async def test_optimizer_tool_csv_file_name_and_mime():
    from packages.tools.optimizer_tool import OptimizerTool

    candidates = [
        {"order_qty": 100.0, "total_cost": 5000.0, "stockout_days": 3},
        {"order_qty": 200.0, "total_cost": 4800.0, "stockout_days": 1},
    ]
    ctx = _make_opt_ctx_with_runner(candidates)
    tool = OptimizerTool()
    result = await tool.handle(
        {"sku_id": "SKU-B", "moq": 100.0, "horizon_days": 60},
        ctx,
    )
    entry = result.output["generated_files"][0]
    assert entry["file_name"] == "optimization_plan.csv"
    assert entry["mime_type"] == "text/csv"


async def test_optimizer_tool_csv_row_count_matches_candidates():
    from packages.tools.optimizer_tool import OptimizerTool

    candidates = [
        {"order_qty": 100.0, "total_cost": 5000.0, "stockout_days": 3},
        {"order_qty": 200.0, "total_cost": 4800.0, "stockout_days": 1},
        {"order_qty": 300.0, "total_cost": 4600.0, "stockout_days": 0},
    ]
    ctx = _make_opt_ctx_with_runner(candidates)
    tool = OptimizerTool()
    result = await tool.handle(
        {"sku_id": "SKU-C", "moq": 100.0, "horizon_days": 90},
        ctx,
    )
    csv_bytes = result.output["generated_files"][0]["file_content"]
    reader = csv.DictReader(io.StringIO(csv_bytes.decode("utf-8")))
    rows = list(reader)
    assert len(rows) == 3


async def test_optimizer_tool_file_size_bytes_matches_content():
    from packages.tools.optimizer_tool import OptimizerTool

    candidates = [{"order_qty": 100.0, "total_cost": 4999.0, "stockout_days": 2}]
    ctx = _make_opt_ctx_with_runner(candidates)
    tool = OptimizerTool()
    result = await tool.handle(
        {"sku_id": "SKU-D", "moq": 100.0, "horizon_days": 90},
        ctx,
    )
    entry = result.output["generated_files"][0]
    assert entry["file_size_bytes"] == len(entry["file_content"])


async def test_optimizer_tool_empty_candidates_produces_empty_csv():
    from packages.tools.optimizer_tool import OptimizerTool

    ctx = _make_opt_ctx_with_runner([])
    tool = OptimizerTool()
    result = await tool.handle(
        {"sku_id": "SKU-E", "moq": 100.0, "horizon_days": 90},
        ctx,
    )
    entry = result.output["generated_files"][0]
    assert entry["file_content"] == b""
    assert entry["file_size_bytes"] == 0


# ---------------------------------------------------------------------------
# ForecastTool — T-617
# ---------------------------------------------------------------------------

def _make_predictor(sku_id: str, predicted_units: list[float]) -> MagicMock:
    """Build a mock predictor for ForecastTool."""
    prediction = MagicMock()
    prediction.predicted_units = predicted_units
    prediction.model_version = "test_v1"
    prediction.source = "stub"

    predictor = MagicMock()
    predictor.predict = AsyncMock(return_value=prediction)
    return predictor


async def test_forecast_tool_returns_generated_files_key():
    from packages.tools.forecast_tool import ForecastTool

    predictor = _make_predictor("SKU-A", [10.0, 12.0, 11.0])
    tool = ForecastTool(predictor=predictor)
    result = await tool.handle({"sku_id": "SKU-A", "horizon_days": 3}, make_ctx())
    assert "generated_files" in result.output


async def test_forecast_tool_csv_file_name_and_mime():
    from packages.tools.forecast_tool import ForecastTool

    predictor = _make_predictor("SKU-B", [20.0, 21.0])
    tool = ForecastTool(predictor=predictor)
    result = await tool.handle({"sku_id": "SKU-B", "horizon_days": 2}, make_ctx())
    entry = result.output["generated_files"][0]
    assert entry["file_name"] == "forecast_result.csv"
    assert entry["mime_type"] == "text/csv"


async def test_forecast_tool_csv_row_count_matches_horizon():
    from packages.tools.forecast_tool import ForecastTool

    predicted = [float(i) for i in range(7)]
    predictor = _make_predictor("SKU-C", predicted)
    tool = ForecastTool(predictor=predictor)
    result = await tool.handle({"sku_id": "SKU-C", "horizon_days": 7}, make_ctx())
    csv_bytes = result.output["generated_files"][0]["file_content"]
    reader = csv.DictReader(io.StringIO(csv_bytes.decode("utf-8")))
    rows = list(reader)
    assert len(rows) == 7


async def test_forecast_tool_csv_day_column_is_1_indexed():
    from packages.tools.forecast_tool import ForecastTool

    predictor = _make_predictor("SKU-D", [5.0, 6.0, 7.0])
    tool = ForecastTool(predictor=predictor)
    result = await tool.handle({"sku_id": "SKU-D", "horizon_days": 3}, make_ctx())
    csv_bytes = result.output["generated_files"][0]["file_content"]
    reader = csv.DictReader(io.StringIO(csv_bytes.decode("utf-8")))
    rows = list(reader)
    assert rows[0]["day"] == "1"
    assert rows[1]["day"] == "2"
    assert rows[2]["day"] == "3"


async def test_forecast_tool_existing_output_keys_unchanged():
    from packages.tools.forecast_tool import ForecastTool

    predictor = _make_predictor("SKU-E", [15.0, 16.0])
    tool = ForecastTool(predictor=predictor)
    result = await tool.handle({"sku_id": "SKU-E", "horizon_days": 2}, make_ctx())
    assert result.output["sku_id"] == "SKU-E"
    assert result.output["forecast_units"] == [15.0, 16.0]
    assert result.output["model_version"] == "test_v1"
    assert result.output["nulls_skipped"] == 0
    assert result.output["prediction"] == 15.0
    assert result.output["source"] == "stub"


async def test_forecast_tool_file_size_bytes_matches_content():
    from packages.tools.forecast_tool import ForecastTool

    predictor = _make_predictor("SKU-F", [8.0, 9.0, 10.0, 11.0])
    tool = ForecastTool(predictor=predictor)
    result = await tool.handle({"sku_id": "SKU-F", "horizon_days": 4}, make_ctx())
    entry = result.output["generated_files"][0]
    assert entry["file_size_bytes"] == len(entry["file_content"])


async def test_forecast_tool_empty_predictions_produces_empty_csv():
    from packages.tools.forecast_tool import ForecastTool

    predictor = _make_predictor("SKU-G", [])
    tool = ForecastTool(predictor=predictor)
    result = await tool.handle({"sku_id": "SKU-G", "horizon_days": 0}, make_ctx())
    entry = result.output["generated_files"][0]
    assert entry["file_content"] == b""
    assert entry["file_size_bytes"] == 0
