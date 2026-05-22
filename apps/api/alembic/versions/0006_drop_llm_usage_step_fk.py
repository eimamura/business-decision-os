"""Drop foreign key from llm_usage.agent_step_id to agent_steps.

Revision ID: 0006_drop_llm_usage_step_fk
Revises: 0005_sessions_user_id_nullable
Create Date: 2026-05-22
"""

from __future__ import annotations

from alembic import op

revision = "0006_drop_llm_usage_step_fk"
down_revision = "0005_sessions_user_id_nullable"


def upgrade() -> None:
    op.execute("ALTER TABLE llm_usage DROP CONSTRAINT IF EXISTS llm_usage_agent_step_id_fkey;")


def downgrade() -> None:
    op.execute("""
        ALTER TABLE llm_usage
            ADD CONSTRAINT llm_usage_agent_step_id_fkey
            FOREIGN KEY (agent_step_id) REFERENCES agent_steps(id);
    """)
