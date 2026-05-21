# ADR-0004: PostgreSQL 16 + pgvector as Single Data Store

**Date:** 2026-05-17  
**Status:** Accepted  
**Deciders:** Engineering Team

## Context

The system needs to persist: relational session/agent/audit data with strong FK consistency, vector embeddings for the memory store (1536-dimensional), and operational domain tables (SKU, inventory, demand, supply, cost). Using separate stores for each concern (e.g., a dedicated vector DB alongside a relational DB) introduces distributed transaction complexity and operational overhead.

## Decision

Use a **single PostgreSQL 16 instance** with the **pgvector** extension for all transactional data. The `memories` table stores `vector(1536)` embeddings with an `ivfflat` cosine index. All other tables use standard relational PostgreSQL. Analytics data is separated to Databricks (Phase 8+).

## Rationale

- **Transactional consistency:** All FK relationships (sessions → agent_steps → tool_calls → audit_log → llm_usage) are enforced by the database. A single transaction boundary per Orchestrator step prevents partial writes.
- **pgvector sufficiency for MVP scale:** The MVP memory store is write-only in Phase 1; retrieval (Phase 7+) uses pgvector cosine similarity. The scale ceiling is acceptable for MVP and early phases.
- **Operational simplicity:** One database means one connection pool, one schema migration path (Alembic), one backup policy, and one security perimeter.
- **audit_log hash chain:** Tamper-evidence via `audit_hash` / `prev_audit_hash` requires same-transaction writes for the chain to be reliable. A single store makes this natural.
- **Repository pattern:** `packages/state/` wraps all DB access. Swapping the underlying store in Phase 9+ (e.g., Citus, Cosmos PG) requires only a new repository implementation, not call-site changes.

## Trade-offs

- **Single scale ceiling:** A single PostgreSQL instance will eventually hit throughput limits under high concurrent write pressure. Mitigated by the repository swap-in pattern; Phase 9+ triggers are documented in DESIGN.md.
- **Polyglot persistence forgone:** A dedicated vector DB (Qdrant, Azure AI Search) would offer better ANN performance at large memory scale. Deferred to Phase 9+ when pgvector latency degrades measurably.
- **No read replicas for MVP:** All reads and writes go to the same instance. Acceptable for MVP; read replicas or connection pooling (PgBouncer) can be added transparently behind the repository layer.

## Consequences

- Migration 0001 covers all Phase 0–9 schema fields. No additive migrations are permitted for new features; the schema is final-form from Day 1.
- ORM: SQLAlchemy 2.x async + Alembic. Driver: asyncpg with connection pool.
- `memories.embedding` is `vector(1536)` with `ivfflat` cosine index; retrieval returns `[]` in Phase 1 (write-only stub).
- DB-level `CHECK` constraints enforce all status enums; ORM mirrors them.
- TLS (`sslmode=require`) enforced on all connections. DB firewall restricted to GitHub Actions OIDC ranges + developer IPs.
- Analytics data path to Databricks is planned but not implemented until Phase 8+. The production agent never queries Databricks directly.
