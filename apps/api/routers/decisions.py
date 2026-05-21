from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Any, AsyncGenerator
from uuid import UUID, uuid4

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from apps.api.state import get_orchestrator, sessions, sse_queues
from packages.agent.orchestrator import SessionUserQuery

router = APIRouter(prefix="/api/v1/decisions", tags=["decisions"])

_celery_jobs: dict[str, str] = {}


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CreateDecisionRequest(BaseModel):
    goal: str


async def _submit_celery_decision(body: CreateDecisionRequest) -> dict[str, str]:
    from packages.agent.runner import CeleryJobRunner, JobSpec
    from packages.tools.base import ToolContext

    runner = CeleryJobRunner()
    spec = JobSpec(
        kind="simulation",
        payload={"sku_id": "SKU001", "goal": body.goal},
        idempotency_key=f"decision:{body.goal[:64]}",
    )
    ctx = ToolContext(
        session_id=uuid4(),
        agent_step_id=uuid4(),
        specialist_role="orchestrator",
        actor="api",
        correlation_id=uuid4(),
    )
    handle = await runner.submit(spec, ctx)
    job_id = str(handle.job_id)
    _celery_jobs[job_id] = "queued"
    return {"job_id": job_id, "status": "queued"}


async def _stream_decision(body: CreateDecisionRequest) -> StreamingResponse:
    session_id = str(uuid4())
    sessions[session_id] = {
        "session_id": session_id,
        "status": "active",
        "goal": body.goal,
        "created_at": _iso_now(),
    }

    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    sse_queues[session_id] = queue

    query = SessionUserQuery(text=body.goal)

    orchestrator = get_orchestrator(queue)

    async def _run_and_signal() -> None:
        import logging

        _log = logging.getLogger(__name__)
        response_reply: str | None = None
        try:
            response = await orchestrator.run(UUID(session_id), query)
            response_reply = response.reply
        except Exception as exc:
            _log.exception("Orchestrator failed for session %s: %s", session_id, exc)
            await queue.put({
                "type": "error",
                "code": "orchestration_failed",
                "message": str(exc),
                "recoverable": False,
                "timestamp": _iso_now(),
            })
        finally:
            await queue.put({
                "type": "done",
                "session_id": session_id,
                "reply": response_reply,
                "timestamp": _iso_now(),
            })

    asyncio.create_task(_run_and_signal())

    async def event_generator() -> AsyncGenerator[str, None]:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30.0)
                yield f"data: {json.dumps(event)}\n\n"
                if event.get("type") == "done":
                    break
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("", response_model=None)
async def create_decision(body: CreateDecisionRequest) -> StreamingResponse | dict[str, str]:
    if os.environ.get("JOB_RUNNER_BACKEND") == "celery":
        return await _submit_celery_decision(body)
    return await _stream_decision(body)


@router.get("/{job_id}/status")
async def get_decision_job_status(job_id: str) -> dict[str, str]:
    from packages.agent.runner import CeleryJobRunner

    try:
        runner = CeleryJobRunner()
        handle = await runner.status(UUID(job_id))
        return {"status": handle.status}
    except Exception:
        stored = _celery_jobs.get(job_id)
        if stored:
            return {"status": stored}
        return {"status": "pending"}
