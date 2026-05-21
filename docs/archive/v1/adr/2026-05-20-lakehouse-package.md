# ADR: Add packages/lakehouse to Monorepo Layout

**Date:** 2026-05-20
**Status:** Accepted
**Scope:** T-8002–T-8004 (Phase 8 — Databricks Lakehouse)

## Context

DESIGN.md §Monorepo Layout lists `packages/` with 8 specific packages. The §Analytics Data Path
section describes the Databricks Lakehouse (Phase 8+ implementation) as a separate data tier, but
does not list a corresponding Python package.

Phase 8 requires:
- Writing CDC data from PostgreSQL to Bronze Delta tables
- Silver/Gold transformation pipelines
- A CLI for local dev and CI smoke tests (no actual Azure required)

## Decision

Add `packages/lakehouse` as the 9th member of `packages/` in the monorepo. This package:

1. Owns the `LakehouseClient` interface (Bronze read/write, Silver/Gold transformation)
2. Provides a file-based local implementation using newline-delimited JSON (no new Python dependencies)
3. Exposes `python -m packages.lakehouse.cli` for local status checks and dry-run jobs
4. Terraform IaC lives in `infra/terraform/databricks/` (extends existing `infra/terraform/` layout)

The production agent continues to read from PostgreSQL only; `packages/lakehouse` is used by training
jobs and analytics pipelines exclusively.

## Consequences

- `pyproject.toml` gains `packages/lakehouse` as a workspace member
- DESIGN.md §Monorepo Layout is updated to include `packages/lakehouse`
- No new top-level root directories are added
- Local dev does not require Azure or Databricks; CI can test the package with file I/O only
