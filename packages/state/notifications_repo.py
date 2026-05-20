from __future__ import annotations

from uuid import UUID


class NotificationsRepository:
    async def get(self, id: UUID) -> object | None:
        raise NotImplementedError("Requires DB — implement when DB wired")

    async def create(self, record: object) -> object:
        raise NotImplementedError("Requires DB — implement when DB wired")

    async def list(self, **filters: object) -> list[object]:
        raise NotImplementedError("Requires DB — implement when DB wired")

    async def mark_read(self, id: UUID) -> None:
        raise NotImplementedError("Requires DB — implement when DB wired")
