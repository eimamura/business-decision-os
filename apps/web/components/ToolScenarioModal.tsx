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
