"use client";

import type { AnalysisSummaryCard } from "@/types/analysis";

interface RiskSummaryCardsProps {
  cards: AnalysisSummaryCard[];
}

const TONE_STYLES: Record<AnalysisSummaryCard["tone"], { wrapper: string; value: string }> = {
  critical: {
    wrapper: "border-red-500/30 bg-red-500/8",
    value: "text-red-400",
  },
  high: {
    wrapper: "border-orange-500/30 bg-orange-500/8",
    value: "text-orange-400",
  },
  warning: {
    wrapper: "border-amber-500/30 bg-amber-500/8",
    value: "text-amber-400",
  },
  neutral: {
    wrapper: "border-indigo-500/30 bg-indigo-500/8",
    value: "text-indigo-300",
  },
  success: {
    wrapper: "border-emerald-500/30 bg-emerald-500/8",
    value: "text-emerald-400",
  },
};

export default function RiskSummaryCards({ cards }: RiskSummaryCardsProps): React.ReactElement {
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
      {cards.map((card, i) => {
        const styles = TONE_STYLES[card.tone];
        return (
          <div
            key={i}
            className={`rounded-xl border px-4 py-3 ${styles.wrapper}`}
          >
            <p className="text-[11px] text-white/50 uppercase tracking-wide mb-1">{card.label}</p>
            <p className={`text-2xl font-bold ${styles.value}`}>{card.value}</p>
          </div>
        );
      })}
    </div>
  );
}
