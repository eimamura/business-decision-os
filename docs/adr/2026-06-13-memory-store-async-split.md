# ADR: MemoryStore Base Class — Sync Protocol with Async Physical Implementations

**Date:** 2026-06-13
**Status:** Accepted
**Deciders:** Orchestrator (P119 evaluation-driven hardening)

---

## Context

`packages/memory/__init__.py` defines six abstract base classes (`ShortTermMemory`,
`WorkingMemory`, `LongTermMemory`, `DecisionMemory`, `UserMemory`, `DomainMemory`) that
all inherit from `MemoryStore`. Their abstract methods are:

```python
class MemoryStore(ABC):
    @abstractmethod
    def write(self, record: dict[str, Any]) -> None: ...

    @abstractmethod
    def search(self, query: str, k: int = 5) -> list[dict[str, Any]]: ...
```

The six subclasses declared these signatures when the public interface was locked (P41).

The physical implementations (`WorkingMemoryStore`, `DecisionMemoryStore`,
`LongTermMemoryStore`) are **standalone async classes** that do NOT inherit from the
abstract bases. Their actual signatures are:

```python
async def write(self, record: dict[str, Any]) -> None: ...
async def search(self, query: str, k: int = 5) -> list[dict[str, Any]]: ...
```

This creates a structural mismatch: the locked Protocol has sync signatures, all
production implementations are async.

---

## Decision

**Keep the current split.** The abstract base classes retain their sync signatures.
Physical implementations remain standalone async classes.

---

## Rationale

1. **The bases are used only as type documentation.** No production callsite invokes
   `MemoryStore.write()` or `MemoryStore.search()` through the abstract type. The concrete
   classes are instantiated directly. The bases document *what stores exist* and *the
   intended sync contract* for unit-test stubs.

2. **Changing the base signatures is a public interface change** (prohibited without ADR
   per `AGENTS.md §Prohibitions`). Changing to `async def` would require all six abstract
   bases to gain `async` methods, which in turn would require every unit-test stub to
   become `AsyncMock`-based — significant test-churn for no runtime benefit.

3. **The split is load-bearing for the test tier.** `StubMemoryStore` and
   `unittest.mock.MagicMock()` both implement the sync Protocol trivially. Making the
   base async would force all unit tests that use these stores to await them.

4. **The legacy `PgVectorMemoryStore`** (also async) follows the same pattern for the same
   reasons.

---

## Trade-offs

| Kept | Cost |
|---|---|
| Sync abstract bases | Type checker cannot verify that physical stores satisfy the interface |
| Standalone async classes | Instantiation is not polymorphic through `MemoryStore` type |
| No change | The mismatch persists as documented tech debt |

---

## Consequences

- Every new physical `*MemoryStore` class MUST document at its class docstring that it
  does not inherit from the abstract base and is async.
- Unit-test stubs MUST remain sync (they use `StubMemoryStore` or `MagicMock`).
- A future migration to a fully async `Protocol` (using `typing.Protocol` with `async`
  methods) is the correct long-term path but requires an ADR and test-suite update.
- This ADR satisfies the P119 evaluation finding that the mismatch was undocumented.
