"""add outcome column to decision_log

Revision ID: 0018
Revises: 0017
Create Date: 2026-06-10
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "decision_log",
        sa.Column("outcome", sa.SmallInteger(), nullable=True),
    )
    op.create_check_constraint(
        "ck_decision_log_outcome",
        "decision_log",
        "outcome IN (1, -1)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_decision_log_outcome", "decision_log", type_="check")
    op.drop_column("decision_log", "outcome")
