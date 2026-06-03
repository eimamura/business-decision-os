"use client";

import { useState } from "react";
import { RefreshCw } from "lucide-react";
import { useAgentRegistry } from "@/features/agents/hooks";
import type { RegistryData } from "@/features/agents/api";

type ActiveTab = "agents" | "tools";

type AgentEntry = RegistryData["agents"][number];
type ToolEntry = RegistryData["tools"][number];

function fmtTime(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function categoryBadgeClass(category: AgentEntry["category"]): string {
  if (category === "domain") return "bg-blue-500/15 text-blue-300";
  if (category === "cross_domain") return "bg-purple-500/15 text-purple-300";
  return "bg-indigo-500/15 text-indigo-300";
}

function categoryLabel(category: AgentEntry["category"]): string {
  if (category === "domain") return "Domain";
  if (category === "cross_domain") return "Cross-Domain";
  return "Orchestrator";
}

function agentBadgeClass(role: string): string {
  const map: Record<string, string> = {
    data_engineer: "bg-blue-500/15 text-blue-300",
    simulation_optimizer: "bg-purple-500/15 text-purple-300",
    evaluator: "bg-amber-500/15 text-amber-300",
    anomaly_detector: "bg-red-500/15 text-red-300",
    orchestrator: "bg-indigo-500/15 text-indigo-300",
  };
  return map[role] ?? "bg-surface dark:bg-white/8 text-muted dark:text-white/50";
}

export default function AgentsPage(): React.ReactElement {
  const [tab, setTab] = useState<ActiveTab>("agents");
  const { data = { agents: [], tools: [] }, isLoading: loading, refetch } = useAgentRegistry();

  const totalRuns = data.agents.reduce((s, a) => s + a.execution_count, 0);
  const totalCalls = data.tools.reduce((s, t) => s + t.execution_count, 0);

  return (
    <div className="min-h-screen bg-background dark:bg-[#070B14] text-foreground dark:text-white">
      <header className="border-b border-border dark:border-white/8 px-6 py-4 flex items-center justify-between">
        <h1 className="text-sm font-semibold text-foreground dark:text-white">Agents &amp; Tools</h1>
        <button
          type="button"
          onClick={() => void refetch()}
          className="flex items-center gap-1.5 text-xs text-muted dark:text-white/40 hover:text-foreground dark:hover:text-white/70 transition-colors"
        >
          <RefreshCw size={12} className={loading ? "animate-spin" : ""} />
          Refresh
        </button>
      </header>

      <main className="max-w-screen-xl mx-auto px-6 py-6 space-y-6">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            { label: "Agents", value: data.agents.length.toString() },
            { label: "Tools", value: data.tools.length.toString() },
            { label: "Total Agent Runs", value: totalRuns.toLocaleString() },
            { label: "Total Tool Calls", value: totalCalls.toLocaleString() },
          ].map(({ label, value }) => (
            <div key={label} className="bg-surface dark:bg-[#0B1020] border border-border dark:border-white/6 rounded-xl px-4 py-3">
              <p className="text-[10px] uppercase tracking-widest text-muted dark:text-white/30 mb-1">{label}</p>
              <p className="text-lg font-semibold text-foreground dark:text-white font-mono">{value}</p>
            </div>
          ))}
        </div>

        <div className="flex gap-1 bg-white/4 rounded-lg p-1 w-fit">
          {(["agents", "tools"] as ActiveTab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-4 py-1.5 rounded-md text-xs font-medium transition-colors ${
                tab === t
                  ? "bg-indigo-500/25 text-foreground dark:text-white"
                  : "text-muted dark:text-white/40 hover:text-foreground dark:hover:text-white/70"
              }`}
            >
              {t === "agents"
                ? `Agents (${data.agents.length})`
                : `Tools (${data.tools.length})`}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="space-y-2">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="h-12 bg-white/4 rounded-lg animate-pulse" />
            ))}
          </div>
        ) : tab === "agents" ? (
          <AgentsTable rows={data.agents} />
        ) : (
          <ToolsTable rows={data.tools} />
        )}
      </main>
    </div>
  );
}

function AgentsTable({ rows }: { rows: AgentEntry[] }): React.ReactElement {
  if (rows.length === 0) {
    return (
      <div className="text-center py-20 text-muted dark:text-white/25 text-sm">
        No agents registered yet.
      </div>
    );
  }

  return (
    <div className="bg-surface dark:bg-[#0B1020] border border-border dark:border-white/6 rounded-xl overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-border dark:border-white/6 text-muted dark:text-white/30">
              <th className="text-left px-4 py-3 font-medium">Agent</th>
              <th className="text-left px-4 py-3 font-medium">Category</th>
              <th className="text-left px-4 py-3 font-medium">Tools</th>
              <th className="text-right px-4 py-3 font-medium">Runs</th>
              <th className="text-right px-4 py-3 font-medium">Last Run</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/4">
            {rows.map((a) => (
              <tr key={a.role} className="hover:bg-white/3 transition-colors">
                <td className="px-4 py-3">
                  <span
                    className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-medium ${categoryBadgeClass(a.category)}`}
                  >
                    {a.display_name}
                  </span>
                </td>
                <td className="px-4 py-3 text-muted dark:text-white/40">{categoryLabel(a.category)}</td>
                <td className="px-4 py-3">
                  <div className="flex flex-wrap gap-1">
                    {a.tools.length === 0 ? (
                      <span className="text-muted dark:text-white/20">—</span>
                    ) : (
                      a.tools.map((t) => (
                        <span
                          key={t}
                          className="inline-block px-1.5 py-0.5 rounded text-[10px] bg-surface dark:bg-white/8 text-muted dark:text-white/45"
                        >
                          {t.replace(/_/g, " ")}
                        </span>
                      ))
                    )}
                  </div>
                </td>
                <td className="px-4 py-3 text-right font-mono">
                  {a.execution_count > 0 ? (
                    <span className="text-foreground/70 dark:text-white/70">{a.execution_count.toLocaleString()}</span>
                  ) : (
                    <span className="text-muted dark:text-white/20">0</span>
                  )}
                </td>
                <td className="px-4 py-3 text-right font-mono text-muted dark:text-white/40 whitespace-nowrap">
                  {fmtTime(a.last_executed_at)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ToolsTable({ rows }: { rows: ToolEntry[] }): React.ReactElement {
  if (rows.length === 0) {
    return (
      <div className="text-center py-20 text-muted dark:text-white/25 text-sm">
        No tools registered yet.
      </div>
    );
  }

  return (
    <div className="bg-surface dark:bg-[#0B1020] border border-border dark:border-white/6 rounded-xl overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-border dark:border-white/6 text-muted dark:text-white/30">
              <th className="text-left px-4 py-3 font-medium">Tool</th>
              <th className="text-left px-4 py-3 font-medium">Used By</th>
              <th className="text-right px-4 py-3 font-medium">Calls</th>
              <th className="text-right px-4 py-3 font-medium">Last Call</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/4">
            {rows.map((t) => (
              <tr key={t.name} className="hover:bg-white/3 transition-colors">
                <td className="px-4 py-3">
                  <span className="inline-block px-2 py-0.5 rounded text-[10px] font-mono bg-surface dark:bg-white/8 text-foreground/70 dark:text-white/70">
                    {t.name}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <div className="flex flex-wrap gap-1">
                    {t.used_by_agents.map((role) => (
                      <span
                        key={role}
                        className={`inline-block px-1.5 py-0.5 rounded-full text-[10px] font-medium ${agentBadgeClass(role)}`}
                      >
                        {role.replace(/_/g, " ")}
                      </span>
                    ))}
                  </div>
                </td>
                <td className="px-4 py-3 text-right font-mono">
                  {t.execution_count > 0 ? (
                    <span className="text-foreground/70 dark:text-white/70">{t.execution_count.toLocaleString()}</span>
                  ) : (
                    <span className="text-muted dark:text-white/20">0</span>
                  )}
                </td>
                <td className="px-4 py-3 text-right font-mono text-muted dark:text-white/40 whitespace-nowrap">
                  {fmtTime(t.last_executed_at)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
