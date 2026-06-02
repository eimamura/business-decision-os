"""Record that memories.embedding is vector(1536) for text-embedding-3-small.

Revision ID: 0010
Revises: 0009
Create Date: 2026-06-02

The memories.embedding column was defined as vector(1536) in migration 0001.
This migration is a named checkpoint confirming that the intended dimension is
1536, matching the OpenAI text-embedding-3-small output (see ADR
docs/ADR/2026-06-02-embedding-model.md). No DDL change is required.
"""

from __future__ import annotations

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The column memories.embedding was already created as vector(1536) in
    # migration 0001_initial. No DDL change is required.
    pass


def downgrade() -> None:
    # No DDL was applied in upgrade(); nothing to revert.
    pass
