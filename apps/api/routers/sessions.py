from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any, AsyncGenerator
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from apps.api.state import get_orchestrator, sessions, sse_queues
from packages.agent.orchestrator import SessionGoal
from packages.schemas.recommendation import Recommendation

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _format_recommendation(rec: Recommendation) -> str:
    order_qty = rec.primary.action.get("order_qty", "N/A")
    lines = [
        "## Recommendation",
        "",
        f"**Primary Action**: Order **{order_qty} units**",
        f"**Risk Level**: {rec.risk_level}",
        f"**Rationale**: {rec.rationale}",
    ]
    if rec.alternatives:
        lines.append("\n**Alternatives**:")
        for alt in rec.alternatives:
            alt_qty = alt.action.get("order_qty", "N/A")
            lines.append(f"- Order {alt_qty} units")
    if rec.requires_approval:
        lines.append("\n_This recommendation requires approval before execution._")
    return "\n".join(lines)


class CreateSessionRequest(BaseModel):
    goal: str | None = None


class SendMessageRequest(BaseModel):
    content: str


@router.post("")
async def create_session(body: CreateSessionRequest) -> dict[str, Any]:
    session_id = str(uuid4())
    sessions[session_id] = {
        "session_id": session_id,
        "status": "active",
        "goal": body.goal,
        "created_at": _iso_now(),
        "messages": [],
    }
    created_at = sessions[session_id]["created_at"]
    return {"session_id": session_id, "status": "active", "created_at": created_at}


@router.get("")
async def list_sessions() -> list[dict[str, Any]]:
    return list(sessions.values())


@router.get("/{session_id}")
async def get_session(session_id: str) -> dict[str, Any]:
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.get("/{session_id}/messages")
async def get_messages(session_id: str) -> list[dict[str, Any]]:
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return list(session.get("messages", []))


@router.post("/{session_id}/messages")
async def post_message(session_id: str, body: SendMessageRequest) -> dict[str, Any]:
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.setdefault("messages", []).append({
        "role": "user",
        "content": body.content,
        "created_at": _iso_now(),
    })

    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    sse_queues[session_id] = queue

    goal_text = session.get("goal") or body.content
    goal = SessionGoal(text=goal_text)

    await queue.put({
        "type": "session_started",
        "session_id": session_id,
        "timestamp": _iso_now(),
    })

    orchestrator = get_orchestrator(queue)

    async def _run_and_signal() -> None:
        import logging
        _log = logging.getLogger(__name__)
        recommendation: Recommendation | None = None
        try:
            recommendation = await orchestrator.run(UUID(session_id), goal)
        except Exception as exc:
            _log.exception("Orchestrator failed for session %s: %s", session_id, exc)
            await queue.put({
                "type": "error",
                "code": "orchestration_failed",
                "message": str(exc),
                "timestamp": _iso_now(),
            })
        finally:
            reply = _format_recommendation(recommendation) if recommendation else (
                "Processing failed. Please try again."
            )
            session.setdefault("messages", []).append({
                "role": "assistant",
                "content": reply,
                "created_at": _iso_now(),
            })
            await queue.put({
                "type": "done",
                "session_id": session_id,
                "reply": reply,
                "timestamp": _iso_now(),
            })

    asyncio.create_task(_run_and_signal())

    message_id = str(uuid4())
    return {"message_id": message_id, "session_id": session_id, "status": "processing"}


@router.get("/{session_id}/stream")
async def stream_session(session_id: str) -> StreamingResponse:
    print(f"Client connected to stream for session {session_id}")
    async def event_generator() -> AsyncGenerator[str, None]:
        queue = sse_queues.get(session_id)
        if not queue:
            yield 'data: {"type": "error", "code": "no_stream", "message": "Stream not found"}\n\n'
            return
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
