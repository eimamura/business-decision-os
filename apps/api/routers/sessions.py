from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, AsyncGenerator
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from apps.api.state import (
    Broadcaster,
    broadcaster_ready,
    broadcasters,
    get_or_create_broadcaster_event,
    get_orchestrator,
    make_event_persister,
    notify_broadcaster_ready,
    session_run_ids,
    sessions,
)
from packages.agent.history import compress_history
from packages.agent.orchestrator import SessionResponse, SessionUserQuery
from packages.agent.rate_limiter import RateLimitExceeded, check_rate_limit
from packages.memory import ShortTermMemory
from packages.persistence.llm_usage_repo import LlmUsageRepository
from packages.persistence.session_events_repo import SessionEventRepository
from packages.persistence.sessions_repo import DecisionSessionRepository

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CreateSessionRequest(BaseModel):
    goal: str | None = None


class SendMessageRequest(BaseModel):
    content: str


class FeedbackRequest(BaseModel):
    feedback: int


class UpdateTitleRequest(BaseModel):
    title: str


class AskUserAnswerRequest(BaseModel):
    answer: str


class SessionUsageResponse(BaseModel):
    input_tokens: int
    output_tokens: int
    total_cost_usd: float


@router.post("")
async def create_session(request: Request, body: CreateSessionRequest) -> dict[str, Any]:
    session_id = str(uuid4())
    goal = body.goal or ""
    sessions[session_id] = {
        "session_id": session_id,
        "status": "pending",
        "goal": goal,
        "title": None,
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
    return {"session_id": session_id, "status": "pending", "created_at": created_at}


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
                        "status": row.get("status", "pending"),
                        "goal": row.get("goal", ""),
                        "title": row.get("title"),
                        "created_at": str(row.get("created_at", "")),
                        "messages": [],
                    }
            return [
                {
                    "session_id": str(r["id"]),
                    "status": r.get("status", "pending"),
                    "goal": r.get("goal", ""),
                    "title": r.get("title"),
                    "created_at": str(r.get("created_at", "")),
                }
                for r in db_rows
            ]
    except Exception:
        pass
    return list(sessions.values())


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_all_sessions() -> None:
    sessions.clear()
    broadcasters.clear()
    broadcaster_ready.clear()
    session_run_ids.clear()
    repo = DecisionSessionRepository()
    await repo.delete_all_sessions()


@router.delete("/{session_id}", status_code=204)
async def delete_session(session_id: str) -> None:
    sessions.pop(session_id, None)
    broadcasters.pop(session_id, None)
    broadcaster_ready.pop(session_id, None)
    session_run_ids.pop(session_id, None)
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


@router.patch("/{session_id}/title", status_code=status.HTTP_204_NO_CONTENT)
async def update_session_title(session_id: str, body: UpdateTitleRequest) -> None:
    title = body.title[:60].strip()
    if not title:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="title must not be empty",
        )
    if session_id in sessions:
        sessions[session_id]["title"] = title
    try:
        repo = DecisionSessionRepository()
        await repo.set_title(session_id, title)
    except Exception:
        _log.warning("DB unavailable; skipping title persist for %s", session_id)


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
                "status": row.get("status", "pending"),
                "goal": row.get("goal", ""),
                "title": row.get("title"),
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
                "status": db_session.get("status", "pending"),
                "goal": db_session.get("goal", ""),
                "title": db_session.get("title"),
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

    queue = broadcasters.get(session_id)
    if queue is None:
        queue = Broadcaster()
        broadcasters[session_id] = queue
        notify_broadcaster_ready(session_id)

    conversation_context: str | None = None
    try:
        msgs = await repo.get_messages(session_id, limit=60)
        short_term = [ShortTermMemory(role=m["role"], content=m["content"]) for m in msgs]
        _msgs_to_use, summary = await compress_history(short_term)
        if summary is not None:
            conversation_context = summary
    except Exception:
        _log.warning("Could not load/compress history for %s; using raw goal", session_id)

    query = SessionUserQuery(text=body.content, conversation_context=conversation_context)

    orchestrator = get_orchestrator(queue)
    orchestrator._event_persister = make_event_persister(session_id)

    run_id = str(uuid4())
    session_run_ids[session_id] = run_id

    async def _run_and_signal() -> None:
        from langgraph.errors import GraphInterrupt

        response: SessionResponse | None = None
        ask_user_id: str | None = None
        interrupted = False
        try:
            response = await orchestrator.run(UUID(session_id), query)
        except GraphInterrupt as exc:
            # Graph paused at wait_for_answer — ask_user_required SSE already sent.
            interrupted = True
            # Extract ask_user_id from interrupt payload so we can echo it in awaiting_input.
            try:
                payload = exc.args[0]
                if isinstance(payload, (list, tuple)) and payload:
                    first = payload[0]
                    ask_user_id = (
                        first.value.get("ask_user_id")
                        if hasattr(first, "value") and isinstance(first.value, dict)
                        else None
                    )
            except Exception:
                pass
        except Exception as exc:
            _log.exception("Orchestrator failed for session %s: %s", session_id, exc)
            if session_run_ids.get(session_id) != run_id:
                return  # Superseded by a newer run — drop this event
            await queue.put({
                "type": "error",
                "code": "orchestration_failed",
                "message": str(exc),
                "recoverable": False,
                "timestamp": _iso_now(),
            })
        finally:
            if session_run_ids.get(session_id) != run_id:
                return  # Superseded by a newer run — drop this event
            if interrupted:
                # Signal the SSE stream to close cleanly; the ask_user card is the response.
                await queue.put({
                    "type": "awaiting_input",
                    "session_id": session_id,
                    "ask_user_id": ask_user_id or "",
                    "timestamp": _iso_now(),
                })
            else:
                reply = response.reply if response else (
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
                try:
                    await repo.add_message(session_id, role="assistant", content=reply)
                except Exception:
                    _log.warning(
                        "DB unavailable; skipping assistant message persist for %s", session_id
                    )

    asyncio.create_task(_run_and_signal())

    message_id = str(uuid4())
    return {"message_id": message_id, "session_id": session_id, "status": "processing"}


@router.get("/{session_id}/events")
async def get_session_events(
    session_id: str, limit: int = 200
) -> list[dict[str, Any]]:
    try:
        repo = SessionEventRepository()
        return await repo.list_for_session(session_id, limit=limit)
    except RuntimeError as exc:
        if "DATABASE_URL" in str(exc):
            return []
        raise HTTPException(status_code=500, detail="Internal error")
    except Exception:
        return []


@router.get("/{session_id}/usage", response_model=SessionUsageResponse)
async def get_session_usage(session_id: str) -> SessionUsageResponse:
    try:
        repo = LlmUsageRepository()
        totals = await repo.get_session_totals(session_id)
        return SessionUsageResponse(**totals)
    except Exception:
        return SessionUsageResponse(input_tokens=0, output_tokens=0, total_cost_usd=0.0)


@router.get("/{session_id}/stream")
async def stream_session(session_id: str) -> StreamingResponse:
    async def event_generator() -> AsyncGenerator[str, None]:
        # Wait for the broadcaster to be created (notified when POST /messages or
        # POST /answer stores it). Use asyncio.Event so we wake up immediately
        # instead of sleeping in a 1-second polling loop — critical for fast
        # LLM stubs (MOCK_LLM=true) where the background task can complete before
        # the first poll interval ends.
        ready_event = get_or_create_broadcaster_event(session_id)
        broadcaster = broadcasters.get(session_id)
        if broadcaster is None:
            yield ": heartbeat\n\n"
            try:
                await asyncio.wait_for(ready_event.wait(), timeout=300)
            except asyncio.TimeoutError:
                return
            broadcaster = broadcasters.get(session_id)
            if broadcaster is None:
                return

        sub_queue = broadcaster.subscribe()
        try:
            while True:
                try:
                    event = await asyncio.wait_for(sub_queue.get(), timeout=30.0)
                    yield f"data: {json.dumps(event)}\n\n"
                    if event.get("type") in ("done", "awaiting_input", "error"):
                        break
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            broadcaster.unsubscribe(sub_queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post(
    "/{session_id}/answer",
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_ask_user_answer(
    session_id: UUID,
    body: AskUserAnswerRequest,
) -> dict[str, Any]:
    session_id_str = str(session_id)
    session = sessions.get(session_id_str)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    queue = broadcasters.get(session_id_str)
    if queue is None:
        queue = Broadcaster()
        broadcasters[session_id_str] = queue
        notify_broadcaster_ready(session_id_str)

    orchestrator = get_orchestrator(queue)
    orchestrator._event_persister = make_event_persister(session_id_str)

    repo = DecisionSessionRepository()
    answer = body.answer

    async def _run_resume_and_signal() -> None:
        response: SessionResponse | None = None
        try:
            response = await orchestrator.answer_ask_user(session_id, answer)
        except Exception as exc:
            _log.exception("Resume failed for session %s: %s", session_id_str, exc)
            await queue.put({
                "type": "error",
                "code": "resume_failed",
                "message": str(exc),
                "recoverable": False,
                "timestamp": _iso_now(),
            })
        finally:
            reply = (
                response.reply if response is not None else "Processing failed. Please try again."
            )
            if response is not None:
                session.setdefault("messages", []).append({
                    "role": "assistant",
                    "content": reply,
                    "created_at": _iso_now(),
                })
            await queue.put({
                "type": "done",
                "session_id": session_id_str,
                "reply": reply,
                "timestamp": _iso_now(),
            })
            if response is not None:
                try:
                    await repo.add_message(session_id_str, role="assistant", content=reply)
                except Exception:
                    _log.warning(
                        "DB unavailable; skipping assistant message persist for %s", session_id_str
                    )

    asyncio.create_task(_run_resume_and_signal())
    return {"status": "processing", "session_id": session_id_str}
