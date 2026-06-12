# ADR: Order-to-Ship and Production Data Domains

- Date: 2026-06-11
- Status: Accepted
- Phases: P87 (order-to-ship), P88 (consumes), P89 (production)

## Context

`docs/SPEC.md` defines ten target questions. Q4 (shipment delays / unshipped orders — an MVP
validation question), Q7 (production plan adjustments), Q9 (demand changes by customer or
region), and Q10 (biggest constraint by sales/profit impact) are currently unanswerable because
the data model contains no customer orders, shipments, or production data. `demand_history`
carries only `sku_id, date, quantity` — no customer or region axis.

The SPEC's flagship cross-domain interpretations ("this customer's open order is not blocked by
inventory — it is a shipping slot shortage") require an order-to-ship trail that can be
cross-referenced against inventory, inbound supply, and cost data.

## Decision

Add two additive data domains. No existing table is altered or dropped.

### Order-to-ship domain (P87)

```text
customer_orders
  order_id              text PK            (e.g. "CO-00042"; deterministic seed ids)
  customer_id           text  FK → customer_master.customer_id
  sku_id                text  FK → sku_master.sku_id
  ship_from_location_id text  FK → location_master.location_id
  region                text               (order destination region; denormalized for Q9)
  quantity              integer            (> 0)
  order_date            date
  requested_ship_date   date
  status                text               (open | allocated | shipped | cancelled)

shipments
  shipment_id           text PK
  order_id              text  FK → customer_orders.order_id
  carrier               text
  planned_ship_date     date
  actual_ship_date      date NULL          (NULL = not yet shipped)
  planned_delivery_date date
  actual_delivery_date  date NULL
  status                text               (pending | in_transit | delivered)
```

Shipments carry **facts only — no `delay_reason` column**. Root causes are derived by tools
cross-referencing the order-to-ship trail with `inventory_snapshot` and `supply_orders`
(inventory_shortage / upstream_supply_delay / warehouse_processing_delay / carrier_delay).
Storing a reason code would reduce SPEC Q4 to a lookup and bypass the agent's cross-domain
joining value.

### Customer/region demand axis (P88)

SPEC Q9 is answered from `customer_orders` (order demand by customer and region), **not** by
altering `demand_history`. Rationale: `demand_history` is the consumption series feeding the
forecast/stockout tools and P84's deterministic risk bands; adding axes there would force a
backfill story and risk disturbing settled determinism. Order data is the natural carrier of
customer/region demand signal.

### Production domain (P89)

```text
production_capacity
  location_id    text  FK → location_master.location_id
  week_start     date               (Monday)
  capacity_units integer            (>= 0)
  PK (location_id, week_start)

production_plan
  sku_id         text  FK → sku_master.sku_id
  location_id    text  FK → location_master.location_id
  week_start     date
  planned_qty    integer            (>= 0)
  PK (sku_id, location_id, week_start)
```

Weekly granularity matches the SPEC's planning cadence (`DESIGN.md §Operational Cadence`) and
keeps capacity utilization math deterministic (utilization = Σ planned_qty / capacity_units per
location-week).

### Cross-cutting rules

- Migrations: Alembic, additive only, under `apps/api/alembic/`.
- Both domains join `ALLOWED_READ_TABLES`; schema context flows from `information_schema` via
  `get_schema_context()` — no hand-written schema strings (AGENTS.md prohibition).
- Seed data follows P82 (dates relative to `date.today()`) and P84 (deterministic fixed-index
  scenario assignment, independently verifiable) conventions, and must not disturb the P84
  risk-band determinism of existing tables.
- New tools obey the hybrid output contract (ADR 2026-06-10-tool-output-contract-hybrid):
  domain-dict returns, mandatory `missing_data`, row caps with `truncated`.

## Consequences

- SPEC Q4, Q7, Q9, Q10 become answerable with grounded, seeded, testable scenarios.
- The demo data narrative stays coherent: unshipped orders tie to P84 critical-risk SKUs;
  underproduction ties to the same SKUs where practical.
- `nl_query` SQL surface grows by four read-only tables; the SQL guardrail allowlist is the
  single control point.
- `demand_history` remains the single consumption series; analysts must understand that
  customer/region demand questions are answered from order data (documented in tool
  descriptions and the Control Agent system prompt).
- No public interface (`Tool`, `LLMClient`, `Orchestrator`, …) changes.
