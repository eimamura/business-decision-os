"""Add production_capacity and production_plan tables (production domain P89).

Revision ID: 0020
Revises: 0019
Create Date: 2026-06-11
"""

from __future__ import annotations

from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE production_capacity (
            location_id    TEXT    NOT NULL REFERENCES location_master(location_id),
            week_start     DATE    NOT NULL,
            capacity_units INTEGER NOT NULL CHECK (capacity_units >= 0),
            PRIMARY KEY (location_id, week_start)
        );
    """)

    op.execute("CREATE INDEX ON production_capacity (week_start)")

    op.execute("""
        CREATE TABLE production_plan (
            sku_id         TEXT    NOT NULL REFERENCES sku_master(sku_id),
            location_id    TEXT    NOT NULL REFERENCES location_master(location_id),
            week_start     DATE    NOT NULL,
            planned_qty    INTEGER NOT NULL CHECK (planned_qty >= 0),
            PRIMARY KEY (sku_id, location_id, week_start)
        );
    """)

    op.execute("CREATE INDEX ON production_plan (location_id, week_start)")
    op.execute("CREATE INDEX ON production_plan (sku_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS production_plan CASCADE")
    op.execute("DROP TABLE IF EXISTS production_capacity CASCADE")
