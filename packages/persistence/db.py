from __future__ import annotations

import os

import asyncpg

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        raw = os.environ.get("DATABASE_URL")
        if not raw:
            raise RuntimeError("DATABASE_URL not set")
        url = raw.replace("postgresql+asyncpg://", "postgresql://")
        _pool = await asyncpg.create_pool(url, command_timeout=10)
    return _pool
