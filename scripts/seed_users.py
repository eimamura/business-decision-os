"""Seeds the users table with the dev-user row.

Usage: uv run python scripts/seed_users.py
"""

from __future__ import annotations

import asyncio
from uuid import UUID

DEV_USER_ID = UUID("00000000-0000-0000-0000-000000000001")
DEV_USER_EMAIL = "dev@local"
DEV_USER_NAME = "Dev User"


async def seed() -> None:
    raise NotImplementedError("Phase 1 — DB required")


if __name__ == "__main__":
    asyncio.run(seed())
