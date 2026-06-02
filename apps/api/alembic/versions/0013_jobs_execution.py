"""extend jobs table with execution columns

Revision ID: 0013
Revises: 0012
Create Date: 2026-06-02
"""

from __future__ import annotations

from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS params_json JSONB")
    op.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS result_json JSONB")
    op.execute("""
        ALTER TABLE jobs
        ADD COLUMN IF NOT EXISTS approval_id UUID REFERENCES approvals(id)
    """)
    op.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS error TEXT")
    op.execute("""
        ALTER TABLE jobs
        ADD COLUMN IF NOT EXISTS input_tokens INT NOT NULL DEFAULT 0
    """)
    op.execute("""
        ALTER TABLE jobs
        ADD COLUMN IF NOT EXISTS output_tokens INT NOT NULL DEFAULT 0
    """)
    op.execute("""
        ALTER TABLE jobs
        ADD COLUMN IF NOT EXISTS cost_usd NUMERIC(12,6) NOT NULL DEFAULT 0
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_jobs_approval_id ON jobs(approval_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_jobs_approval_id")
    op.execute("ALTER TABLE jobs DROP COLUMN IF EXISTS cost_usd")
    op.execute("ALTER TABLE jobs DROP COLUMN IF EXISTS output_tokens")
    op.execute("ALTER TABLE jobs DROP COLUMN IF EXISTS input_tokens")
    op.execute("ALTER TABLE jobs DROP COLUMN IF EXISTS error")
    op.execute("ALTER TABLE jobs DROP COLUMN IF EXISTS approval_id")
    op.execute("ALTER TABLE jobs DROP COLUMN IF EXISTS result_json")
    op.execute("ALTER TABLE jobs DROP COLUMN IF EXISTS params_json")
