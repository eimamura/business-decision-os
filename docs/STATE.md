# STATE.md

Orchestrator execution state. Written only by bdos-orchestrator.

---

## Active Phase

**Phase: Domain Integrity**

Goal: Eliminate AGENTS.md prohibited violations and close the critical design gaps
identified in the 2026-06-02 evaluation. Adopt low-cost patterns from reference
projects that do not require public interface changes.

Tasks: T-001 through T-011 defined in TASKS.md.

## Active Lease

None.

## Blockers

- T-003 (real embeddings) requires an ADR before implementation.
  ADR must decide: embedding model selection, vector dimension, MemoryStore interface impact.
