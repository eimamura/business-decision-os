"""Rename memories.metadata to memories.metadata_json.

Revision ID: 0004_memories_metadata_rename
Revises: 0003_session_cascade
Create Date: 2026-05-21
"""

from __future__ import annotations

from alembic import op

revision = "0004_memories_metadata_rename"
down_revision = "0003_session_cascade"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE memories RENAME COLUMN metadata TO metadata_json;")


def downgrade() -> None:
    op.execute("ALTER TABLE memories RENAME COLUMN metadata_json TO metadata;")
