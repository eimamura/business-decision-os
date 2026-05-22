"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { RefreshCw } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const DEV_HEADERS = { "X-Dev-User": "dev-user" };

interface AgentStep {
  step_id: string;
  session_id: string;
  session_title: string;
  specialist_role: string;
  step_type: string;
  started_at: string | null;
  ended_at: string | null;
  duration_ms: number | null;
  input_tokens: number;
  output_tokens: number;
  total_cost_usd: number;
}

interface LlmUsageRow {
  id: string;
  agent_step_id: string;
  specialist_role: string;
  session_id: string;
  session_title: string;
  model: string;
  input_tokens: number;
  output_tokens: number;
  cache_read_tokens: number;
  cache_write_tokens: number;
  total_cost_usd: number;
  latency_ms: number | null;
  created_at: string;
}

type ActiveTab = "steps" | "llm";

function fmt(n: number): string {
  return n.toLocaleString();
}

function fmtCost(n: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 4,
    maximumFractionDigits: 6,
  }).format(n);
}

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

function fmtDuration(ms: number | null): string {
  if (ms == null || ms < 0) return "—";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function roleBadgeClass(role: string): string {
  const map: Record<string, string> = {
    data_engineer: "bg-blue-500/15 text-blue-300",
    simulation_optimizer: "bg-purple-500/15 text-purple-300",
    evaluator: "bg-amber-500/15 text-amber-300",
    anomaly_detector: "bg-red-500/15 text-red-300",
    orchestrator: "bg-indigo-500/15 text-indigo-300",
  };
  return map[role] ?? "bg-white/8 text-white/50";
}

export default function UsagePage(): React.ReactElement {
  const [steps, setSteps] = useState<AgentStep[]>([]);
  const [llmRows, setLlmRows] = useState<LlmUsageRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<ActiveTab>("steps");
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [stepsRes, llmRes] = await Promise.all([
        fetch(`${API_BASE}/api/v1/admin/steps`, { headers: DEV_HEADERS }),
        fetch(`${API_BASE}/api/v1/admin/llm-usage`, { headers: DEV_HEADERS }),
      ]);
      const [stepsData, llmData] = await Promise.all([
        stepsRes.ok ? stepsRes.json() : [],
        llmRes.ok ? llmRes.json() : [],
      ]);
      setSteps(Array.isArray(stepsData) ? (stepsData as AgentStep[]) : []);
      setLlmRows(Array.isArray(llmData) ? (llmData as LlmUsageRow[]) : []);
    } catch {
      setSteps([]);
      setLlmRows([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleDeleteAll(): Promise<void> {
    setDeleting(true);
    try {
      await fetch(`${API_BASE}/api/v1/admin/sessions`, {
        method: "DELETE",
        headers: DEV_HEADERS,
      });
      setConfirmDelete(false);
      await load();
    } finally {
      setDeleting(false);
    }
  }

  const totalCost = steps.reduce((s, r) => s + r.total_cost_usd, 0);
  const totalIn = steps.reduce((s, r) => s + r.input_tokens, 0);
  const totalOut = steps.reduce((s, r) => s + r.output_tokens, 0);
  const uniqueSessions = new Set(steps.map((r) => r.session_id)).size;

  return (
    <div className="min-h-screen bg-[#070B14] text-white">
      {/* Header */}
      <header className="border-b border-white/8 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link href="/chat" className="text-xs text-white/40 hover:text-white/70 transition-colors">
            ← Chat
          </Link>
          <h1 className="text-sm font-semibold text-white">Usage &amp; Cost</h1>
        </div>
        <div className="flex items-center gap-4">
          {confirmDelete ? (
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setConfirmDelete(false)}
                className="text-xs text-white/40 hover:text-white/70 transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => void handleDeleteAll()}
                disabled={deleting}
                className="text-xs px-3 py-1.5 rounded-md bg-red-600 text-white hover:bg-red-500 disabled:opacity-50 transition-colors"
              >
                {deleting ? "Deleting…" : "Confirm Delete All"}
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setConfirmDelete(true)}
              className="text-xs text-red-400/60 hover:text-red-400 transition-colors"
            >
              Delete All Sessions
            </button>
          )}
          <button
            type="button"
            onClick={() => void load()}
            className="flex items-center gap-1.5 text-xs text-white/40 hover:text-white/70 transition-colors"
          >
            <RefreshCw size={12} className={loading ? "animate-spin" : ""} />
            Refresh
          </button>
        </div>
      </header>

      <main className="max-w-screen-xl mx-auto px-6 py-6 space-y-6">
        {/* Stats bar */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            { label: "Sessions", value: uniqueSessions.toString() },
            { label: "Agent Steps", value: fmt(steps.length) },
            { label: "Total Tokens", value: fmt(totalIn + totalOut) },
            { label: "Total Cost", value: fmtCost(totalCost) },
          ].map(({ label, value }) => (
            <div
              key={label}
              className="bg-[#0B1020] border border-white/6 rounded-xl px-4 py-3"
            >
              <p className="text-[10px] uppercase tracking-widest text-white/30 mb-1">{label}</p>
              <p className="text-lg font-semibold text-white font-mono">{value}</p>
            </div>
          ))}
        </div>

        {/* Tab switcher */}
        <div className="flex gap-1 bg-white/4 rounded-lg p-1 w-fit">
          {(["steps", "llm"] as ActiveTab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-4 py-1.5 rounded-md text-xs font-medium transition-colors ${
                tab === t
                  ? "bg-indigo-500/25 text-white"
                  : "text-white/40 hover:text-white/70"
              }`}
            >
              {t === "steps" ? `Agent Steps (${steps.length})` : `LLM Calls (${llmRows.length})`}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="space-y-2">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="h-12 bg-white/4 rounded-lg animate-pulse" />
            ))}
          </div>
        ) : tab === "steps" ? (
          <StepsTable rows={steps} />
        ) : (
          <LlmTable rows={llmRows} />
        )}
      </main>
    </div>
  );
}

function StepsTable({ rows }: { rows: AgentStep[] }): React.ReactElement {
  if (rows.length === 0) {
    return (
      <div className="text-center py-20 text-white/25 text-sm">
        No agent steps recorded yet. Send a message in chat to generate data.
      </div>
    );
  }

  return (
    <div className="bg-[#0B1020] border border-white/6 rounded-xl overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-white/6 text-white/30">
              <th className="text-left px-4 py-3 font-medium">Time</th>
              <th className="text-left px-4 py-3 font-medium">Session</th>
              <th className="text-left px-4 py-3 font-medium">Role</th>
              <th className="text-right px-4 py-3 font-medium">Duration</th>
              <th className="text-right px-4 py-3 font-medium">Tok In</th>
              <th className="text-right px-4 py-3 font-medium">Tok Out</th>
              <th className="text-right px-4 py-3 font-medium">Cost</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/4">
            {rows.map((r) => (
              <tr key={r.step_id} className="hover:bg-white/3 transition-colors">
                <td className="px-4 py-3 font-mono text-white/40 whitespace-nowrap">
                  {fmtTime(r.started_at)}
                </td>
                <td className="px-4 py-3 max-w-[180px]">
                  <Link
                    href={`/chat/${r.session_id}`}
                    className="text-indigo-400 hover:text-indigo-300 truncate block transition-colors"
                    title={r.session_title}
                  >
                    {r.session_title}
                  </Link>
                </td>
                <td className="px-4 py-3">
                  <span
                    className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-medium ${roleBadgeClass(r.specialist_role)}`}
                  >
                    {r.specialist_role.replace(/_/g, " ")}
                  </span>
                </td>
                <td className="px-4 py-3 text-right font-mono text-white/50">
                  {fmtDuration(r.duration_ms)}
                </td>
                <td className="px-4 py-3 text-right font-mono text-white/50">
                  {fmt(r.input_tokens)}
                </td>
                <td className="px-4 py-3 text-right font-mono text-white/50">
                  {fmt(r.output_tokens)}
                </td>
                <td className="px-4 py-3 text-right font-mono text-emerald-400/80">
                  {fmtCost(r.total_cost_usd)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function LlmTable({ rows }: { rows: LlmUsageRow[] }): React.ReactElement {
  if (rows.length === 0) {
    return (
      <div className="text-center py-20 text-white/25 text-sm">
        No LLM usage recorded yet. Send a message in chat to generate data.
      </div>
    );
  }

  return (
    <div className="bg-[#0B1020] border border-white/6 rounded-xl overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-white/6 text-white/30">
              <th className="text-left px-4 py-3 font-medium">Time</th>
              <th className="text-left px-4 py-3 font-medium">Session</th>
              <th className="text-left px-4 py-3 font-medium">Role</th>
              <th className="text-left px-4 py-3 font-medium">Model</th>
              <th className="text-right px-4 py-3 font-medium">Tok In</th>
              <th className="text-right px-4 py-3 font-medium">Tok Out</th>
              <th className="text-right px-4 py-3 font-medium">Cache R</th>
              <th className="text-right px-4 py-3 font-medium">Latency</th>
              <th className="text-right px-4 py-3 font-medium">Cost</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/4">
            {rows.map((r) => (
              <tr key={r.id} className="hover:bg-white/3 transition-colors">
                <td className="px-4 py-3 font-mono text-white/40 whitespace-nowrap">
                  {fmtTime(r.created_at)}
                </td>
                <td className="px-4 py-3 max-w-[160px]">
                  <Link
                    href={`/chat/${r.session_id}`}
                    className="text-indigo-400 hover:text-indigo-300 truncate block transition-colors"
                    title={r.session_title}
                  >
                    {r.session_title}
                  </Link>
                </td>
                <td className="px-4 py-3">
                  <span
                    className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-medium ${roleBadgeClass(r.specialist_role)}`}
                  >
                    {r.specialist_role.replace(/_/g, " ")}
                  </span>
                </td>
                <td className="px-4 py-3 font-mono text-white/40 whitespace-nowrap">
                  {r.model.replace("claude-", "").replace(/-\d{8}$/, "")}
                </td>
                <td className="px-4 py-3 text-right font-mono text-white/50">
                  {fmt(r.input_tokens)}
                </td>
                <td className="px-4 py-3 text-right font-mono text-white/50">
                  {fmt(r.output_tokens)}
                </td>
                <td className="px-4 py-3 text-right font-mono text-white/40">
                  {r.cache_read_tokens > 0 ? fmt(r.cache_read_tokens) : "—"}
                </td>
                <td className="px-4 py-3 text-right font-mono text-white/40">
                  {fmtDuration(r.latency_ms)}
                </td>
                <td className="px-4 py-3 text-right font-mono text-emerald-400/80">
                  {fmtCost(r.total_cost_usd)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
