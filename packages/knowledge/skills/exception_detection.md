---
skill_name: exception_detection
description: Scan inventory, supply orders, shipments, and demand forecasts for anomalies exceeding thresholds, rank by business impact, and return a prioritized exception list with root cause candidates.
required_tables: [inventory_snapshot, supply_orders, demand_history, sku_master]
required_kpis: [days_of_supply, order_fill_rate, on_time_delivery_rate]
---

# Procedure

1. Scan `inventory_snapshot` for SKUs where `days_of_supply < 7` (critical threshold); compute `days_of_supply` using the KPI formula from `packages/knowledge/kpi.py`.
2. Scan `supply_orders` for overdue orders where `expected_arrival < today` and `status != 'delivered'`; each overdue order is a candidate exception.
3. Scan `supply_orders` for orders where `expected_arrival < today - 7` and status is `in_transit`; each qualifies as a delayed-in-transit exception.
4. Scan `demand_history` for demand spikes where the forecast quantity for any SKU in the next 7 days exceeds 1.5x that SKU's rolling 7-day average; each spike is a candidate exception.
5. For each candidate exception: assign severity — `critical` if business impact is severe and immediate action is required; `warning` if the situation is developing and action is advisable within 24 hours; `watch` if the anomaly is notable but not yet urgent.
6. Compute business impact for each exception as `revenue_at_risk × severity_weight`, where severity weights are: `critical = 3`, `warning = 2`, `watch = 1`; source revenue data from `sku_master` and `supply_orders`.
7. Sort all exceptions descending by business impact and return the top N (default N=10).
8. For each returned exception, include type, entity identifier, severity, root cause candidates, and a recommended immediate action.

# Output Schema

- exception_type: category of the exception such as low_inventory | overdue_order | delayed_shipment | demand_spike (str)
- entity_id: SKU identifier, order identifier, or shipment identifier depending on exception_type (str)
- severity: critical | warning | watch (str)
- root_cause_candidates: list of candidate root causes in descending likelihood order (list[str])
- recommended_action: suggested immediate action the operator should take (str)
- rank: position in the business-impact-sorted exception list, starting at 1 (int)
