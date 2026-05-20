"""Phase 10 tables — session_messages and rate_limit_counters.

Revision ID: 0002_phase10
Revises: 0001
Create Date: 2026-05-20
"""

from __future__ import annotations

from alembic import op

revision = "0002_phase10"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE session_messages (
            id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            session_id    UUID NOT NULL REFERENCES decision_sessions(id) ON DELETE CASCADE,
            role          TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
            content       TEXT NOT NULL,
            feedback      SMALLINT CHECK (feedback IN (-1, 1)),
            input_tokens  INT,
            output_tokens INT,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    op.execute("""
        CREATE INDEX ON session_messages (session_id, created_at);
    """)

    op.execute("""
        CREATE TABLE rate_limit_counters (
            key          TEXT NOT NULL,
            window_start TIMESTAMPTZ NOT NULL,
            count        INT NOT NULL DEFAULT 0,
            PRIMARY KEY (key, window_start)
        );
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS rate_limit_counters CASCADE;")
    op.execute("DROP TABLE IF EXISTS session_messages CASCADE;")
