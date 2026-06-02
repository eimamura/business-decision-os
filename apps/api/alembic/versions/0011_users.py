"""add users table

Revision ID: 0011
Revises: 0010
Create Date: 2026-06-02
"""

from __future__ import annotations

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # If a users table already exists with id UUID (wrong schema), drop and recreate.
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'users'
                  AND column_name = 'id'
                  AND data_type = 'uuid'
            ) THEN
                DROP TABLE users CASCADE;
            END IF;
        END;
        $$;
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            role TEXT NOT NULL CHECK (role IN ('analyst', 'manager', 'admin')),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute(
        "INSERT INTO users (id, role) VALUES ('dev-user', 'analyst') ON CONFLICT (id) DO NOTHING"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS users")
