---
skill_name: stockout_risk_analysis
description: Identify SKUs at risk of stockout by comparing on-hand inventory against demand forecasts and inbound supply, then classify root cause and rank by business impact.
required_tables: [inventory, demand_history, supply, sku_master]
required_kpis: [days_of_supply, stockout_risk_score, reorder_threshold]
---

# Procedure

1. Query current on-hand inventory per SKU from `inventory` (field: on_hand quantity).
2. Query demand forecast for the next N days (default: 14) from `demand_history` to derive the daily demand rate per SKU.
3. Query open inbound supply orders from `supply` where expected receipt date is in the future and status is not received; capture expected receipt date and incoming quantity per SKU.
4. For each SKU: compute `days_of_supply = on_hand / daily_demand_rate`; use the `days_of_supply` KPI formula from `packages/knowledge/kpi.py`.
5. Flag SKUs with `days_of_supply < reorder_threshold` as at-risk; retrieve `reorder_threshold` from `sku_master`.
6. For each at-risk SKU: classify the root cause using the following logic — `low_stock` if `on_hand < safety_stock`; `inbound_delay` if there are no open supply orders or all open orders have a receipt date past the projected stockout date; `demand_surge` if recent demand (last 7 days) exceeds 1.5x the baseline daily demand rate.
7. Rank at-risk SKUs by business impact: sort descending by `(daily_demand_rate × stockout_cost)` where `stockout_cost` is sourced from `sku_master`.
8. Return the prioritized list with one record per at-risk SKU.

# Output Schema

- sku_id: product identifier (str)
- days_of_supply: computed days of inventory coverage at current demand rate (float)
- root_cause: one of low_stock | inbound_delay | demand_surge (str)
- incoming_supply_date: next expected receipt date from open supply orders, or null if none (str | None)
- risk_rank: position in the business-impact-sorted list, starting at 1 (int)
