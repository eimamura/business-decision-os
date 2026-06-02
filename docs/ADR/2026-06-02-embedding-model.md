# ADR: Embedding Model Selection

Date: 2026-06-02

## Status

Accepted

## Context

`packages/memory/__init__.py` contains `_make_embedding()`, which generates
192-dimensional vectors using a SHA-256 hash loop. This violates the AGENTS.md
prohibition on "smart stubs that approximate real behavior":

- The function produces deterministic but semantically meaningless vectors.
- Cosine similarity between two semantically related texts is effectively random.
- `PgVectorMemoryStore.search()` returns results ranked by numerical hash proximity,
  not semantic similarity.
- The dimension mismatch (192 vs the DB column definition of `vector(1536)`)
  causes every `INSERT` to silently store a truncated or padded vector depending
  on pgvector coercion behaviour.

The DB column `memories.embedding` is already defined as `vector(1536)` in
migration `0001_initial.py`. No schema change is required — the mismatch is
entirely in the Python embedding function.

The `MemoryStore` Protocol public interface (`write`, `search`, `get`) does not
reference the embedding dimension. Switching to a real API does not require a
Protocol signature change.

## Decision

Replace `_make_embedding()` with `_get_embedding(text: str) -> list[float]` that
calls the OpenAI Embeddings API using model `text-embedding-3-small`.

### Model selection

| Candidate | Dimensions | Cost (per 1M tokens) | Notes |
|---|---|---|---|
| `text-embedding-3-small` | 1536 | $0.02 | Matches existing DB column; lowest cost |
| `text-embedding-3-large` | 3072 | $0.13 | Higher quality; requires schema change |
| `text-embedding-ada-002` | 1536 | $0.10 | Legacy; superseded by v3 models |
| Anthropic (no embedding API) | — | — | Anthropic does not expose a public embedding endpoint |

`text-embedding-3-small` is selected because:

1. Its output dimension (1536) exactly matches the existing `vector(1536)` column —
   no schema migration is required.
2. It is the lowest-cost OpenAI embedding model.
3. Quality is sufficient for memory retrieval (semantic similarity ranking).

### Interface impact

The `MemoryStore` Protocol signatures are unchanged:

```python
async def write(self, memory: Memory) -> UUID: ...
async def search(self, query: MemoryQuery) -> list[tuple[Memory, float]]: ...
async def get(self, id: UUID) -> Memory | None: ...
```

`PgVectorMemoryStore` calls `_get_embedding()` internally. The embedding is an
implementation detail, not a protocol contract.

### API key requirement

`OPENAI_API_KEY` is required at runtime. Per Python rules and security rules,
a missing env var raises `RuntimeError` at the call site — no silent fallback.

### StubMemoryStore

`StubMemoryStore` does not embed and returns empty search results. This is
acceptable for dev/test environments where `OPENAI_API_KEY` is not present.
It is not a "smart stub" — it makes no attempt to approximate semantic search.

### Alembic migration

A migration `0010_memories_vector_1536.py` is created to document the intent
explicitly and provide a clear upgrade path. Because the column is already
`vector(1536)` from migration `0001`, the `upgrade()` body is a no-op. The
`downgrade()` body is also a no-op since the column definition does not change.

The migration exists as a named checkpoint in the revision chain to record that
the embedding dimension is intentionally 1536 and corresponds to
`text-embedding-3-small`.

## Consequences

- Every `PgVectorMemoryStore.write()` and `PgVectorMemoryStore.search()` call
  makes one synchronous-async HTTP request to `api.openai.com`. Latency is
  typically 50–200 ms per call.
- Tests that use `PgVectorMemoryStore` must either mock the OpenAI client or run
  against a real API key (integration tests).
- Unit tests continue to use `StubMemoryStore` and require no API key.
- If `OPENAI_API_KEY` is absent and `PgVectorMemoryStore` is used, the service
  raises `RuntimeError` on the first embedding call — fail-fast behaviour.

## Reversal Cost

Low. Delete `_get_embedding()`, restore `_make_embedding()` (or any alternative
embedding implementation), update `PgVectorMemoryStore` to call it. No DB schema
change required.
