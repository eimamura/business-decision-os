"""Physical async implementation of the WorkingMemory store.

T-292 — WorkingMemoryStore backed by agent_steps via AgentStepsRepository.

WorkingMemoryStore is a standalone async class that does NOT inherit from WorkingMemory.
The abstract typed bases have sync signatures (locked per AGENTS.md); all physical DB
operations are async. Use StubWorkingMemory from packages/memory/stub.py for unit tests.

T-293: no Alembic migration required — agent_steps already exists and intermediate_artifact
is not used by this implementation.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from packages.persistence.agent_steps_repo import AgentStepsRepository

_log = logging.getLogger(__name__)

_SESSION_PREFIX = "session:"


class WorkingMemoryStore:
    """Async physical implementation of the WorkingMemory concept backed by agent_steps."""

    def __init__(self, repo: AgentStepsRepository | None = None) -> None:
        self._repo = repo or AgentStepsRepository()

    async def write(self, record: dict[str, Any]) -> None:
        """Insert a tool-result step into agent_steps.

        Required keys: session_id (str), content (str).
        Optional keys: step_type (default "tool_result"), specialist_role (default "control").
        """
        session_id: str = record["session_id"]
        content: str = record["content"]
        step_type: str = record.get("step_type", "tool_result")
        specialist_role: str = record.get("specialist_role", "control")

        step_id = str(uuid.uuid4())
        await self._repo.create(
            step_id=step_id,
            session_id=session_id,
            specialist_role=specialist_role,
            step_type=step_type,
            input_json={"content": content},
            started_at=datetime.now(timezone.utc),
        )
        _log.debug(
            "WorkingMemoryStore.write: step_id=%s session_id=%s step_type=%s",
            step_id,
            session_id,
            step_type,
        )

    async def search(self, query: str, k: int = 5) -> list[dict[str, Any]]:
        """Return the k most recent agent_steps rows for a session.

        Query format: "session:<uuid>" — any other format returns [] without error.
        Returned dicts: step_id, session_id, step_type, content, created_at.
        """
        if not query.startswith(_SESSION_PREFIX):
            _log.debug(
                "WorkingMemoryStore.search: query %r does not match prefix — returning []",
                query,
            )
            return []

        session_id = query[len(_SESSION_PREFIX):]
        return await self._repo.list_recent_by_session(session_id=session_id, limit=k)
