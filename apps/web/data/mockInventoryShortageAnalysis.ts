import type { InventoryShortageAnalysis } from "@/types/analysis";

export const mockInventoryShortageAnalysis: InventoryShortageAnalysis = {
  title: "Inventory Shortage Risk — Next 4 Weeks",
  status: "Completed",
  duration: "12s",
  confidence: 84,
  confidenceLabel: "High confidence",
  summary:
    "Inventory shortage risk is elevated for selected SKUs over the next 4 weeks, driven by low days of supply, inbound delays, and demand spikes.",
  summaryCards: [
    { label: "Critical SKUs", value: "3", tone: "critical" },
    { label: "High Risk SKUs", value: "3", tone: "high" },
    { label: "Top Driver", value: "Inbound delay", tone: "neutral" },
    { label: "Action Required", value: "This week", tone: "warning" }
  ],
  keyFindings: [
    "SKU-B has only 4 days of supply and inbound is delayed to Week 3.",
    "SKU-A is exposed to demand spike risk with no confirmed replenishment.",
    "SKU-C has limited expected supply inbound over the next 4 weeks.",
    "Promo-driven demand is not fully covered by current stock plan."
  ],
  recommendedActions: [
    {
      action: "Expedite replenishment for SKU-B",
      priority: "Critical",
      reason: "Inbound delayed to Week 3 and only 4 days of supply.",
      owner: "Supply Planning",
      timing: "48–72 hours"
    },
    {
      action: "Allocate SKU-C to priority channels",
      priority: "Critical",
      reason: "Only 40% of expected supply inbound.",
      owner: "Supply Planning",
      timing: "48–72 hours"
    },
    {
      action: "Pull forward replenishment orders by 5–7 days",
      priority: "High",
      owner: "Procurement",
      timing: "This week"
    },
    {
      action: "Validate promo uplift assumptions",
      priority: "High",
      owner: "Demand Planning",
      timing: "This week"
    },
    { action: "Monitor medium-risk SKUs weekly", priority: "Medium" }
  ],
  riskGroups: [
    {
      level: "Critical",
      description: "Act within 48–72 hours",
      items: [
        {
          sku: "SKU-A",
          location: "DC-East",
          daysOfSupply: "6 days",
          driver: "Demand spike (+18%) + no replenishment confirmed"
        },
        {
          sku: "SKU-B",
          location: "Store Cluster 3",
          daysOfSupply: "4 days",
          driver: "Inbound delayed to Week 3"
        },
        {
          sku: "SKU-C",
          location: "DC-West",
          daysOfSupply: "8 days",
          driver: "Only 40% of expected supply inbound"
        }
      ],
      actions:
        "Emergency replenishment or lateral DC transfer. Activate backup supplier for SKU-B."
    },
    {
      level: "High",
      description: "Intervene this week",
      items: [
        {
          sku: "SKU-D",
          location: "DC-Central",
          daysOfSupply: "18 days",
          driver: "Promo in Week 2 not covered in stock plan"
        },
        {
          sku: "SKU-E",
          location: "Store Cluster 1",
          daysOfSupply: "14 days",
          driver: "Accelerating demand trend"
        },
        {
          sku: "SKU-F",
          location: "DC-East",
          daysOfSupply: "16 days",
          driver: "Dual promos + high demand volatility"
        }
      ],
      actions:
        "Pull forward replenishment orders by 5–7 days and build 1.5x safety stock buffer."
    }
  ],
  dataUsed: [
    "Inventory On Hand",
    "Demand Forecast",
    "Sales Orders",
    "Supplier Lead Time"
  ]
};
