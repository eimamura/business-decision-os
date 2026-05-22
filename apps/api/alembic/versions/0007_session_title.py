"""Add title column to decision_sessions.

Revision ID: 0007_session_title
Revises: 0006_drop_llm_usage_step_fk
Create Date: 2026-05-22
"""

from __future__ import annotations

from alembic import op

revision = "0007_session_title"
down_revision = "0006_drop_llm_usage_step_fk"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE decision_sessions ADD COLUMN IF NOT EXISTS title TEXT;")


def downgrade() -> None:
    op.execute("ALTER TABLE decision_sessions DROP COLUMN IF EXISTS title;")
