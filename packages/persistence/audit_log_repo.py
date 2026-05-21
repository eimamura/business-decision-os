from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import UUID


def compute_hash(payload: dict[str, Any], prev_hash: str | None) -> str:
    raw = json.dumps(
        {"payload": payload, "prev_hash": prev_hash or ""},
        sort_keys=True,
    )
    return hashlib.sha256(raw.encode()).hexdigest()


class AuditLogRepository:
    async def get(self, id: UUID) -> object | None:
        raise NotImplementedError("Phase 1 — DB required")

    async def create(self, record: object) -> object:
        raise NotImplementedError("Phase 1 — DB required")

    async def update(self, id: UUID, **kwargs: object) -> object:
        raise NotImplementedError("Phase 1 — DB required")

    async def list(self, **filters: object) -> list[object]:
        raise NotImplementedError("Phase 1 — DB required")

    async def hash_chain_write(
        self,
        session_id: UUID | None,
        agent_step_id: UUID | None,
        tool_call_id: UUID | None,
        event_type: str,
        payload: dict[str, Any],
        actor: str | None,
    ) -> object:
        prev_hash: str | None = None
        compute_hash(payload, prev_hash)
        raise NotImplementedError("Phase 1 — DB required")
