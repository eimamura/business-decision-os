"""Add prediction_features table for forecast model output storage.

Revision ID: 0022
Revises: 0021
Create Date: 2026-06-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE prediction_features (
            sku_id        VARCHAR(100) PRIMARY KEY,
            predicted_units REAL[]     NOT NULL,
            model_version VARCHAR(50)  NOT NULL,
            updated_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS prediction_features")
