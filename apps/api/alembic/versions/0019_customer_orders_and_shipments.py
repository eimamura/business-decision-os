"""Add customer_orders and shipments tables (order-to-ship domain P87).

Revision ID: 0019
Revises: 0018
Create Date: 2026-06-11
"""

from __future__ import annotations

from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE customer_orders (
            order_id              TEXT PRIMARY KEY,
            customer_id           TEXT NOT NULL REFERENCES customer_master(customer_id),
            sku_id                TEXT NOT NULL REFERENCES sku_master(sku_id),
            ship_from_location_id TEXT NOT NULL REFERENCES location_master(location_id),
            region                TEXT NOT NULL,
            quantity              INTEGER NOT NULL CHECK (quantity > 0),
            order_date            DATE NOT NULL,
            requested_ship_date   DATE NOT NULL,
            status                TEXT NOT NULL CHECK (status IN ('open', 'allocated', 'shipped', 'cancelled')),
            created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    op.execute("CREATE INDEX ON customer_orders (customer_id)")
    op.execute("CREATE INDEX ON customer_orders (sku_id)")
    op.execute("CREATE INDEX ON customer_orders (status)")
    op.execute("CREATE INDEX ON customer_orders (requested_ship_date)")

    op.execute("""
        CREATE TABLE shipments (
            shipment_id           TEXT PRIMARY KEY,
            order_id              TEXT NOT NULL REFERENCES customer_orders(order_id),
            carrier               TEXT NOT NULL,
            planned_ship_date     DATE NOT NULL,
            actual_ship_date      DATE,
            planned_delivery_date DATE NOT NULL,
            actual_delivery_date  DATE,
            status                TEXT NOT NULL CHECK (status IN ('pending', 'in_transit', 'delivered')),
            created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    op.execute("CREATE INDEX ON shipments (order_id)")
    op.execute("CREATE INDEX ON shipments (status)")
    op.execute("CREATE INDEX ON shipments (planned_ship_date)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS shipments CASCADE")
    op.execute("DROP TABLE IF EXISTS customer_orders CASCADE")
