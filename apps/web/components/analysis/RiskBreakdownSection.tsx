"use client";

import type { RiskGroup, RiskLevel } from "@/types/analysis";

interface RiskBreakdownSectionProps {
  riskGroups: RiskGroup[];
}

const LEVEL_STYLES: Record<RiskLevel, { wrapper: string; header: string; badge: string }> = {
  Critical: {
    wrapper: "border-red-500/30",
    header: "bg-red-500/10",
    badge: "bg-red-500/20 text-red-400",
  },
  High: {
    wrapper: "border-orange-500/30",
    header: "bg-orange-500/10",
    badge: "bg-orange-500/20 text-orange-400",
  },
  Medium: {
    wrapper: "border-amber-500/30",
    header: "bg-amber-500/10",
    badge: "bg-amber-500/20 text-amber-400",
  },
  Low: {
    wrapper: "border-white/10",
    header: "bg-white/5",
    badge: "bg-white/10 text-white/50",
  },
};

export default function RiskBreakdownSection({ riskGroups }: RiskBreakdownSectionProps): React.ReactElement {
  return (
    <div>
      {riskGroups.map((group, i) => {
        const styles = LEVEL_STYLES[group.level];
        return (
          <div
            key={i}
            className={`rounded-xl border overflow-hidden mb-3 last:mb-0 ${styles.wrapper}`}
          >
            {/* Header row */}
            <div className={`flex items-center justify-between px-4 py-2.5 ${styles.header}`}>
              <div className="flex items-center gap-2">
                <span className={`text-[10px] font-bold uppercase px-1.5 py-0.5 rounded ${styles.badge}`}>
                  {group.level}
                </span>
                <span className="text-sm font-semibold text-white/80">{group.level} Risk</span>
              </div>
              <span className="text-xs text-white/40 italic">{group.description}</span>
            </div>

            {/* SKU rows */}
            <div className="divide-y divide-white/5">
              {group.items.map((item, j) => (
                <div
                  key={j}
                  className="flex items-center gap-3 px-4 py-2 text-xs"
                >
                  <span className="font-mono font-semibold text-white/80 w-16 shrink-0">{item.sku}</span>
                  <span className="text-white/40 w-28 shrink-0">{item.location}</span>
                  <span className="text-white/55 w-16 shrink-0 tabular-nums">{item.daysOfSupply}</span>
                  <span className="text-white/40 truncate flex-1">{item.driver}</span>
                </div>
              ))}
            </div>

            {/* Footer actions */}
            {group.actions && (
              <div className="px-4 py-2 border-t border-white/5">
                <p className="text-xs text-white/35 italic">{group.actions}</p>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
