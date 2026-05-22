"use client";

import type { RecommendedAction, RiskLevel } from "@/types/analysis";

interface RecommendedActionsPanelProps {
  actions: RecommendedAction[];
}

const PRIORITY_BADGE: Record<RiskLevel, string> = {
  Critical: "bg-red-500/15 text-red-400 border border-red-500/25",
  High: "bg-orange-500/15 text-orange-400 border border-orange-500/25",
  Medium: "bg-amber-500/15 text-amber-400 border border-amber-500/25",
  Low: "bg-white/10 text-white/40 border border-white/15",
};

export default function RecommendedActionsPanel({ actions }: RecommendedActionsPanelProps): React.ReactElement {
  return (
    <div className="space-y-2">
      {actions.map((action, i) => (
        <div
          key={i}
          className="flex items-start gap-3 p-3 rounded-lg bg-white/3 border border-white/8 hover:bg-white/6 transition-colors"
        >
          {/* Priority badge */}
          <span
            className={`shrink-0 text-[10px] font-bold uppercase px-1.5 py-0.5 rounded mt-0.5 ${PRIORITY_BADGE[action.priority]}`}
          >
            {action.priority}
          </span>

          {/* Content */}
          <div className="flex-1 min-w-0">
            <p className="text-sm text-white/80">{action.action}</p>
            {(action.reason ?? action.owner ?? action.timing) && (
              <p className="text-[11px] text-white/35 mt-0.5 leading-snug">
                {[action.reason, action.owner && `Owner: ${action.owner}`, action.timing && `By: ${action.timing}`]
                  .filter(Boolean)
                  .join(" · ")}
              </p>
            )}
          </div>

          {/* Link-style button */}
          <button className="shrink-0 text-[11px] text-indigo-400/70 hover:text-indigo-300 transition-colors whitespace-nowrap mt-0.5">
            View action plan →
          </button>
        </div>
      ))}
    </div>
  );
}
