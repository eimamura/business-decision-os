"""Add session_events table for SSE event persistence.

Revision ID: 0007_session_events
Revises: 0006_drop_llm_usage_step_fk
Create Date: 2026-05-22
"""

from __future__ import annotations

from alembic import op

revision = "0007_session_events"
down_revision = "0006_drop_llm_usage_step_fk"


def upgrade() -> None:
    op.execute("""
        CREATE TABLE session_events (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            session_id  UUID NOT NULL REFERENCES decision_sessions(id) ON DELETE CASCADE,
            event_type  TEXT NOT NULL,
            payload     JSONB NOT NULL DEFAULT '{}',
            event_id    TEXT,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX ON session_events (session_id, created_at)")
    op.execute("CREATE INDEX ON session_events (session_id, event_type)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS session_events CASCADE;")
