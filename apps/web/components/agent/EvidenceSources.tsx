"use client";

import type { SseEvent } from "@/types/chat";

const TOOL_LABELS: Record<string, string> = {
  sql_query: "SQL Query",
  nl_query: "Natural Language Query",
  forecast: "Demand Forecast",
  simulate_inventory: "Inventory Simulation",
  optimize_replenishment: "Replenishment Optimizer",
  evaluate_candidates: "Candidate Evaluator",
  write_audit_log: "Audit Log",
};

function toolLabel(name: string): string {
  return TOOL_LABELS[name] ?? name;
}

interface EvidenceSourcesProps {
  events: SseEvent[];
}

export default function EvidenceSources({ events }: EvidenceSourcesProps): React.ReactElement {
  const usedTools: Map<string, string> = new Map();
  for (const ev of events) {
    if (ev.type === "tool_completed" && ev.status !== "error") {
      usedTools.set(ev.tool_name, toolLabel(ev.tool_name));
    }
  }

  if (usedTools.size === 0) return <></>;

  return (
    <div className="border-t border-white/8 px-4 py-3">
      <h3 className="text-[10px] font-bold uppercase tracking-widest text-white/35 mb-2">
        Evidence / Data Sources
      </h3>
      <ul className="space-y-1.5">
        {Array.from(usedTools.entries()).map(([id, label]) => (
          <li key={id} className="flex items-center justify-between gap-2">
            <span className="text-xs text-white/55 truncate">{label}</span>
            <span className="shrink-0 text-[10px] font-semibold text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded">
              Used
            </span>
          </li>
        ))}
      </ul>
      <button className="mt-2 text-[10px] text-indigo-400/70 hover:text-indigo-300 transition-colors">
        View all data sources →
      </button>
    </div>
  );
}
