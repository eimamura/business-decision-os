from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any, AsyncGenerator
from uuid import UUID, uuid4

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from apps.api.state import get_orchestrator, sessions, sse_queues
from packages.agent.orchestrator import SessionGoal

router = APIRouter(prefix="/api/v1/decisions", tags=["decisions"])


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CreateDecisionRequest(BaseModel):
    goal: str


@router.post("")
async def create_decision(body: CreateDecisionRequest) -> StreamingResponse:
    session_id = str(uuid4())
    sessions[session_id] = {
        "session_id": session_id,
        "status": "active",
        "goal": body.goal,
        "created_at": _iso_now(),
    }

    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    sse_queues[session_id] = queue

    goal = SessionGoal(text=body.goal)

    await queue.put({
        "type": "session_started",
        "session_id": session_id,
        "timestamp": _iso_now(),
    })

    orchestrator = get_orchestrator(queue)

    async def _run_and_signal() -> None:
        import logging
        _log = logging.getLogger(__name__)
        try:
            await orchestrator.run(UUID(session_id), goal)
        except Exception as exc:
            _log.exception("Orchestrator failed for session %s: %s", session_id, exc)
            await queue.put({
                "type": "error",
                "code": "orchestration_failed",
                "message": str(exc),
                "timestamp": _iso_now(),
            })
        finally:
            await queue.put({
                "type": "done",
                "session_id": session_id,
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
