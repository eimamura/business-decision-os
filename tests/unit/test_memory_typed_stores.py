from __future__ import annotations

"""Unit tests for P41 typed memory store base classes and stub implementations.

T-290: abstract base classes
T-291: stub implementations
"""

import pytest

from packages.memory import (
    DecisionMemory,
    DomainMemory,
    LongTermMemory,
    MemoryStore,
    ShortTermMemory,
    UserMemory,
    WorkingMemory,
)
from packages.memory.stub import (
    StubDecisionMemory,
    StubDomainMemory,
    StubLongTermMemory,
    StubShortTermMemory,
    StubUserMemory,
    StubWorkingMemory,
)


# ---------------------------------------------------------------------------
# T-290 — Abstract base class structural checks
# ---------------------------------------------------------------------------


def test_memory_store_is_abstract() -> None:
    with pytest.raises(TypeError):
        MemoryStore()  # type: ignore[abstract]


@pytest.mark.parametrize(
    "cls",
    [
        ShortTermMemory,
        WorkingMemory,
        LongTermMemory,
        DecisionMemory,
        UserMemory,
        DomainMemory,
    ],
)
def test_typed_store_inherits_memory_store(cls: type) -> None:
    assert issubclass(cls, MemoryStore)


@pytest.mark.parametrize(
    "cls",
    [
        ShortTermMemory,
        WorkingMemory,
        LongTermMemory,
        DecisionMemory,
        UserMemory,
        DomainMemory,
    ],
)
def test_typed_store_is_abstract(cls: type) -> None:
    """Typed stores must remain abstract — concrete impl lives in stub.py."""
    with pytest.raises(TypeError):
        cls()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# T-291 — Stub implementations
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "stub_cls,base_cls",
    [
        (StubShortTermMemory, ShortTermMemory),
        (StubWorkingMemory, WorkingMemory),
        (StubLongTermMemory, LongTermMemory),
        (StubDecisionMemory, DecisionMemory),
        (StubUserMemory, UserMemory),
        (StubDomainMemory, DomainMemory),
    ],
)
def test_stub_inherits_typed_store(stub_cls: type, base_cls: type) -> None:
    assert issubclass(stub_cls, base_cls)


@pytest.mark.parametrize(
    "stub_cls",
    [
        StubShortTermMemory,
        StubWorkingMemory,
        StubLongTermMemory,
        StubDecisionMemory,
        StubUserMemory,
        StubDomainMemory,
    ],
)
def test_stub_is_concrete(stub_cls: type) -> None:
    instance = stub_cls()
    assert instance is not None


@pytest.mark.parametrize(
    "stub_cls",
    [
        StubShortTermMemory,
        StubWorkingMemory,
        StubLongTermMemory,
        StubDecisionMemory,
        StubUserMemory,
        StubDomainMemory,
    ],
)
def test_stub_write_and_search_returns_record(stub_cls: type) -> None:
    store = stub_cls()
    record = {"key": "value", "data": 42}
    store.write(record)
    results = store.search("any query", k=5)
    assert len(results) == 1
    assert results[0] == record


@pytest.mark.parametrize(
    "stub_cls",
    [
        StubShortTermMemory,
        StubWorkingMemory,
        StubLongTermMemory,
        StubDecisionMemory,
        StubUserMemory,
        StubDomainMemory,
    ],
)
def test_stub_search_empty_store_returns_empty_list(stub_cls: type) -> None:
    store = stub_cls()
    results = store.search("query", k=5)
    assert results == []


@pytest.mark.parametrize(
    "stub_cls",
    [
        StubShortTermMemory,
        StubWorkingMemory,
        StubLongTermMemory,
        StubDecisionMemory,
        StubUserMemory,
        StubDomainMemory,
    ],
)
def test_stub_search_respects_k_limit(stub_cls: type) -> None:
    store = stub_cls()
    for i in range(10):
        store.write({"index": i})
    results = store.search("query", k=3)
    assert len(results) == 3


@pytest.mark.parametrize(
    "stub_cls",
    [
        StubShortTermMemory,
        StubWorkingMemory,
        StubLongTermMemory,
        StubDecisionMemory,
        StubUserMemory,
        StubDomainMemory,
    ],
)
def test_stub_search_returns_most_recent_records(stub_cls: type) -> None:
    store = stub_cls()
    for i in range(5):
        store.write({"index": i})
    results = store.search("query", k=3)
    # Most recent k=3 means indexes 2, 3, 4
    assert results == [{"index": 2}, {"index": 3}, {"index": 4}]


@pytest.mark.parametrize(
    "stub_cls",
    [
        StubShortTermMemory,
        StubWorkingMemory,
        StubLongTermMemory,
        StubDecisionMemory,
        StubUserMemory,
        StubDomainMemory,
    ],
)
def test_stub_search_k_zero_returns_empty(stub_cls: type) -> None:
    store = stub_cls()
    store.write({"key": "value"})
    results = store.search("query", k=0)
    assert results == []


@pytest.mark.parametrize(
    "stub_cls",
    [
        StubShortTermMemory,
        StubWorkingMemory,
        StubLongTermMemory,
        StubDecisionMemory,
        StubUserMemory,
        StubDomainMemory,
    ],
)
def test_stub_search_default_k_is_five(stub_cls: type) -> None:
    store = stub_cls()
    for i in range(10):
        store.write({"index": i})
    results = store.search("query")
    assert len(results) == 5
