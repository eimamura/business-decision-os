from __future__ import annotations

from uuid import UUID


class PoliciesRepository:
    async def get_current(self) -> object | None:
        raise NotImplementedError("Requires DB — implement when DB wired")

    async def create(self, record: object) -> object:
        raise NotImplementedError("Requires DB — implement when DB wired")

    async def update(self, id: UUID, **kwargs: object) -> object:
        raise NotImplementedError("Requires DB — implement when DB wired")
