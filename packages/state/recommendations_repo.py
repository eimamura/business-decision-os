from __future__ import annotations

from uuid import UUID


class RecommendationsRepository:
    async def get(self, id: UUID) -> object | None:
        raise NotImplementedError("Phase 1 — DB required")

    async def create(self, record: object) -> object:
        raise NotImplementedError("Phase 1 — DB required")

    async def update(self, id: UUID, **kwargs: object) -> object:
        raise NotImplementedError("Phase 1 — DB required")

    async def list(self, **filters: object) -> list[object]:
        raise NotImplementedError("Phase 1 — DB required")
