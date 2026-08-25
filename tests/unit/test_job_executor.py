from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from packages.agent.job_executor import _extract_files, _parse_params
from packages.tools.base import ToolResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_job_row(
    job_id: UUID | None = None,
    job_type: str = "simulate",
    params_json: dict[str, Any] | None = None,
    session_id: UUID | None = None,
) -> dict[str, Any]:
    return {
        "id": job_id or uuid4(),
        "job_type": job_type,
        "params_json": params_json if params_json is not None else {},
        "session_id": session_id,
        "status": "pending_approval",
    }


def _ok_tool_result() -> ToolResult:
    return ToolResult(output={"result": "ok"}, audit_payload={})


# ---------------------------------------------------------------------------
# _parse_params unit tests
# ---------------------------------------------------------------------------


def test_parse_params_handles_dict() -> None:
    assert _parse_params({"k": "v"}) == {"k": "v"}


def test_parse_params_handles_json_string() -> None:
    assert _parse_params('{"k": "v"}') == {"k": "v"}


def test_parse_params_handles_invalid_returns_empty() -> None:
    assert _parse_params(None) == {}


# ---------------------------------------------------------------------------
# execute_job routing and status tests
# ---------------------------------------------------------------------------


async def test_execute_job_routes_to_correct_tool_simulate() -> None:
    """execute_job must call SimulationTool.handle for job_type='simulate'."""
    from packages.agent.job_executor import execute_job

    job_id = uuid4()
    fake_job = _fake_job_row(job_id=job_id, job_type="simulate")
    mock_handle = AsyncMock(return_value=_ok_tool_result())
    mock_get_job = AsyncMock(return_value=fake_job)
    mock_update_status = AsyncMock(return_value={**fake_job, "status": "completed"})

    with (
        patch("packages.persistence.jobs_repo.JobsRepository.get_job", mock_get_job),
        patch("packages.persistence.jobs_repo.JobsRepository.update_status", mock_update_status),
        patch("packages.tools.simulation_tool.SimulationTool.handle", mock_handle),
    ):
        await execute_job(job_id)

    mock_handle.assert_called_once()


async def test_execute_job_calls_update_status_completed_on_success() -> None:
    """On a successful tool call execute_job must update the job to status='completed'.

    Updated in P101-T-601: execute_job now also sets status='running' before the
    tool call, so update_status is called at least twice; assert_called_once()
    is replaced with a check that the LAST call used status='completed'.
    """
    from packages.agent.job_executor import execute_job

    job_id = uuid4()
    fake_job = _fake_job_row(job_id=job_id, job_type="simulate")
    mock_handle = AsyncMock(return_value=_ok_tool_result())
    mock_get_job = AsyncMock(return_value=fake_job)
    mock_update_status = AsyncMock(return_value={**fake_job, "status": "completed"})

    with (
        patch("packages.persistence.jobs_repo.JobsRepository.get_job", mock_get_job),
        patch("packages.persistence.jobs_repo.JobsRepository.update_status", mock_update_status),
        patch("packages.tools.simulation_tool.SimulationTool.handle", mock_handle),
    ):
        await execute_job(job_id)

    assert mock_update_status.call_count >= 2, (
        "update_status must be called at least twice: once for 'running', once for 'completed'"
    )
    # The last call must be for the terminal status 'completed'
    last_call_kwargs = mock_update_status.call_args
    # call_args is a (args, kwargs) pair; status may be positional or keyword
    last_status = (
        last_call_kwargs.kwargs.get("status")
        or (last_call_kwargs.args[1] if len(last_call_kwargs.args) > 1 else None)
    )
    assert last_status == "completed", (
        f"Last update_status call must use status='completed', got {last_status!r}"
    )


async def test_execute_job_calls_update_status_failed_on_exception() -> None:
    """When the tool raises, execute_job must update the job to status='failed' with the error.

    Updated in P101-T-601: execute_job now also sets status='running' before the
    tool call, so update_status is called at least twice.
    """
    from packages.agent.job_executor import execute_job

    job_id = uuid4()
    fake_job = _fake_job_row(job_id=job_id, job_type="simulate")
    mock_handle = AsyncMock(side_effect=RuntimeError("boom"))
    mock_get_job = AsyncMock(return_value=fake_job)
    mock_update_status = AsyncMock(return_value={**fake_job, "status": "failed"})

    with (
        patch("packages.persistence.jobs_repo.JobsRepository.get_job", mock_get_job),
        patch("packages.persistence.jobs_repo.JobsRepository.update_status", mock_update_status),
        patch("packages.tools.simulation_tool.SimulationTool.handle", mock_handle),
    ):
        await execute_job(job_id)

    assert mock_update_status.call_count >= 2, (
        "update_status must be called at least twice: once for 'running', once for 'failed'"
    )
    # The last call must be for the terminal status 'failed'
    last_call_kwargs = mock_update_status.call_args
    last_status = (
        last_call_kwargs.kwargs.get("status")
        or (last_call_kwargs.args[1] if len(last_call_kwargs.args) > 1 else None)
    )
    assert last_status == "failed", (
        f"Last update_status call must use status='failed', got {last_status!r}"
    )
    last_error = last_call_kwargs.kwargs.get("error")
    assert last_error == "boom", f"Expected error='boom', got {last_error!r}"


async def test_execute_job_pushes_sse_job_completed_on_success() -> None:
    """On success execute_job must push a 'job_completed' event to the sse_queue."""
    from packages.agent.job_executor import execute_job

    job_id = uuid4()
    fake_job = _fake_job_row(job_id=job_id, job_type="simulate")
    mock_handle = AsyncMock(return_value=_ok_tool_result())
    mock_get_job = AsyncMock(return_value=fake_job)
    mock_update_status = AsyncMock(return_value={**fake_job, "status": "completed"})
    sse_queue: asyncio.Queue[Any] = asyncio.Queue()

    with (
        patch("packages.persistence.jobs_repo.JobsRepository.get_job", mock_get_job),
        patch("packages.persistence.jobs_repo.JobsRepository.update_status", mock_update_status),
        patch("packages.tools.simulation_tool.SimulationTool.handle", mock_handle),
    ):
        await execute_job(job_id, sse_queue=sse_queue)

    assert not sse_queue.empty()
    event = sse_queue.get_nowait()
    assert event["type"] == "job_completed"


# ---------------------------------------------------------------------------
# Parametrized job-type routing
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# _extract_files — T-614
# ---------------------------------------------------------------------------


def test_extract_files_pops_generated_files_from_output() -> None:
    """_extract_files must remove 'generated_files' from output and return it."""
    output: dict[str, Any] = {
        "result": "ok",
        "generated_files": [{"file_name": "out.csv", "mime_type": "text/csv"}],
    }
    files = _extract_files(output)

    assert files == [{"file_name": "out.csv", "mime_type": "text/csv"}]
    assert "generated_files" not in output


def test_extract_files_returns_empty_list_when_key_missing() -> None:
    """_extract_files must return [] when 'generated_files' is absent."""
    output: dict[str, Any] = {"result": "ok"}
    files = _extract_files(output)
    assert files == []


def test_extract_files_returns_empty_list_when_value_is_not_list() -> None:
    """_extract_files must return [] when 'generated_files' is not a list."""
    output: dict[str, Any] = {"generated_files": "bad"}
    files = _extract_files(output)
    assert files == []


# ---------------------------------------------------------------------------
# execute_job — file_content propagation (T-614)
# ---------------------------------------------------------------------------


async def test_execute_job_passes_file_content_to_add_file() -> None:
    """execute_job must pass file_content bytes from the tool result to repo.add_file."""
    from packages.agent.job_executor import execute_job

    job_id = uuid4()
    fake_job = _fake_job_row(job_id=job_id, job_type="simulate")
    csv_bytes = b"sku,qty\nA001,10\n"
    tool_result = ToolResult(
        output={
            "result": "ok",
            "generated_files": [
                {
                    "file_name": "sim.csv",
                    "mime_type": "text/csv",
                    "file_content": csv_bytes,
                }
            ],
        },
        audit_payload={},
    )

    mock_handle = AsyncMock(return_value=tool_result)
    mock_get_job = AsyncMock(return_value=fake_job)
    mock_update_status = AsyncMock(return_value={**fake_job, "status": "completed"})
    mock_add_file = AsyncMock(return_value={})

    with (
        patch("packages.persistence.jobs_repo.JobsRepository.get_job", mock_get_job),
        patch("packages.persistence.jobs_repo.JobsRepository.update_status", mock_update_status),
        patch("packages.persistence.jobs_repo.JobsRepository.add_file", mock_add_file),
        patch("packages.tools.simulation_tool.SimulationTool.handle", mock_handle),
    ):
        await execute_job(job_id)

    mock_add_file.assert_called_once()
    call_kwargs = mock_add_file.call_args.kwargs
    assert call_kwargs["file_content"] == csv_bytes
    assert call_kwargs["download_url"].startswith("/api/v1/jobs/files/")
    assert call_kwargs["download_url"].endswith("/download")


async def test_execute_job_sse_event_includes_download_url_for_files() -> None:
    """The 'job_completed' SSE event must include a non-empty download_url for each file."""
    from packages.agent.job_executor import execute_job

    job_id = uuid4()
    fake_job = _fake_job_row(job_id=job_id, job_type="simulate")
    tool_result = ToolResult(
        output={
            "result": "ok",
            "generated_files": [
                {
                    "file_name": "sim.csv",
                    "mime_type": "text/csv",
                    "file_content": b"a,b\n1,2\n",
                }
            ],
        },
        audit_payload={},
    )

    mock_handle = AsyncMock(return_value=tool_result)
    mock_get_job = AsyncMock(return_value=fake_job)
    mock_update_status = AsyncMock(return_value={**fake_job, "status": "completed"})
    mock_add_file = AsyncMock(return_value={})
    sse_queue: asyncio.Queue[Any] = asyncio.Queue()

    with (
        patch("packages.persistence.jobs_repo.JobsRepository.get_job", mock_get_job),
        patch("packages.persistence.jobs_repo.JobsRepository.update_status", mock_update_status),
        patch("packages.persistence.jobs_repo.JobsRepository.add_file", mock_add_file),
        patch("packages.tools.simulation_tool.SimulationTool.handle", mock_handle),
    ):
        await execute_job(job_id, sse_queue=sse_queue)

    # First event should be job_completed
    event = sse_queue.get_nowait()
    assert event["type"] == "job_completed"
    assert len(event["files"]) == 1
    url = event["files"][0]["download_url"]
    assert url.startswith("/api/v1/jobs/files/")
    assert url.endswith("/download")


@pytest.mark.parametrize(
    "job_type,tool_path",
    [
        ("simulate", "packages.tools.simulation_tool.SimulationTool.handle"),
        ("optimize", "packages.tools.optimizer_tool.OptimizerTool.handle"),
        ("forecast", "packages.tools.forecast_tool.ForecastTool.handle"),
        ("train_forecast", "packages.tools.train_forecast_tool.TrainForecastTool.handle"),
    ],
)
async def test_execute_job_routes_to_correct_tool_by_type(
    job_type: str, tool_path: str
) -> None:
    """execute_job must dispatch to the tool class that matches the job_type."""
    from packages.agent.job_executor import execute_job

    job_id = uuid4()
    fake_job = _fake_job_row(job_id=job_id, job_type=job_type)
    mock_handle = AsyncMock(return_value=_ok_tool_result())
    mock_get_job = AsyncMock(return_value=fake_job)
    mock_update_status = AsyncMock(return_value={**fake_job, "status": "completed"})

    patches: list[Any] = [
        patch("packages.persistence.jobs_repo.JobsRepository.get_job", mock_get_job),
        patch("packages.persistence.jobs_repo.JobsRepository.update_status", mock_update_status),
        patch(tool_path, mock_handle),
    ]

    if job_type == "forecast":
        from packages.prediction import LinearRegressionPredictor
        patches.append(
            patch(
                "packages.agent.job_executor._instantiate_tool",
                return_value=MagicMock(handle=mock_handle),
            )
        )

    with patches[0], patches[1], patches[2]:
        if len(patches) > 3:
            with patches[3]:
                await execute_job(job_id)
        else:
            await execute_job(job_id)

    mock_handle.assert_called_once()
