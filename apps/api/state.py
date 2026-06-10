from __future__ import annotations

import asyncio
import logging
import os
from asyncio import Queue
from collections.abc import Callable
from typing import Any
from uuid import UUID

from packages.agent.llm import LLMUsage
from packages.agent.orchestrator import SessionOrchestrator
from packages.agent.runner import AcaJobsRunner, CeleryJobRunner, InProcessJobRunner
from packages.memory import PgVectorMemoryStore, StubMemoryStore
from packages.persistence.llm_usage_repo import LlmUsageRepository
from packages.persistence.session_events_repo import SessionEventRepository
from packages.tools import create_tool_registry

logger = logging.getLogger(__name__)

sessions: dict[str, dict[str, Any]] = {}

# Registry of in-flight background asyncio tasks, keyed by session_id string.
# Populated by post_message / submit_ask_user_answer; cleaned up on task
# completion (via done-callback) and on session deletion.
session_tasks: dict[str, asyncio.Task[None]] = {}

# Tombstone set: session IDs that have been deleted during this process lifetime.
# Used by make_event_persister to skip writes after a session is deleted, avoiding
# FK-violation spam from orphaned background tasks.  A session in this set may or
# may not be present in the DB — the tombstone only tracks the deletion intent
# issued in this process.  Sessions recovered from DB (via get_or_recover_session)
# are NOT removed from the tombstone; recovery is an explicit opt-in by the router.
_deleted_session_ids: set[str] = set()

_shared_pool: Any = None


async def init_shared_pool() -> None:
    global _shared_pool
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        return
    from psycopg import AsyncConnection
    from psycopg.rows import dict_row
    from psycopg_pool import AsyncConnectionPool

    psycopg_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
    pool: AsyncConnectionPool[AsyncConnection[dict[str, Any]]] = AsyncConnectionPool(
        psycopg_url,
        max_size=5,
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
        open=False,
    )
    await pool.open()
    _shared_pool = pool


async def close_shared_pool() -> None:
    global _shared_pool
    if _shared_pool is not None:
        await _shared_pool.close()
        _shared_pool = None


_TERMINAL_EVENT_TYPES = frozenset({"done", "error", "awaiting_input"})
_BROADCASTER_BUFFER_MAX = 1000


class Broadcaster:
    """Fan-out pub/sub so multiple /stream connections each get every event.

    Replay buffer: events are buffered until a terminal event (done / error /
    awaiting_input) is delivered.  A subscriber that joins *after* some events
    have already been emitted (the common case when the SSE client registers
    slightly after the background task starts) receives all buffered events
    immediately on subscribe(), so the execution trace is always complete.
    """

    def __init__(self) -> None:
        self._subs: list[Queue[dict[str, Any]]] = []
        self._buffer: list[dict[str, Any]] = []

    async def put(self, event: dict[str, Any]) -> None:
        # Buffer the event so late subscribers can replay it.
        if len(self._buffer) < _BROADCASTER_BUFFER_MAX:
            self._buffer.append(event)

        for q in self._subs:
            await q.put(event)

        # After a terminal event, clear the buffer entirely so the next SSE
        # subscription (for a subsequent answer or new message) does not replay
        # a stale terminal event from the previous run.  Subscribers that were
        # already connected during the run receive the terminal event live via
        # their queue; they do not need it in the buffer.
        if event.get("type") in _TERMINAL_EVENT_TYPES:
            self._buffer = []

    def subscribe(self) -> Queue[dict[str, Any]]:
        q: Queue[dict[str, Any]] = Queue()
        # Replay any buffered events synchronously before adding to subscribers.
        # This is safe: subscribe() is called from an async context, but Queue.put_nowait
        # is non-blocking and always succeeds for an unbounded Queue.
        for buffered in self._buffer:
            q.put_nowait(buffered)
        self._subs.append(q)
        return q

    def unsubscribe(self, q: Queue[dict[str, Any]]) -> None:
        try:
            self._subs.remove(q)
        except ValueError:
            pass


broadcasters: dict[str, Broadcaster] = {}

# Per-session asyncio.Event, set when a broadcaster is first stored for the session.
# Allows /stream to wake up instantly instead of polling with a fixed sleep interval.
broadcaster_ready: dict[str, asyncio.Event] = {}

# Tracks the most-recent run_id per session. A background task whose run_id no longer
# matches has been superseded by a newer POST /messages and must drop its events.
session_run_ids: dict[str, str] = {}


def get_or_create_broadcaster_event(session_id: str) -> asyncio.Event:
    if session_id not in broadcaster_ready:
        broadcaster_ready[session_id] = asyncio.Event()
    return broadcaster_ready[session_id]


def notify_broadcaster_ready(session_id: str) -> None:
    """Call after storing a Broadcaster in broadcasters[session_id]."""
    get_or_create_broadcaster_event(session_id).set()


def _build_runner() -> AcaJobsRunner | InProcessJobRunner | CeleryJobRunner:
    backend = os.environ.get("JOB_RUNNER_BACKEND", "in_process").strip()
    if backend == "aca":
        return AcaJobsRunner()
    if backend == "celery":
        return CeleryJobRunner()
    return InProcessJobRunner()


def _build_memory_store() -> PgVectorMemoryStore | StubMemoryStore:
    url = os.environ.get("DATABASE_URL", "")
    if url:
        url = url.replace("postgresql+asyncpg://", "postgresql://")
        return PgVectorMemoryStore(url)
    return StubMemoryStore()


async def _real_usage_writer(
    session_id: UUID | None,
    agent_step_id: UUID | None,
    specialist_role: str | None,
    provider: str,
    model: str,
    usage: LLMUsage,
) -> None:
    # Resolve the step to write against.  Priority:
    #   1. Caller already supplied agent_step_id  → use it directly.
    #   2. session_id present but no agent_step_id → create a fallback step row.
    #   3. Both are None                           → skip (no session context).
    effective_step_id: UUID | None = agent_step_id

    if effective_step_id is None:
        if session_id is None:
            # No session context — skip the write entirely.
            return
        # Create a lightweight "llm_call" step so the usage row joins the session.
        try:
            from packages.persistence.agent_steps_repo import make_step

            fallback_id = await make_step(
                str(session_id),
                step_type="llm_call",
                specialist_role=specialist_role or "unknown",
            )
            effective_step_id = fallback_id
        except Exception as exc:
            logger.warning("LLM usage fallback make_step failed: %s", exc)

    if effective_step_id is None:
        # make_step returned None (DB failure) — skip the write.
        return

    repo = LlmUsageRepository()
    _step_id = effective_step_id  # captured for the closure below

    async def _write() -> None:
        try:
            await repo.create(
                agent_step_id=str(_step_id),
                model=model,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                cache_read_tokens=usage.cache_read_tokens,
                cache_write_tokens=usage.cache_write_tokens,
                total_cost_usd=float(usage.total_cost_usd),
                prompt_messages_json=usage.prompt_messages_json,
                response_text=usage.response_text,
                tool_calls_json=usage.tool_calls_json,
            )
        except RuntimeError as exc:
            logger.warning("LLM usage write skipped: %s", exc)
        except Exception as exc:
            logger.warning("LLM usage write failed: %s", exc)

    asyncio.create_task(_write())


def make_event_persister(session_id: str) -> Callable[[dict[str, Any]], Any]:
    """Return a fire-and-forget persister for SSE events of *session_id*.

    Deleted-session semantics: if *session_id* appears in ``_deleted_session_ids``
    the write is skipped entirely and no task is created.  This prevents the
    FK-violation spam that occurs when an orphaned background run (not yet
    cancelled) tries to persist events after its session row was deleted.

    FK-violation handling: asyncpg raises ``ForeignKeyViolationError`` when the
    ``decision_sessions`` parent row has already been removed.  We catch it at
    ``debug`` level (single line) rather than ``warning`` to avoid log spam from
    the narrow window between deletion and task cancellation.
    """

    async def _persister(event: dict[str, Any]) -> None:
        # Guard: skip write if this session has been marked deleted in this process.
        if session_id in _deleted_session_ids:
            return

        repo = SessionEventRepository()

        async def _write() -> None:
            try:
                await repo.create(
                    session_id=session_id,
                    event_type=event.get("type", "unknown"),
                    payload=event,
                )
            except RuntimeError as exc:
                logger.warning("event persist skipped: %s", exc)
            except Exception as exc:
                # Attempt to detect FK violation (asyncpg path) and downgrade to
                # debug to avoid noisy warning spam during the brief window
                # between session deletion and background-task cancellation.
                try:
                    import asyncpg  # noqa: PLC0415 — conditional import; asyncpg optional

                    if isinstance(exc, asyncpg.exceptions.ForeignKeyViolationError):
                        logger.debug(
                            "event persist skipped (session deleted): session=%s type=%s",
                            session_id,
                            event.get("type"),
                        )
                        return
                except ImportError:
                    pass
                # FK violation surfaced as a string message (non-asyncpg path)
                exc_str = str(exc)
                if "foreign key constraint" in exc_str or "ForeignKeyViolation" in exc_str:
                    logger.debug(
                        "event persist skipped (session deleted): session=%s type=%s",
                        session_id,
                        event.get("type"),
                    )
                    return
                logger.warning("event persist failed: %s", exc)

        asyncio.create_task(_write())

    return _persister


def get_orchestrator(sse_queue: Any | None = None) -> SessionOrchestrator:
    from packages.agent.model_registry import create_model_registry

    registry = create_model_registry(usage_writer=_real_usage_writer)
    runner = _build_runner()
    tool_registry = create_tool_registry(runner=runner, model=registry.get("control"))
    memory_store = _build_memory_store()
    return SessionOrchestrator(
        registry.get("control"), tool_registry, memory_store, sse_queue,
        checkpoint_pool=_shared_pool,
        model_registry=registry,
    )
