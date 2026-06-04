"""add prompt_messages_json, response_text, tool_calls_json to llm_usage

Revision ID: 0015
Revises: 0014
Create Date: 2026-06-04
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("llm_usage", sa.Column("prompt_messages_json", sa.Text(), nullable=True))
    op.add_column("llm_usage", sa.Column("response_text", sa.Text(), nullable=True))
    op.add_column("llm_usage", sa.Column("tool_calls_json", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("llm_usage", "tool_calls_json")
    op.drop_column("llm_usage", "response_text")
    op.drop_column("llm_usage", "prompt_messages_json")
