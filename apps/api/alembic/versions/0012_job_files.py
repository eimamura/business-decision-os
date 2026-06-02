"""add jobs and job_files tables

Revision ID: 0012
Revises: 0011
Create Date: 2026-06-02
"""

from __future__ import annotations

from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            session_id UUID REFERENCES decision_sessions(id),
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            job_type VARCHAR(50) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            completed_at TIMESTAMPTZ NULL
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS job_files (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
            file_name VARCHAR(255) NOT NULL,
            file_size_bytes BIGINT NOT NULL DEFAULT 0,
            mime_type VARCHAR(100) NOT NULL DEFAULT 'application/octet-stream',
            download_url TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_jobs_session_id ON jobs(session_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_job_files_job_id ON job_files(job_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS job_files")
    op.execute("DROP TABLE IF EXISTS jobs")
