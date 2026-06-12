"""Add screening_runs table for daily screening job audit trail (P93).

Revision ID: 0021
Revises: 0020
Create Date: 2026-06-12
"""

from __future__ import annotations

from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE screening_runs (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            run_date        DATE NOT NULL,
            triggered_by    TEXT NOT NULL CHECK (triggered_by IN ('schedule','startup','manual')),
            status          TEXT NOT NULL CHECK (status IN ('completed','failed')),
            exception_count INT,
            severity_counts JSONB,
            payload         JSONB,
            error           TEXT,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    op.execute("CREATE INDEX ON screening_runs (run_date, created_at DESC)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS screening_runs CASCADE")
