"use client";

import type { GraphRunNode } from "@/types/workspace";

const TOOL_DISPLAY_NAMES: Record<string, string> = {
  sql_query: "SQL Query",
  nl_query: "Natural Language Query",
  forecast: "Demand Forecast",
  simulate_inventory: "Inventory Simulation",
  optimize_replenishment: "Replenishment Optimization",
  evaluate_candidates: "Candidate Evaluation",
  write_audit_log: "Audit Log",
};

interface ToolSource {
  name: string;
  toolName: string;
  detail: string;
}

interface EvidenceSourcesProps {
  graphRun: GraphRunNode[];
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

function outputDetail(node: GraphRunNode): string {
  const out = node.output;
  if (!out) return "Retrieved";
  if (typeof out.row_count === "number") return `${out.row_count} rows`;
  if (typeof out.executed_query === "string") return "Query executed";
  if (typeof out.forecast_periods === "number") return `${out.forecast_periods} periods`;
  return "Retrieved";
}

function SourceRow({ name, detail }: ToolSource): React.ReactElement {
  return (
    <li className="flex items-start gap-3 py-2.5 border-b border-white/[0.06] last:border-0">
      <DatabaseIcon />
      <div className="flex-1 min-w-0">
        <p className="text-xs text-white/70 font-medium truncate">{name}</p>
        <p className="text-[10px] text-white/35 mt-0.5">{detail}</p>
      </div>
      <span className="text-[10px] font-semibold text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-1.5 py-0.5 rounded shrink-0">
        Used
      </span>
    </li>
  );
}

export default function EvidenceSources({ graphRun }: EvidenceSourcesProps): React.ReactElement {
  // Deduplicate completed tool nodes by tool name
  const seen = new Set<string>();
  const sources: ToolSource[] = [];
  for (const node of graphRun) {
    if (node.kind !== "tool" || node.status !== "completed") continue;
    if (seen.has(node.name)) continue;
    seen.add(node.name);
    sources.push({
      name: TOOL_DISPLAY_NAMES[node.name] ?? node.name.replace(/_/g, " "),
      toolName: node.name,
      detail: outputDetail(node),
    });
  }

  if (sources.length === 0) {
    return (
      <p className="text-[11px] text-white/25 py-2">No data sources used yet.</p>
    );
  }

  return (
    <>
      <ul>
        {sources.map((src) => (
          <SourceRow key={src.toolName} name={src.name} toolName={src.toolName} detail={src.detail} />
        ))}
      </ul>
      <button className="mt-2 text-[10px] text-indigo-400/70 hover:text-indigo-300 transition-colors">
        View all data sources →
      </button>
    </>
  );
}
