"use client";

import { LayoutGrid } from "lucide-react";

interface Scenario {
  id: string;
  label: string;
  prompt: string;
}

const SCENARIOS: Scenario[] = [
  {
    id: "sql",
    label: "SQL Query",
    prompt: "在庫テーブルから全SKUの現在庫数をSQLで直接取得して",
  },
  {
    id: "forecast",
    label: "Forecast",
    prompt: "来月のDC Westの需要予測をforecastツールで実行して数値を見せて",
  },
  {
    id: "simulate",
    label: "Simulate",
    prompt: "現在の発注パラメータで在庫シミュレーションを実行して結果を見せて",
  },
  {
    id: "optimize",
    label: "Optimize",
    prompt: "発注量の最適化を実行して推奨値を計算して",
  },
  {
    id: "catalog",
    label: "Data Catalog",
    prompt: "利用可能なデータテーブル一覧をカタログから検索して",
  },
];

interface ToolScenarioBarProps {
  onSelect: (prompt: string) => void;
  onOpenModal: () => void;
}

export default function ToolScenarioBar({
  onSelect,
  onOpenModal,
}: ToolScenarioBarProps): React.ReactElement {
  return (
    <div className="flex items-center gap-2 overflow-x-auto px-3 py-2 border-b border-white/5 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
      {/* Expand to modal button */}
      <button
        type="button"
        onClick={onOpenModal}
        title="Browse all tool scenarios"
        className="shrink-0 flex items-center justify-center w-6 h-6 rounded-md bg-white/5 border border-white/10 text-white/35 hover:bg-indigo-500/15 hover:border-indigo-500/30 hover:text-indigo-300 transition-colors"
      >
        <LayoutGrid size={12} />
      </button>
      <span className="shrink-0 text-xs text-white/20 select-none">|</span>
      <span className="shrink-0 text-xs text-white/25 select-none">Demo:</span>
      {SCENARIOS.map((s) => (
        <button
          key={s.id}
          type="button"
          onClick={() => onSelect(s.prompt)}
          className="shrink-0 text-xs px-2.5 py-1 rounded-full bg-white/5 border border-white/10 text-white/50 hover:bg-indigo-500/15 hover:border-indigo-500/30 hover:text-indigo-300 transition-colors"
        >
          {s.label}
        </button>
      ))}
    </div>
  );
}
