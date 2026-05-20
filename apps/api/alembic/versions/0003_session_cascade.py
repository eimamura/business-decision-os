"""Add ON DELETE CASCADE to all session_id FKs referencing decision_sessions.

Revision ID: 0003_session_cascade
Revises: 0002_phase10
Create Date: 2026-05-20
"""

from __future__ import annotations

from alembic import op

revision = "0003_session_cascade"
down_revision = "0002_phase10"
branch_labels = None
depends_on = None

_TABLES = [
    "agent_steps",
    "approvals",
    "recommendations",
    "evaluations",
    "forecast_runs",
    "simulation_runs",
    "optimization_runs",
]


def upgrade() -> None:
    for table in _TABLES:
        fkey = f"{table}_session_id_fkey"
        op.execute(
            f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {fkey};"
        )
        op.execute(
            f"""
            ALTER TABLE {table}
            ADD CONSTRAINT {fkey}
            FOREIGN KEY (session_id) REFERENCES decision_sessions(id) ON DELETE CASCADE;
            """
        )


def downgrade() -> None:
    for table in _TABLES:
        fkey = f"{table}_session_id_fkey"
        op.execute(
            f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {fkey};"
        )
        op.execute(
            f"""
            ALTER TABLE {table}
            ADD CONSTRAINT {fkey}
            FOREIGN KEY (session_id) REFERENCES decision_sessions(id);
            """
        )
