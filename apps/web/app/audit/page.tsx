"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface AuditEntry {
  id: string;
  session_id?: string;
  agent?: string;
  tool_name?: string;
  status: string;
  input?: unknown;
  output?: unknown;
  tokens_in?: number;
  tokens_out?: number;
  cost_usd?: number;
  created_at: string;
  audit_hash?: string;
}

export default function AuditPage() {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({
    session_id: "",
    agent: "",
    tool: "",
    status: "",
  });
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  function toggleExpanded(id: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function loadEntries() {
    setLoading(true);
    const params = new URLSearchParams();
    if (filters.session_id) params.set("session_id", filters.session_id);
    if (filters.agent) params.set("agent", filters.agent);
    if (filters.tool) params.set("tool", filters.tool);
    if (filters.status) params.set("status", filters.status);

    fetch(`${API_BASE}/api/v1/audit?${params}`, {
      headers: { "X-Dev-User": "dev-user" },
    })
      .then((r) => r.json())
      .then((data) => setEntries(Array.isArray(data) ? data : data.items ?? []))
      .catch(() => setEntries([]))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    loadEntries();
  }, []);

  const totalTokensIn = entries.reduce((s, e) => s + (e.tokens_in ?? 0), 0);
  const totalTokensOut = entries.reduce((s, e) => s + (e.tokens_out ?? 0), 0);
  const totalCost = entries.reduce((s, e) => s + (e.cost_usd ?? 0), 0);

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center gap-4">
        <Link href="/chat" className="text-sm text-blue-600 hover:underline">← Chat</Link>
        <h1 className="text-lg font-semibold text-gray-900">Audit Timeline</h1>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-8 space-y-6">
        <div className="bg-white rounded-xl border border-gray-200 p-5">
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
                className="text-sm border border-gray-300 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500 w-40"
              />
            ))}
            <button
              onClick={loadEntries}
              className="bg-blue-600 text-white px-4 py-1.5 rounded-lg text-sm font-medium hover:bg-blue-700"
            >
              Filter
            </button>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-4">
          <div className="bg-white rounded-xl border border-gray-200 p-4 text-center">
            <p className="text-xs text-gray-500 mb-1">Tokens In</p>
            <p className="text-lg font-semibold text-gray-900">{totalTokensIn.toLocaleString()}</p>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-4 text-center">
            <p className="text-xs text-gray-500 mb-1">Tokens Out</p>
            <p className="text-lg font-semibold text-gray-900">{totalTokensOut.toLocaleString()}</p>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-4 text-center">
            <p className="text-xs text-gray-500 mb-1">Total Cost</p>
            <p className="text-lg font-semibold text-gray-900">
              {new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 4 }).format(totalCost)}
            </p>
          </div>
        </div>

        {loading ? (
          <div className="space-y-3">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-16 bg-gray-200 rounded-xl animate-pulse" />
            ))}
          </div>
        ) : entries.length === 0 ? (
          <div className="text-center py-16 text-gray-500">
            <p>No audit entries found.</p>
          </div>
        ) : (
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-200">
                  <th className="text-left px-5 py-3 font-medium text-gray-600">Time</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Agent</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Tool</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Status</th>
                  <th className="text-right px-4 py-3 font-medium text-gray-600">Tok In</th>
                  <th className="text-right px-4 py-3 font-medium text-gray-600">Tok Out</th>
                  <th className="text-right px-4 py-3 font-medium text-gray-600">Cost</th>
                  <th className="text-center px-4 py-3 font-medium text-gray-600">Detail</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {entries.map((e) => (
                  <>
                    <tr key={e.id} className="hover:bg-gray-50">
                      <td className="px-5 py-3 text-xs text-gray-500 font-mono whitespace-nowrap">
                        {new Date(e.created_at).toLocaleString()}
                      </td>
                      <td className="px-4 py-3 text-xs text-gray-700">{e.agent ?? "-"}</td>
                      <td className="px-4 py-3 text-xs text-gray-700">{e.tool_name ?? "-"}</td>
                      <td className="px-4 py-3">
                        <span
                          className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                            e.status === "success"
                              ? "bg-green-100 text-green-700"
                              : e.status === "failed"
                              ? "bg-red-100 text-red-700"
                              : "bg-gray-100 text-gray-600"
                          }`}
                        >
                          {e.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-xs text-right text-gray-600 font-mono">
                        {e.tokens_in?.toLocaleString() ?? "-"}
                      </td>
                      <td className="px-4 py-3 text-xs text-right text-gray-600 font-mono">
                        {e.tokens_out?.toLocaleString() ?? "-"}
                      </td>
                      <td className="px-4 py-3 text-xs text-right text-gray-600 font-mono">
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
                      <tr key={`${e.id}-detail`} className="bg-gray-50">
                        <td colSpan={8} className="px-5 py-4">
                          <div className="grid grid-cols-2 gap-4">
                            {e.input != null && (
                              <div>
                                <p className="text-xs font-semibold text-gray-600 mb-1">Input</p>
                                <pre className="text-xs bg-gray-900 text-green-300 rounded p-3 overflow-x-auto whitespace-pre-wrap">
                                  {JSON.stringify(e.input, null, 2)}
                                </pre>
                              </div>
                            )}
                            {e.output != null && (
                              <div>
                                <p className="text-xs font-semibold text-gray-600 mb-1">Output</p>
                                <pre className="text-xs bg-gray-900 text-blue-300 rounded p-3 overflow-x-auto whitespace-pre-wrap">
                                  {JSON.stringify(e.output, null, 2)}
                                </pre>
                              </div>
                            )}
                          </div>
                          {e.audit_hash && (
                            <p className="text-xs text-gray-400 mt-2 font-mono">
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
