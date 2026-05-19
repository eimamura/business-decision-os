from __future__ import annotations

from uuid import uuid4

import pytest

from packages.agent.job_runner import InProcessJobRunner, JobSpec
from packages.tools.base import ToolContext


def _make_ctx() -> ToolContext:
    return ToolContext(
        session_id=uuid4(),
        agent_step_id=uuid4(),
        specialist_role="data_engineer",
        actor="test",
        correlation_id=uuid4(),
    )


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
async def test_result_raises_not_implemented():
    runner = InProcessJobRunner()
    with pytest.raises(NotImplementedError, match="Phase 2"):
        await runner.result(uuid4())
