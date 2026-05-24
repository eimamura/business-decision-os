"""Rename operational tables and add location_master and forecast_history.

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-24

customers        → customer_master
inventory        → inventory_snapshot
supply           → supply_orders
cost             → cost_master
+ location_master  (new)
+ forecast_history (new)
"""

from __future__ import annotations

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE customers RENAME TO customer_master")
    op.execute("ALTER TABLE inventory RENAME TO inventory_snapshot")
    op.execute("ALTER TABLE supply RENAME TO supply_orders")
    op.execute("ALTER TABLE cost RENAME TO cost_master")

    op.execute("""
        CREATE TABLE location_master (
            id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            location_id                 TEXT NOT NULL UNIQUE,
            name                        TEXT NOT NULL,
            region                      TEXT NOT NULL,
            country                     TEXT NOT NULL DEFAULT 'JP',
            location_type               TEXT NOT NULL CHECK (location_type IN ('warehouse','distribution_center','store')),
            capacity_units              NUMERIC NOT NULL,
            handling_cost_per_unit      NUMERIC NOT NULL,
            lead_time_to_customer_days  INT NOT NULL,
            created_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    op.execute("""
        CREATE TABLE forecast_history (
            id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            sku_id         TEXT NOT NULL REFERENCES sku_master(sku_id),
            forecast_date  DATE NOT NULL,
            target_date    DATE NOT NULL,
            forecast_qty   NUMERIC NOT NULL,
            model_version  TEXT NOT NULL,
            created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    op.execute("CREATE INDEX ON forecast_history (sku_id, target_date)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS forecast_history CASCADE")
    op.execute("DROP TABLE IF EXISTS location_master CASCADE")
    op.execute("ALTER TABLE cost_master RENAME TO cost")
    op.execute("ALTER TABLE supply_orders RENAME TO supply")
    op.execute("ALTER TABLE inventory_snapshot RENAME TO inventory")
    op.execute("ALTER TABLE customer_master RENAME TO customers")
