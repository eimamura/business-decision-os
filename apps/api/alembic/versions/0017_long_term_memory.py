"""create long_term_memory table

Revision ID: 0017
Revises: 0016
Create Date: 2026-06-06
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "long_term_memory",
        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("memory_type", sa.String(32), nullable=False),
        sa.Column(
            "scope",
            sa.String(128),
            nullable=False,
            server_default="",
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "metadata_json",
            sa.Text(),
            nullable=False,
            server_default="{}",
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
        "ix_long_term_memory_type_scope",
        "long_term_memory",
        ["memory_type", "scope"],
    )


def downgrade() -> None:
    op.drop_index("ix_long_term_memory_type_scope", table_name="long_term_memory")
    op.drop_table("long_term_memory")
