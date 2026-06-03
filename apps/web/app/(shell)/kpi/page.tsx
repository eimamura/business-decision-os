"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { useKpiTrends, useLlmCostEntries } from "@/features/kpi/hooks";
import type { KpiTrend, LlmCostEntry } from "@/features/kpi/api";

export default function KpiPage(): React.ReactElement {
  const { data: kpiData = [], isLoading: kpiLoading } = useKpiTrends();
  const { data: llmData = [], isLoading: llmLoading } = useLlmCostEntries();

  const llmByDate = aggregateLlmByDate(llmData);

  return (
    <div className="min-h-screen bg-background">
      <header className="bg-background border-b border-border px-6 py-4">
        <h1 className="text-lg font-semibold text-foreground">KPI Dashboard</h1>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-8 space-y-8">
        <div className="bg-background rounded-xl border border-border p-6">
          <h2 className="text-base font-semibold text-foreground mb-4">Service Level Trend</h2>
          {kpiLoading ? (
            <div className="h-64 bg-surface rounded-lg animate-pulse" />
          ) : kpiData.length === 0 ? (
            <PlaceholderChart label="Service Level" />
          ) : (
            <ResponsiveContainer width="100%" height={256}>
              <LineChart data={kpiData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                <YAxis domain={[0, 1]} tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`} tick={{ fontSize: 11 }} />
                <Tooltip formatter={(v: number) => `${(v * 100).toFixed(1)}%`} />
                <Legend />
                <Line type="monotone" dataKey="service_level" name="Service Level" stroke="#3b82f6" dot={false} strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {[
            { key: "inventory_cost", label: "Inventory Cost", color: "#10b981", format: (v: number) => `$${v.toFixed(0)}` },
            { key: "stockout_days", label: "Stockout Days", color: "#ef4444", format: (v: number) => `${v.toFixed(1)}d` },
            { key: "working_capital", label: "Working Capital", color: "#8b5cf6", format: (v: number) => `$${v.toFixed(0)}` },
          ].map(({ key, label, color, format }) => (
            <div key={key} className="bg-background rounded-xl border border-border p-4">
              <h3 className="text-sm font-semibold text-foreground mb-3">{label}</h3>
              {kpiLoading ? (
                <div className="h-32 bg-surface rounded animate-pulse" />
              ) : kpiData.length === 0 ? (
                <PlaceholderChart label={label} height={128} />
              ) : (
                <ResponsiveContainer width="100%" height={128}>
                  <LineChart data={kpiData}>
                    <XAxis dataKey="date" hide />
                    <YAxis hide />
                    <Tooltip formatter={(v: number) => format(v)} />
                    <Line type="monotone" dataKey={key} stroke={color} dot={false} strokeWidth={2} />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </div>
          ))}
        </div>

        <div className="bg-background rounded-xl border border-border p-6">
          <h2 className="text-base font-semibold text-foreground mb-4">LLM Cost Trend</h2>
          {llmLoading ? (
            <div className="h-64 bg-surface rounded-lg animate-pulse" />
          ) : llmByDate.length === 0 ? (
            <PlaceholderChart label="LLM Cost (USD)" />
          ) : (
            <ResponsiveContainer width="100%" height={256}>
              <LineChart data={llmByDate}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                <YAxis
                  tickFormatter={(v: number) =>
                    new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2 }).format(v)
                  }
                  tick={{ fontSize: 11 }}
                />
                <Tooltip
                  formatter={(v: number) =>
                    new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 4 }).format(v)
                  }
                />
                <Legend />
                <Line type="monotone" dataKey="domain_expert" name="Domain Expert" stroke="#3b82f6" dot={false} strokeWidth={2} />
                <Line type="monotone" dataKey="data_engineer" name="Data Engineer" stroke="#10b981" dot={false} strokeWidth={2} />
                <Line type="monotone" dataKey="sim_opt" name="Sim/Opt" stroke="#f59e0b" dot={false} strokeWidth={2} />
                <Line type="monotone" dataKey="evaluator" name="Evaluator" stroke="#8b5cf6" dot={false} strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>
      </main>
    </div>
  );
}

function PlaceholderChart({ label, height = 256 }: { label: string; height?: number }): React.ReactElement {
  return (
    <div
      className="flex items-center justify-center bg-surface rounded-lg border border-dashed border-border text-muted text-sm"
      style={{ height }}
    >
      {label} — no data yet
    </div>
  );
}

function aggregateLlmByDate(entries: LlmCostEntry[]): Record<string, number | string>[] {
  const byDate: Record<string, Record<string, number>> = {};
  for (const e of entries) {
    if (!byDate[e.date]) byDate[e.date] = {};
    const role = e.specialist ?? "unknown";
    byDate[e.date][role] = (byDate[e.date][role] ?? 0) + e.cost_usd;
  }
  return Object.entries(byDate)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, costs]) => ({ date, ...costs }));
}
