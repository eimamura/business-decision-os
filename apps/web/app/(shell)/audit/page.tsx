"use client";

import { useState } from "react";
import { useAuditEntries } from "@/features/audit/hooks";
import type { AuditEntry } from "@/features/audit/api";

export default function AuditPage(): React.ReactElement {
  const [filters, setFilters] = useState({
    session_id: "",
    agent: "",
    tool: "",
    status: "",
  });
  const [activeFilters, setActiveFilters] = useState({
    session_id: "",
    agent: "",
    tool: "",
    status: "",
  });
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  function toggleExpanded(id: string): void {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  const { data: entries = [], isLoading: loading } = useAuditEntries({
    sessionId: activeFilters.session_id || undefined,
    role: activeFilters.agent || undefined,
  });

  const totalTokensIn = entries.reduce((s, e) => s + (e.tokens_in ?? 0), 0);
  const totalTokensOut = entries.reduce((s, e) => s + (e.tokens_out ?? 0), 0);
  const totalCost = entries.reduce((s, e) => s + (e.cost_usd ?? 0), 0);

  return (
    <div className="min-h-screen bg-background">
      <header className="bg-background border-b border-border px-6 py-4">
        <h1 className="text-lg font-semibold text-foreground">Audit Timeline</h1>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-8 space-y-6">
        <div className="bg-background rounded-xl border border-border p-5">
          <div className="flex flex-wrap gap-3">
            {[
              { key: "session_id", label: "Session ID" },
              { key: "agent", label: "Agent" },
              { key: "tool", label: "Tool" },
              { key: "status", label: "Status" },
            ].map(({ key, label }) => (
              <input
                key={key}
                placeholder={label}
                value={filters[key as keyof typeof filters]}
                onChange={(e) => setFilters((p) => ({ ...p, [key]: e.target.value }))}
                className="text-sm border border-border rounded-lg px-3 py-1.5 bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-blue-500 w-40"
              />
            ))}
            <button
              onClick={() => setActiveFilters(filters)}
              className="bg-blue-600 text-white px-4 py-1.5 rounded-lg text-sm font-medium hover:bg-blue-700"
            >
              Filter
            </button>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-4">
          <div className="bg-background rounded-xl border border-border p-4 text-center">
            <p className="text-xs text-muted mb-1">Tokens In</p>
            <p className="text-lg font-semibold text-foreground">{totalTokensIn.toLocaleString()}</p>
          </div>
          <div className="bg-background rounded-xl border border-border p-4 text-center">
            <p className="text-xs text-muted mb-1">Tokens Out</p>
            <p className="text-lg font-semibold text-foreground">{totalTokensOut.toLocaleString()}</p>
          </div>
          <div className="bg-background rounded-xl border border-border p-4 text-center">
            <p className="text-xs text-muted mb-1">Total Cost</p>
            <p className="text-lg font-semibold text-foreground">
              {new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 4 }).format(totalCost)}
            </p>
          </div>
        </div>

        {loading ? (
          <div className="space-y-3">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-16 bg-surface rounded-xl animate-pulse" />
            ))}
          </div>
        ) : entries.length === 0 ? (
          <div className="text-center py-16 text-muted">
            <p>No audit entries found.</p>
          </div>
        ) : (
          <div className="bg-background rounded-xl border border-border overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-surface border-b border-border">
                  <th className="text-left px-5 py-3 font-medium text-muted">Time</th>
                  <th className="text-left px-4 py-3 font-medium text-muted">Agent</th>
                  <th className="text-left px-4 py-3 font-medium text-muted">Tool</th>
                  <th className="text-left px-4 py-3 font-medium text-muted">Status</th>
                  <th className="text-right px-4 py-3 font-medium text-muted">Tok In</th>
                  <th className="text-right px-4 py-3 font-medium text-muted">Tok Out</th>
                  <th className="text-right px-4 py-3 font-medium text-muted">Cost</th>
                  <th className="text-center px-4 py-3 font-medium text-muted">Detail</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {entries.map((e: AuditEntry) => (
                  <>
                    <tr key={e.id} className="hover:bg-surface transition-colors">
                      <td className="px-5 py-3 text-xs text-muted font-mono whitespace-nowrap">
                        {new Date(e.created_at).toLocaleString()}
                      </td>
                      <td className="px-4 py-3 text-xs text-foreground">{e.agent ?? "-"}</td>
                      <td className="px-4 py-3 text-xs text-foreground">{e.tool_name ?? "-"}</td>
                      <td className="px-4 py-3">
                        <span
                          className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                            e.status === "success"
                              ? "bg-green-100 text-green-700 dark:bg-green-500/15 dark:text-green-300"
                              : e.status === "failed"
                              ? "bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-300"
                              : "bg-surface text-muted"
                          }`}
                        >
                          {e.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-xs text-right text-muted font-mono">
                        {e.tokens_in?.toLocaleString() ?? "-"}
                      </td>
                      <td className="px-4 py-3 text-xs text-right text-muted font-mono">
                        {e.tokens_out?.toLocaleString() ?? "-"}
                      </td>
                      <td className="px-4 py-3 text-xs text-right text-muted font-mono">
                        {e.cost_usd != null
                          ? new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 4 }).format(e.cost_usd)
                          : "-"}
                      </td>
                      <td className="px-4 py-3 text-center">
                        <button
                          onClick={() => toggleExpanded(e.id)}
                          className="text-xs text-blue-600 hover:underline"
                        >
                          {expanded.has(e.id) ? "Hide" : "Show"}
                        </button>
                      </td>
                    </tr>
                    {expanded.has(e.id) && (
                      <tr key={`${e.id}-detail`} className="bg-surface">
                        <td colSpan={8} className="px-5 py-4">
                          <div className="grid grid-cols-2 gap-4">
                            {e.input != null && (
                              <div>
                                <p className="text-xs font-semibold text-muted mb-1">Input</p>
                                <pre className="text-xs bg-gray-900 text-green-300 rounded p-3 overflow-x-auto whitespace-pre-wrap">
                                  {JSON.stringify(e.input, null, 2)}
                                </pre>
                              </div>
                            )}
                            {e.output != null && (
                              <div>
                                <p className="text-xs font-semibold text-muted mb-1">Output</p>
                                <pre className="text-xs bg-gray-900 text-blue-300 rounded p-3 overflow-x-auto whitespace-pre-wrap">
                                  {JSON.stringify(e.output, null, 2)}
                                </pre>
                              </div>
                            )}
                          </div>
                          {e.audit_hash && (
                            <p className="text-xs text-muted mt-2 font-mono">
                              Hash: {e.audit_hash}
                            </p>
                          )}
                        </td>
                      </tr>
                    )}
                  </>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </div>
  );
}
