"use client";

import type { SseEvent } from "@/types/chat";

interface DataSource {
  name: string;
  freshness: string;
  status: string;
}

const DEFAULT_SOURCES: readonly DataSource[] = [
  { name: "Inventory On Hand", freshness: "Real-time", status: "Used" },
  { name: "Demand Forecast", freshness: "Next 4 weeks", status: "Used" },
  { name: "Sales Orders", freshness: "Last 90 days", status: "Used" },
  { name: "Supplier Lead Time", freshness: "Latest available", status: "Used" },
] as const;

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

function DatabaseIcon(): React.ReactElement {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 14 14"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className="shrink-0 mt-0.5 text-indigo-400/70"
    >
      <ellipse cx="7" cy="3.5" rx="4.5" ry="1.75" stroke="currentColor" strokeWidth="1" />
      <path
        d="M2.5 3.5v3.5c0 .966 2.015 1.75 4.5 1.75s4.5-.784 4.5-1.75V3.5"
        stroke="currentColor"
        strokeWidth="1"
      />
      <path
        d="M2.5 7v3.5c0 .966 2.015 1.75 4.5 1.75s4.5-.784 4.5-1.75V7"
        stroke="currentColor"
        strokeWidth="1"
      />
    </svg>
  );
}

function SourceRow({ name, freshness, status }: DataSource): React.ReactElement {
  return (
    <li className="flex items-start gap-3 py-2.5 border-b border-white/[0.06] last:border-0">
      <DatabaseIcon />
      <div className="flex-1 min-w-0">
        <p className="text-xs text-white/70 font-medium truncate">{name}</p>
        <p className="text-[10px] text-white/35 mt-0.5">{freshness}</p>
      </div>
      <span className="text-[10px] font-semibold text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-1.5 py-0.5 rounded shrink-0">
        {status}
      </span>
    </li>
  );
}

export default function EvidenceSources({ events }: EvidenceSourcesProps): React.ReactElement {
  const usedTools: Map<string, string> = new Map();
  for (const ev of events) {
    if (ev.type === "tool_completed" && ev.status !== "error") {
      usedTools.set(ev.tool_name, toolLabel(ev.tool_name));
    }
  }

  const sources: readonly DataSource[] =
    usedTools.size === 0
      ? DEFAULT_SOURCES
      : Array.from(usedTools.entries()).map(([id, label]) => ({
          name: label,
          freshness: id,
          status: "Used",
        }));

  return (
    <>
      <ul>
        {sources.map((src) => (
          <SourceRow key={src.name} name={src.name} freshness={src.freshness} status={src.status} />
        ))}
      </ul>
      <button className="mt-2 text-[10px] text-indigo-400/70 hover:text-indigo-300 transition-colors">
        View all data sources →
      </button>
    </>
  );
}
