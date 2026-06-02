from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from packages.tools.base import ToolContext, ToolResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ctx() -> ToolContext:
    return ToolContext(
        session_id=uuid4(),
        agent_step_id=uuid4(),
        specialist_role="simulation_optimizer",
        actor="test",
        correlation_id=uuid4(),
        user_role="admin",
    )


def _fake_job(job_type: str = "simulate") -> dict[str, Any]:
    return {
        "id": uuid4(),
        "session_id": uuid4(),
        "status": "pending_approval",
        "job_type": job_type,
        "params_json": {},
        "approval_id": None,
        "created_at": None,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_handle_creates_job_row_with_correct_job_type() -> None:
    """handle() must call JobsRepository.create with the supplied job_type."""
    from packages.tools.job_dispatch_tool import JobDispatchTool

    fake_job = _fake_job("simulate")
    mock_create = AsyncMock(return_value=fake_job)

    with patch(
        "packages.persistence.jobs_repo.JobsRepository.create",
        mock_create,
    ):
        tool = JobDispatchTool()
        ctx = _make_ctx()
        await tool.handle(
            {"job_type": "simulate", "params": {}, "description": "test"},
            ctx,
        )

    mock_create.assert_called_once()
    _, kwargs = mock_create.call_args
    assert kwargs.get("job_type") == "simulate"


async def test_handle_returns_tool_result_with_job_id() -> None:
    """handle() must return a ToolResult whose output contains the mocked job's id."""
    from packages.tools.job_dispatch_tool import JobDispatchTool

    expected_id = uuid4()
    fake_job = _fake_job("simulate")
    fake_job["id"] = expected_id
    mock_create = AsyncMock(return_value=fake_job)

    with patch(
        "packages.persistence.jobs_repo.JobsRepository.create",
        mock_create,
    ):
        tool = JobDispatchTool()
        ctx = _make_ctx()
        result = await tool.handle(
            {"job_type": "simulate", "params": {}, "description": "test"},
            ctx,
        )

    assert isinstance(result, ToolResult)
    assert result.output["job_id"] == str(expected_id)


async def test_handle_returns_pending_approval_status() -> None:
    """handle() must return status == 'pending_approval' in the ToolResult output."""
    from packages.tools.job_dispatch_tool import JobDispatchTool

    fake_job = _fake_job("simulate")
    mock_create = AsyncMock(return_value=fake_job)

    with patch(
        "packages.persistence.jobs_repo.JobsRepository.create",
        mock_create,
    ):
        tool = JobDispatchTool()
        ctx = _make_ctx()
        result = await tool.handle(
            {"job_type": "simulate", "params": {"horizon": 30}, "description": "run sim"},
            ctx,
        )

    assert result.output["status"] == "pending_approval"
