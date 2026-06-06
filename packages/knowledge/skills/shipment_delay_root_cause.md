---
skill_name: shipment_delay_root_cause
description: Diagnose the root cause of a shipment or order delay by cross-referencing order status, inventory availability, carrier progress, and inbound supply schedule, then rank candidates by evidence strength.
required_tables: [supply, inventory, sku_master]
required_kpis: [on_time_delivery_rate, order_fill_rate]
---

# Procedure

1. Retrieve the order or shipment record from `supply` using the provided identifier; capture current status, expected delivery date, and actual progress dates.
2. Check inventory availability at the source: query `inventory` for the ordered SKU; if `on_hand < order_quantity`, record a signal supporting `inventory_blocked` as the root cause.
3. Check carrier or shipment progress: if a shipment record exists in `supply` but there has been no status movement for longer than `expected_transit_days`, record a signal supporting `carrier_delayed`.
4. Check slot or dispatch availability: if the order is confirmed but no shipment record has been created, record a signal supporting `slot_constrained` (the order is waiting for a dispatch slot).
5. Check inbound supply: query `supply` for open inbound orders for the source SKU; if source inventory is low due to delayed inbound receipts (expected receipt date < today and status is not received), record a signal supporting `inbound_delayed`.
6. Tally the evidence signals for each candidate root cause; compute confidence — `high` if two or more independent signals agree, `medium` if one strong signal exists, `low` if the signal is present but ambiguous.
7. Rank root cause candidates by evidence strength (number and quality of supporting signals), descending.
8. Return the ranked candidates with supporting evidence, confidence level, and suggested escalation action.

# Output Schema

- root_cause_type: inventory_blocked | carrier_delayed | slot_constrained | inbound_delayed (str)
- supporting_evidence: list of data signals that support this root cause (list[str])
- confidence: high | medium | low (str)
- suggested_escalation: recommended next action for the operator or escalation target (str)
- rank: position among ranked root cause candidates, starting at 1 (int)
