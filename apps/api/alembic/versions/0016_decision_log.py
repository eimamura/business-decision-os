"""create decision_log table

Revision ID: 0016
Revises: 0015
Create Date: 2026-06-06
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "decision_log",
        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("record_type", sa.String(32), nullable=False),
        sa.Column("content_json", sa.Text(), nullable=False),
        sa.Column(
            "agent_role",
            sa.String(64),
            nullable=False,
            server_default="control",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_decision_log_session_record_type",
        "decision_log",
        ["session_id", "record_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_decision_log_session_record_type", table_name="decision_log")
    op.drop_table("decision_log")
