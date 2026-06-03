"""add awaiting_input to decision_sessions status check constraint

Revision ID: 0014
Revises: 0013
Create Date: 2026-06-03
"""

from __future__ import annotations

from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE decision_sessions DROP CONSTRAINT IF EXISTS decision_sessions_status_check")
    op.execute("""
        ALTER TABLE decision_sessions
        ADD CONSTRAINT decision_sessions_status_check
        CHECK (status IN ('pending', 'running', 'completed', 'failed', 'awaiting_input'))
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE decision_sessions DROP CONSTRAINT IF EXISTS decision_sessions_status_check")
    op.execute("""
        ALTER TABLE decision_sessions
        ADD CONSTRAINT decision_sessions_status_check
        CHECK (status IN ('pending', 'running', 'completed', 'failed'))
    """)
