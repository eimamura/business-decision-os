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
        title: "SQL Direct Query",
        description: "Run a raw SQL query against the inventory tables",
        prompt: "在庫テーブルから全SKUの現在庫数をSQLで直接取得して",
      },
      {
        id: "catalog",
        title: "Data Catalog Search",
        description: "Browse available tables and datasets in the catalog",
        prompt: "利用可能なデータテーブル一覧をカタログから検索して",
      },
      {
        id: "schema",
        title: "Table Schema Reader",
        description: "Inspect column definitions for a specific table",
        prompt: "inventoryテーブルのスキーマを確認して",
      },
      {
        id: "quality",
        title: "Data Quality Check",
        description: "Run completeness and consistency checks on a table",
        prompt: "inventoryテーブルのデータ品質をチェックして問題があれば報告して",
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
        description: "Forecast demand for a DC over the next month",
        prompt: "来月のDC Westの需要予測をforecastツールで実行して数値を見せて",
      },
      {
        id: "multi-sku",
        title: "Multi-SKU Forecast",
        description: "Forecast all SKUs for the next 3 months",
        prompt: "全SKUの今後3ヶ月の需要予測を実行してCSVで出力して",
      },
      {
        id: "train-model",
        title: "Train Forecast Model",
        description: "Retrain the demand forecast model on latest data",
        prompt: "需要予測モデルを最新データでトレーニングして",
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
        prompt: "現在の発注パラメータで在庫シミュレーションを実行して結果を見せて",
      },
      {
        id: "optimize",
        title: "Replenishment Optimization",
        description: "Calculate optimal replenishment quantities",
        prompt: "発注量の最適化を実行して推奨値を計算して",
      },
      {
        id: "compare",
        title: "Scenario Comparison",
        description: "Compare current vs optimized parameters side-by-side",
        prompt: "現在パラメータと最適化パラメータで2パターンのシミュレーションを比較して",
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
        prompt: "Forecast demand for DC West next quarter",
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
        prompt: "Optimize replenishment for SKU-001 for Q3 2025",
      },
      {
        id: "au-fully-specified",
        title: "Fully Specified (No Question Expected)",
        description:
          "All critical parameters included — agent should skip AskUser and run the analysis directly",
        prompt:
          "Analyze inventory for SKU-001 at DC West for the past 30 days and compare with the previous month",
      },
    ],
  },
  {
    id: "jobs",
    label: "Job Dispatch (HITL)",
    icon: "◎",
    scenarios: [
      {
        id: "job-simulate",
        title: "Run Simulation Job",
        description: "Dispatch a background simulation job — requires approval",
        prompt:
          "Run an inventory simulation for Q3 with current stock levels",
      },
      {
        id: "job-optimize",
        title: "Run Optimization Job",
        description: "Dispatch an optimization job and generate a results report",
        prompt:
          "Optimize replenishment parameters for Q3 and generate a report",
      },
      {
        id: "job-forecast",
        title: "Run Demand Forecast Job",
        description: "Dispatch a forecast job for all SKUs — results saved as file",
        prompt:
          "Run a demand forecast for all SKUs and generate a results file",
      },
    ],
  },
  {
    id: "supply",
    label: "Supply Planning",
    icon: "◧",
    scenarios: [
      {
        id: "supply-gap",
        title: "Supply Gap Analysis",
        description: "Calculate the gap between demand forecast and available supply over 30 days",
        prompt: "SKU-A の供給ギャップを30日間で分析して、不足リスクと補充推奨を教えて",
      },
      {
        id: "lead-time",
        title: "Lead Time Review",
        description: "Analyse supplier lead times and flag high-variance or long-tail suppliers",
        prompt: "サプライヤーのリードタイム分析を実行して、平均・最大・最小リードタイムと遅延リスクを報告して",
      },
      {
        id: "open-orders",
        title: "Open Supply Orders",
        description: "List all pending and in-transit orders with expected arrival dates",
        prompt: "現在オープン状態のすべての供給注文を取得して、到着予定日と数量を一覧で見せて",
      },
      {
        id: "supply-risk",
        title: "Supply Risk Assessment",
        description: "Score supply risk combining gap, lead-time variance, and supplier concentration",
        prompt: "SKU-A の供給リスクを総合評価して、ギャップリスク・リードタイムリスク・集中リスクのスコアを報告して",
      },
    ],
  },
  {
    id: "finance",
    label: "Finance & Cost",
    icon: "⬟",
    scenarios: [
      {
        id: "holding-cost",
        title: "Holding Cost Analysis",
        description: "Calculate monthly and annualised holding cost for excess inventory",
        prompt: "SKU-A の過剰在庫 500 units の保管コストを計算して、月次・年次の金額を教えて",
      },
      {
        id: "stockout-cost",
        title: "Stockout Cost Impact",
        description: "Quantify the opportunity cost of a stockout event for a given SKU",
        prompt: "SKU-A で 200 units の欠品が発生した場合の機会損失コストを計算して",
      },
      {
        id: "expedite-cost",
        title: "Expedite Cost vs Stockout",
        description: "Compare expedite premium against stockout cost to find the break-even",
        prompt: "SKU-A を緊急調達する場合のコストを計算して、欠品放置と比較してどちらが安いか教えて",
      },
      {
        id: "cost-scenarios",
        title: "3-Way Cost Scenario Comparison",
        description: "Compare do-nothing, full-expedite, and partial-fulfill total costs",
        prompt: "SKU-A の不足 300 units に対して、do_nothing・全量緊急調達・部分対応の3シナリオのコストを比較して最適な選択肢を推奨して",
      },
    ],
  },
  {
    id: "sop",
    label: "S&OP",
    icon: "◬",
    scenarios: [
      {
        id: "sop-full",
        title: "Full S&OP Cycle",
        description: "Sequential demand → inventory → supply → finance → SopAgent synthesis",
        prompt: "SKU-A の S&OP 分析を実行して：需要予測 → 在庫状況 → 供給フィージビリティ → 財務影響の順で分析し、最終的な対応方針と次のアクションを推奨して",
      },
      {
        id: "sop-shortage",
        title: "Shortage Decision",
        description: "Compare full-response, partial-response, and do-nothing across cost, risk, and service level",
        prompt: "SKU-A で来月 400 units の不足が予想される。全量対応・部分対応・何もしないの選択肢をコスト・リスク・サービスレベルの観点から比較して、最適な意思決定をして",
      },
      {
        id: "sop-health",
        title: "Inventory Health Check",
        description: "Cross-domain health scan: stockout risk, excess, ATP, and supply gap across SKUs",
        prompt: "主要SKUの在庫健全性をチェックして：欠品リスク・過剰在庫・ATP・供給ギャップを横断的に分析して課題のあるSKUを優先度順にリストアップして",
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
