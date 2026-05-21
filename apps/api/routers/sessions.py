from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, AsyncGenerator
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from apps.api.state import get_orchestrator, sessions, sse_queues
from packages.agent.history import compress_history
from packages.agent.orchestrator import SessionGoal
from packages.agent.rate_limiter import RateLimitExceeded, check_rate_limit
from packages.schemas.recommendation import Recommendation
from packages.state.sessions_repo import DecisionSessionRepository

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _format_recommendation(rec: Recommendation) -> str:
    if rec.direct_reply:
        return rec.direct_reply
    order_qty = rec.primary.action.get("order_qty", "N/A") if rec.primary else "N/A"
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


class FeedbackRequest(BaseModel):
    feedback: int


@router.post("")
async def create_session(request: Request, body: CreateSessionRequest) -> dict[str, Any]:
    session_id = str(uuid4())
    goal = body.goal or ""
    sessions[session_id] = {
        "session_id": session_id,
        "status": "active",
        "goal": goal,
        "created_at": _iso_now(),
        "messages": [],
    }
    try:
        repo = DecisionSessionRepository()
        user_id = getattr(request.state, "user_id", None)
        await repo.create(session_id, user_id, goal)
    except Exception:
        _log.warning("DB unavailable; skipping session persist for %s", session_id)
    created_at = sessions[session_id]["created_at"]
    return {"session_id": session_id, "status": "active", "created_at": created_at}


@router.get("")
async def list_sessions() -> list[dict[str, Any]]:
    try:
        repo = DecisionSessionRepository()
        db_rows = await repo.list_sessions()
        if db_rows:
            # Reconcile in-memory dict so downstream endpoints stay consistent
            for row in db_rows:
                sid = str(row["id"])
                if sid not in sessions:
                    sessions[sid] = {
                        "session_id": sid,
                        "status": row.get("status", "active"),
                        "goal": row.get("goal", ""),
                        "created_at": str(row.get("created_at", "")),
                        "messages": [],
                    }
            return [
                {
                    "session_id": str(r["id"]),
                    "status": r.get("status", "active"),
                    "goal": r.get("goal", ""),
                    "created_at": str(r.get("created_at", "")),
                }
                for r in db_rows
            ]
    except Exception:
        pass
    return list(sessions.values())


@router.delete("/{session_id}", status_code=204)
async def delete_session(session_id: str) -> None:
    sessions.pop(session_id, None)
    try:
        repo = DecisionSessionRepository()
        deleted = await repo.delete_session(session_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Session not found")
    except HTTPException:
        raise
    except RuntimeError as e:
        if "DATABASE_URL" in str(e):
            return
        raise HTTPException(status_code=500, detail="Internal error")


@router.get("/{session_id}")
async def get_session(session_id: str) -> dict[str, Any]:
    session = sessions.get(session_id)
    if not session:
        try:
            repo = DecisionSessionRepository()
            row = await repo.get(session_id)
            if row is None:
                raise HTTPException(status_code=404, detail="Session not found")
            session = {
                "session_id": session_id,
                "status": row.get("status", "active"),
                "goal": row.get("goal", ""),
                "created_at": str(row.get("created_at", "")),
                "messages": [],
            }
            sessions[session_id] = session
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.get("/{session_id}/messages")
async def get_messages(session_id: str) -> list[dict[str, Any]]:
    try:
        repo = DecisionSessionRepository()
        db_messages = await repo.get_messages(session_id)
        return [
            {
                "id": str(msg["id"]),
                "role": msg["role"],
                "content": msg["content"],
                "created_at": (
                    msg["created_at"].isoformat()
                    if hasattr(msg["created_at"], "isoformat")
                    else msg["created_at"]
                ),
                "feedback": msg.get("feedback"),
            }
            for msg in db_messages
        ]
    except RuntimeError as e:
        if "DATABASE_URL" not in str(e):
            raise HTTPException(status_code=500, detail="Internal error")

    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return [
        {
            "id": str(uuid4()),
            "role": msg["role"],
            "content": msg["content"],
            "created_at": msg.get("created_at"),
            "feedback": None,
        }
        for msg in session.get("messages", [])
    ]


@router.patch("/{session_id}/messages/{message_id}/feedback", status_code=204)
async def set_message_feedback(
    session_id: str,
    message_id: str,
    body: FeedbackRequest,
) -> None:
    if body.feedback not in (1, -1):
        raise HTTPException(status_code=422, detail="feedback must be 1 or -1")

    try:
        repo = DecisionSessionRepository()
        updated = await repo.set_message_feedback(
            message_id=message_id,
            feedback=body.feedback,
            session_id=session_id,
        )
        if not updated:
            raise HTTPException(status_code=404, detail="Message not found")
    except HTTPException:
        raise
    except RuntimeError as e:
        if "DATABASE_URL" in str(e):
            return
        raise HTTPException(status_code=500, detail="Internal error")


@router.post("/{session_id}/messages")
async def post_message(
    session_id: str, body: SendMessageRequest, request: Request
) -> dict[str, Any]:
    user_id = getattr(request.state, "user_id", "anonymous")
    try:
        await check_rate_limit(user_id)
    except RateLimitExceeded:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please wait before sending another message.",
        )

    session = sessions.get(session_id)
    if not session:
        # Server may have restarted — attempt DB recovery before returning 404
        try:
            repo_check = DecisionSessionRepository()
            db_session = await repo_check.get(session_id)
            if db_session is None:
                raise HTTPException(status_code=404, detail="Session not found")
            sessions[session_id] = {
                "session_id": session_id,
                "status": db_session.get("status", "active"),
                "goal": db_session.get("goal", ""),
                "created_at": str(db_session.get("created_at", _iso_now())),
                "messages": [],
            }
            session = sessions[session_id]
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=404, detail="Session not found")

    session.setdefault("messages", []).append({
        "role": "user",
        "content": body.content,
        "created_at": _iso_now(),
    })

    repo = DecisionSessionRepository()
    try:
        await repo.add_message(session_id, role="user", content=body.content)
    except Exception:
        _log.warning("DB unavailable; skipping user message persist for %s", session_id)

    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    sse_queues[session_id] = queue

    goal_text = body.content
    try:
        msgs = await repo.get_messages(session_id, limit=60)
        msgs_to_use, summary = await compress_history(msgs)
        if summary is not None:
            goal_text = f"[Conversation context: {summary}]\n\n{goal_text}"
    except Exception:
        _log.warning("Could not load/compress history for %s; using raw goal", session_id)

    goal = SessionGoal(text=goal_text)

    await queue.put({
        "type": "session_started",
        "session_id": session_id,
        "timestamp": _iso_now(),
    })

    orchestrator = get_orchestrator(queue)

    async def _run_and_signal() -> None:
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
            try:
                await repo.add_message(session_id, role="assistant", content=reply)
            except Exception:
                _log.warning(
                    "DB unavailable; skipping assistant message persist for %s", session_id
                )
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
    async def event_generator() -> AsyncGenerator[str, None]:
        max_wait = 300
        elapsed = 0
        while elapsed < max_wait:
            queue = sse_queues.get(session_id)
            if queue:
                break
            yield ": heartbeat\n\n"
            await asyncio.sleep(1.0)
            elapsed += 1
        else:
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
