"""Add context_log table and fix jobs.session_id ON DELETE CASCADE.

Revision ID: 0024
Revises: 0023
Create Date: 2026-06-13

Changes:
  1. Create context_log table for ContextPack observability (P114).
  2. Add ON DELETE CASCADE to jobs.session_id FK (carry-over from FP-016 /
     migration 0003 cascade pass; jobs table was added in 0012 after that pass).
"""

from __future__ import annotations

from alembic import op

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Fix jobs.session_id FK — add ON DELETE CASCADE (FP-016 carry-over)
    # ------------------------------------------------------------------
    op.execute(
        "ALTER TABLE jobs DROP CONSTRAINT IF EXISTS jobs_session_id_fkey;"
    )
    op.execute(
        """
        ALTER TABLE jobs
        ADD CONSTRAINT jobs_session_id_fkey
        FOREIGN KEY (session_id) REFERENCES decision_sessions(id) ON DELETE CASCADE;
        """
    )

    # ------------------------------------------------------------------
    # 2. Create context_log table
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS context_log (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            session_id UUID NOT NULL REFERENCES decision_sessions(id) ON DELETE CASCADE,
            use_case_id VARCHAR(8) NOT NULL,
            intent VARCHAR(64) NOT NULL,
            required_tools JSONB NOT NULL DEFAULT '[]',
            prohibited_tools JSONB NOT NULL DEFAULT '[]',
            context_pack_json JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_context_log_session_id ON context_log(session_id);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_context_log_use_case_id ON context_log(use_case_id);"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_context_log_use_case_id;")
    op.execute("DROP INDEX IF EXISTS idx_context_log_session_id;")
    op.execute("DROP TABLE IF EXISTS context_log;")

    # Restore jobs.session_id FK without CASCADE
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
