"""Make decision_sessions.user_id nullable and drop FK to users.

Revision ID: 0005_sessions_user_id_nullable
Revises: 0004_memories_metadata_rename
Create Date: 2026-05-21
"""

from __future__ import annotations

from alembic import op

revision = "0005_sessions_user_id_nullable"
down_revision = "0004_memories_metadata_rename"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE decision_sessions DROP CONSTRAINT IF EXISTS"
        " decision_sessions_user_id_fkey;"
    )
    op.execute(
        "ALTER TABLE decision_sessions ALTER COLUMN user_id DROP NOT NULL;"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE decision_sessions ALTER COLUMN user_id SET NOT NULL;"
    )
    op.execute("""
        ALTER TABLE decision_sessions
        ADD CONSTRAINT decision_sessions_user_id_fkey
        FOREIGN KEY (user_id) REFERENCES users(id);
    """)
