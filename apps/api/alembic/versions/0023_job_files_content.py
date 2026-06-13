"""Add file_content BYTEA column to job_files table.

Revision ID: 0023
Revises: 0022
Create Date: 2026-06-13
"""

from __future__ import annotations

from alembic import op

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE job_files ADD COLUMN IF NOT EXISTS file_content BYTEA NOT NULL DEFAULT ''"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE job_files DROP COLUMN IF EXISTS file_content")
