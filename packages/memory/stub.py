"""In-memory stub implementations of the six typed memory stores.

These stubs are intended for use in unit tests only. They store records in a
plain Python list and return the most recent ``k`` records from ``search()``
(no semantic matching — pure recency ordering).

Do NOT use these stubs in production or integration tests that rely on
semantic search behaviour.
"""

from __future__ import annotations

from typing import Any

from packages.memory import (
    DecisionMemory,
    DomainMemory,
    LongTermMemory,
    ShortTermMemory,
    UserMemory,
    WorkingMemory,
)

__all__ = [
    "StubShortTermMemory",
    "StubWorkingMemory",
    "StubLongTermMemory",
    "StubDecisionMemory",
    "StubUserMemory",
    "StubDomainMemory",
]


class StubShortTermMemory(ShortTermMemory):
    """Stub implementation of ShortTermMemory backed by an in-memory list."""

    def __init__(self) -> None:
        self._records: list[dict[str, Any]] = []

    def write(self, record: dict[str, Any]) -> None:
        self._records.append(record)

    def search(self, query: str, k: int = 5) -> list[dict[str, Any]]:
        return self._records[-k:] if k > 0 else []


class StubWorkingMemory(WorkingMemory):
    """Stub implementation of WorkingMemory backed by an in-memory list."""

    def __init__(self) -> None:
        self._records: list[dict[str, Any]] = []

    def write(self, record: dict[str, Any]) -> None:
        self._records.append(record)

    def search(self, query: str, k: int = 5) -> list[dict[str, Any]]:
        return self._records[-k:] if k > 0 else []


class StubLongTermMemory(LongTermMemory):
    """Stub implementation of LongTermMemory backed by an in-memory list."""

    def __init__(self) -> None:
        self._records: list[dict[str, Any]] = []

    def write(self, record: dict[str, Any]) -> None:
        self._records.append(record)

    def search(self, query: str, k: int = 5) -> list[dict[str, Any]]:
        return self._records[-k:] if k > 0 else []


class StubDecisionMemory(DecisionMemory):
    """Stub implementation of DecisionMemory backed by an in-memory list."""

    def __init__(self) -> None:
        self._records: list[dict[str, Any]] = []

    def write(self, record: dict[str, Any]) -> None:
        self._records.append(record)

    def search(self, query: str, k: int = 5) -> list[dict[str, Any]]:
        return self._records[-k:] if k > 0 else []


class StubUserMemory(UserMemory):
    """Stub implementation of UserMemory backed by an in-memory list."""

    def __init__(self) -> None:
        self._records: list[dict[str, Any]] = []

    def write(self, record: dict[str, Any]) -> None:
        self._records.append(record)

    def search(self, query: str, k: int = 5) -> list[dict[str, Any]]:
        return self._records[-k:] if k > 0 else []


class StubDomainMemory(DomainMemory):
    """Stub implementation of DomainMemory backed by an in-memory list."""

    def __init__(self) -> None:
        self._records: list[dict[str, Any]] = []

    def write(self, record: dict[str, Any]) -> None:
        self._records.append(record)

    def search(self, query: str, k: int = 5) -> list[dict[str, Any]]:
        return self._records[-k:] if k > 0 else []
