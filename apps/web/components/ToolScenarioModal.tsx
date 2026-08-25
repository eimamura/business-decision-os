"use client";

import { useState, useEffect, useCallback } from "react";
import { X } from "lucide-react";

interface Scenario {
  id: string;
  title: string;
  description: string;
  prompt: string;
}

interface Category {
  id: string;
  label: string;
  icon: string;
  scenarios: Scenario[];
}

const CATEGORIES: Category[] = [
  {
    id: "data",
    label: "Data Query",
    icon: "⬡",
    scenarios: [
      {
        id: "sql",
        title: "Natural Language Query",
        description:
          "Query inventory data using natural language — the agent converts it to SQL via nl_query",
        prompt:
          "Show me the current inventory levels for all SKUs using a natural language query",
      },
      {
        id: "catalog",
        title: "Data Catalog Search",
        description: "Browse available tables and datasets in the catalog",
        prompt: "Search the data catalog for all available tables and datasets",
      },
      {
        id: "schema",
        title: "Table Schema Reader",
        description: "Inspect column definitions for a specific table",
        prompt: "Show me the schema for the inventory_snapshot table",
      },
      {
        id: "quality",
        title: "Data Quality Check",
        description: "Run completeness and consistency checks on a table",
        prompt:
          "Run a data quality check on the inventory_snapshot table and report any issues",
      },
    ],
  },
  {
    id: "forecast",
    label: "Forecasting",
    icon: "◈",
    scenarios: [
      {
        id: "demand-forecast",
        title: "Demand Forecast",
        description: "Forecast demand for a specific SKU over the next 30 days",
        prompt: "Forecast demand for SKU-001 over the next 30 days",
      },
      {
        id: "multi-sku",
        title: "Multi-SKU Forecast",
        description:
          "Forecast demand for a set of SKUs and summarize results in chat",
        prompt:
          "Forecast demand for SKU-001, SKU-002, and SKU-003 over the next 30 days and summarize the results",
      },
    ],
  },
  {
    id: "simulation",
    label: "Simulation & Optimization",
    icon: "⬖",
    scenarios: [
      {
        id: "simulate",
        title: "Inventory Simulation",
        description: "Simulate inventory levels with current order parameters",
        prompt:
          "Run an inventory simulation with the current order parameters and show the results",
      },
      {
        id: "optimize",
        title: "Replenishment Optimization",
        description: "Calculate optimal replenishment quantities",
        prompt:
          "Run replenishment optimization and calculate the recommended order quantities",
      },
      {
        id: "compare",
        title: "Scenario Comparison",
        description: "Compare current vs optimized parameters side-by-side",
        prompt:
          "Run two simulations — current parameters vs optimized parameters — and compare the results side by side",
      },
    ],
  },
  {
    id: "job-dispatch",
    label: "Job Dispatch",
    icon: "⬗",
    scenarios: [
      {
        id: "jd-train-forecast",
        title: "Train Forecast Model",
        description: "Submit a forecast model training job — runs in the background and notifies you in chat on completion",
        prompt: "Train the demand forecast model for SKU-001 as a background job and notify me in chat when it completes.",
      },
      {
        id: "jd-inventory-simulation",
        title: "Full Inventory Simulation",
        description: "Run a full inventory simulation for all SKUs — background execution with a completion report",
        prompt: "Run a full inventory simulation for all SKUs as a background job and notify me in chat when the results are ready.",
      },
      {
        id: "jd-supply-analysis",
        title: "Batch Supply Chain Analysis",
        description: "Kick off a comprehensive supply gap analysis across the entire SKU catalog",
        prompt: "Run a comprehensive supply chain analysis for the entire SKU catalog as a background job. Notify me in chat when it is complete.",
      },
    ],
  },
  {
    id: "charts",
    label: "Charts",
    icon: "◈",
    scenarios: [
      {
        id: "chart-stockout-risk",
        title: "Stockout Risk Chart",
        description:
          "List all SKUs at risk of stockout with days-of-cover values — renders an inline bar chart",
        prompt:
          "List all SKUs at risk of stockout. For each SKU show the days of cover remaining and the risk level. I need the full list sorted by urgency.",
      },
      {
        id: "chart-demand-trend",
        title: "Demand Trend Chart",
        description:
          "Analyze the demand trend direction and period-over-period changes for SKU-001 — renders an inline line chart",
        prompt:
          "Analyze the demand trend for SKU-001. Show me the trend direction, slope, and period-over-period demand quantities so I can see how demand is changing over time.",
      },
    ],
  },
  {
    id: "ask-user",
    label: "Ask User (HITL)",
    icon: "◑",
    scenarios: [
      {
        id: "au-vague-inventory",
        title: "Vague Inventory Request",
        description:
          "Maximally underspecified — agent will ask for SKU, period, and location before proceeding",
        prompt: "Analyze inventory",
      },
      {
        id: "au-forecast-no-target",
        title: "Forecast Without Target",
        description:
          "Intent is clear but product and horizon are both missing — expect the agent to ask what to forecast",
        prompt: "Run a demand forecast",
      },
      {
        id: "au-warehouse-given",
        title: "Warehouse Specified, SKU Missing",
        description:
          "Location is provided but the target product is absent — one focused question expected",
        prompt: "Forecast demand for WH-001 next quarter",
      },
      {
        id: "au-sku-no-period",
        title: "SKU Known, Period Missing",
        description:
          "Product is identified but the analysis window is open — agent likely asks for a date range",
        prompt: "Check stockout risk for SKU-001",
      },
      {
        id: "au-mostly-specified",
        title: "Mostly Specified",
        description:
          "SKU and quarter are provided — agent may proceed or ask for a service-level threshold",
        prompt: "Optimize replenishment for SKU-001 for next quarter",
      },
      {
        id: "au-fully-specified",
        title: "Fully Specified (No Question Expected)",
        description:
          "All critical parameters included — agent should skip AskUser and run the analysis directly",
        prompt:
          "Analyze inventory for SKU-001 at WH-001 for the past 30 days and compare with the previous month",
      },
    ],
  },
  {
    id: "supply-chain",
    label: "Supply Chain",
    icon: "◉",
    scenarios: [
      {
        id: "sc-exceptions",
        title: "Today's Exceptions",
        description:
          "Identify and prioritize operational exceptions requiring immediate attention",
        prompt: "What are today's exceptions?",
      },
      {
        id: "sc-daily-exception-review",
        title: "Daily Exception Review",
        description:
          "Aggregate all stockout risk, delayed supply orders, demand anomalies, and data quality issues into one prioritized list for daily review",
        prompt:
          "What exceptions require human judgment today? Give me a severity-ranked list covering stockout risk, delayed supply orders, demand anomalies, and data quality issues.",
      },
      {
        id: "sc-stockout-risk",
        title: "Stockout Risk This Week",
        description:
          "Assess stockout risk across inventory and supply signals",
        prompt: "Which products are at stockout risk this week?",
      },
      {
        id: "sc-order-delay",
        title: "Supply Order Delays",
        description:
          "Identify delayed supply orders for a specific SKU and analyze risk",
        prompt:
          "Are there any delayed supply orders for SKU-001? Analyze the supply risk.",
      },
      {
        id: "sc-shipment-delay-causes",
        title: "Shipment Delay Root Causes",
        description:
          "Cross-reference orders, shipments, inventory, and supply to classify root causes of shipment delays and unshipped orders",
        prompt:
          "What is causing shipment delays or unshipped orders? Classify each delayed order by root cause.",
      },
      {
        id: "sc-biggest-constraint-impact",
        title: "Biggest Constraint Impact",
        description:
          "Identify the binding constraint with the largest negative impact on sales or profit using capacity and demand data",
        prompt:
          "Which constraint is having the biggest negative impact on sales or profit right now?",
      },
      {
        id: "sc-production-plan-adjustments",
        title: "Production Plan Adjustments",
        description:
          "Identify products requiring production plan adjustments over the next four weeks using capacity and demand gap analysis",
        prompt:
          "Which products require production plan adjustments over the next four weeks?",
      },
      {
        id: "sc-demand-shift",
        title: "Customer & Region Demand Shifts",
        description:
          "Detect demand changes by customer or region this month using demand shift analysis",
        prompt: "Are there demand changes by customer or region this month?",
      },
      {
        id: "sc-forecast-vs-actual",
        title: "Forecast vs Actual Gap",
        description:
          "Decompose the gap between the demand forecast and actual demand by SKU and ISO week",
        prompt:
          "Why is there a gap between the demand forecast and actual demand over the last four weeks?",
      },
      {
        id: "sc-purchase-timing",
        title: "Purchase Timing Adjustments",
        description:
          "Identify open supply orders that should be pulled forward (arriving too late) or pushed out (arriving too early) relative to projected stockout dates",
        prompt:
          "Which supply orders should be purchased earlier or later? Identify pull-forward and push-out candidates.",
      },
    ],
  },
];

interface ToolScenarioModalProps {
  open: boolean;
  onClose: () => void;
  onApply: (prompt: string) => void;
}

export default function ToolScenarioModal({
  open,
  onClose,
  onApply,
}: ToolScenarioModalProps): React.JSX.Element | null {
  const [activeCategoryId, setActiveCategoryId] = useState(CATEGORIES[0].id);

  const handleKey = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    },
    [onClose],
  );

  useEffect(() => {
    if (open) {
      document.addEventListener("keydown", handleKey);
      return () => document.removeEventListener("keydown", handleKey);
    }
  }, [open, handleKey]);

  if (!open) return null;

  const activeCategory =
    CATEGORIES.find((c) => c.id === activeCategoryId) ?? CATEGORIES[0];

  function handleApply(prompt: string): void {
    onApply(prompt);
    onClose();
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-label="Tool Scenario Selector"
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal panel */}
      <div className="relative z-10 w-full max-w-2xl rounded-2xl border border-white/10 bg-[#0e1120] shadow-2xl flex flex-col overflow-hidden max-h-[80vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-white/8">
          <div>
            <h2 className="text-sm font-semibold text-white/90">Tool Scenarios</h2>
            <p className="text-xs text-white/35 mt-0.5">
              Select a scenario to set and send the prompt
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-white/30 hover:text-white/70 hover:bg-white/6 transition-colors"
            aria-label="Close"
          >
            <X size={16} />
          </button>
        </div>

        {/* Body */}
        <div className="flex flex-1 overflow-hidden">
          {/* Category sidebar */}
          <nav className="w-44 shrink-0 border-r border-white/8 py-3 flex flex-col gap-0.5 overflow-y-auto">
            {CATEGORIES.map((cat) => (
              <button
                key={cat.id}
                onClick={() => setActiveCategoryId(cat.id)}
                data-testid={
                  cat.id === "job-dispatch"
                    ? "category-job-dispatch"
                    : cat.id === "charts"
                      ? "category-charts"
                      : undefined
                }
                className={`w-full text-left px-4 py-2.5 flex items-center gap-2.5 text-sm transition-colors ${
                  activeCategoryId === cat.id
                    ? "bg-indigo-500/15 text-indigo-300 border-r-2 border-indigo-500"
                    : "text-white/45 hover:text-white/75 hover:bg-white/4"
                }`}
              >
                <span className="text-base leading-none">{cat.icon}</span>
                <span className="font-medium">{cat.label}</span>
              </button>
            ))}
          </nav>

          {/* Scenario cards */}
          <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-3">
            {activeCategory.scenarios.map((s) => (
              <button
                key={s.id}
                onClick={() => handleApply(s.prompt)}
                data-testid={activeCategory.id === "job-dispatch" ? `scenario-job-dispatch-${s.id}` : undefined}
                className="group w-full text-left rounded-xl border border-white/8 bg-white/[0.03] hover:bg-indigo-500/10 hover:border-indigo-500/30 px-4 py-3 transition-all"
              >
                <p className="text-sm font-semibold text-white/85 group-hover:text-indigo-200 mb-1">
                  {s.title}
                </p>
                <p className="text-xs text-white/40 leading-relaxed mb-2">
                  {s.description}
                </p>
                <p className="text-xs font-mono text-white/25 group-hover:text-indigo-300/50 truncate">
                  {s.prompt}
                </p>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
