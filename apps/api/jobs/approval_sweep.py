from __future__ import annotations


async def sweep_expired_approvals(db_session: object, ttl_seconds: int = 86400) -> None:
    raise NotImplementedError("Phase 1 — DB required")
