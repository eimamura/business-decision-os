"""Add ON DELETE CASCADE to jobs.session_id FK (FP-016 residual).

FP-016 root cause: the jobs table was created in migration 0012 after the
cascade pass in migration 0003, so its session_id FK was added without
ON DELETE CASCADE.  Migration 0024 bundled a partial fix alongside the
context_log table; this migration is the standalone, canonical record of
the cascade addition for the jobs table — completing the convention from
0003 for all session-child tables.

Revision ID: 0025
Revises: 0024
Create Date: 2026-06-14
"""

from __future__ import annotations

from alembic import op

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the existing FK (with or without CASCADE — IF EXISTS is safe).
    op.execute(
        "ALTER TABLE jobs DROP CONSTRAINT IF EXISTS jobs_session_id_fkey;"
    )
    # Re-add with ON DELETE CASCADE, completing the convention from 0003.
    op.execute(
        """
        ALTER TABLE jobs
        ADD CONSTRAINT jobs_session_id_fkey
        FOREIGN KEY (session_id) REFERENCES decision_sessions(id) ON DELETE CASCADE;
        """
    )


def downgrade() -> None:
    # Restore the FK without CASCADE (pre-FP-016-fix state).
    op.execute(
        "ALTER TABLE jobs DROP CONSTRAINT IF EXISTS jobs_session_id_fkey;"
    )
    op.execute(
        """
        ALTER TABLE jobs
        ADD CONSTRAINT jobs_session_id_fkey
        FOREIGN KEY (session_id) REFERENCES decision_sessions(id);
        """
    )
