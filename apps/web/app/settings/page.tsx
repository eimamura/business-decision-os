"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface Policy {
  id: string;
  budget_soft_limit_usd: number | null;
  budget_hard_limit_usd: number | null;
  budget_period: string;
  updated_by: string | null;
  updated_at: string | null;
}

export default function SettingsPage() {
  const [policy, setPolicy] = useState<Policy | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [softLimit, setSoftLimit] = useState("");
  const [hardLimit, setHardLimit] = useState("");
  const [status, setStatus] = useState<{ type: "success" | "error"; message: string } | null>(null);

  useEffect(() => {
    fetch(`${API_BASE}/api/v1/policies`, {
      headers: { "X-Dev-User": "dev-user" },
    })
      .then((r) => r.json())
      .then((data: Policy) => {
        setPolicy(data);
        setSoftLimit(data.budget_soft_limit_usd != null ? String(data.budget_soft_limit_usd) : "");
        setHardLimit(data.budget_hard_limit_usd != null ? String(data.budget_hard_limit_usd) : "");
      })
      .catch(() => setStatus({ type: "error", message: "Failed to load policy." }))
      .finally(() => setLoading(false));
  }, []);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setStatus(null);

    const body: Record<string, number> = {};
    const soft = parseFloat(softLimit);
    const hard = parseFloat(hardLimit);
    if (!isNaN(soft)) body.budget_soft_limit_usd = soft;
    if (!isNaN(hard)) body.budget_hard_limit_usd = hard;

    try {
      const res = await fetch(`${API_BASE}/api/v1/policies`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          "X-Dev-User": "dev-user",
        },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error((err as { detail?: string }).detail ?? `HTTP ${res.status}`);
      }

      const updated: Policy = await res.json();
      setPolicy(updated);
      setSoftLimit(updated.budget_soft_limit_usd != null ? String(updated.budget_soft_limit_usd) : "");
      setHardLimit(updated.budget_hard_limit_usd != null ? String(updated.budget_hard_limit_usd) : "");
      setStatus({ type: "success", message: "Settings saved." });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Save failed.";
      setStatus({ type: "error", message });
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
        <h1 className="text-lg font-semibold text-gray-900">Business Decision OS</h1>
        <nav className="flex gap-4 text-sm text-gray-600">
          <Link href="/chat" className="hover:text-gray-900">Chat</Link>
          <Link href="/approvals" className="hover:text-gray-900">Approvals</Link>
          <Link href="/audit" className="hover:text-gray-900">Audit</Link>
          <Link href="/kpi" className="hover:text-gray-900">KPI</Link>
          <Link href="/settings" className="font-medium text-gray-900">Settings</Link>
        </nav>
      </header>

      <main className="max-w-2xl mx-auto px-6 py-10">
        <h2 className="text-xl font-semibold text-gray-900 mb-6">Budget Thresholds</h2>

        {loading ? (
          <div className="space-y-4">
            <div className="h-12 bg-gray-200 rounded-lg animate-pulse" />
            <div className="h-12 bg-gray-200 rounded-lg animate-pulse" />
            <div className="h-10 bg-gray-200 rounded-lg animate-pulse w-24" />
          </div>
        ) : (
          <form onSubmit={handleSave} className="bg-white border border-gray-200 rounded-xl p-6 space-y-5">
            <div>
              <label htmlFor="soft-limit" className="block text-sm font-medium text-gray-700 mb-1.5">
                Soft limit (USD)
              </label>
              <input
                id="soft-limit"
                type="number"
                min="0"
                step="0.01"
                value={softLimit}
                onChange={(e) => setSoftLimit(e.target.value)}
                placeholder="e.g. 10.00"
                className="w-full text-sm border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <p className="mt-1 text-xs text-gray-500">
                A warning is triggered when spending approaches this amount within the current period.
              </p>
            </div>

            <div>
              <label htmlFor="hard-limit" className="block text-sm font-medium text-gray-700 mb-1.5">
                Hard limit (USD)
              </label>
              <input
                id="hard-limit"
                type="number"
                min="0"
                step="0.01"
                value={hardLimit}
                onChange={(e) => setHardLimit(e.target.value)}
                placeholder="e.g. 50.00"
                className="w-full text-sm border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <p className="mt-1 text-xs text-gray-500">
                LLM calls are blocked once spending reaches this amount within the current period.
              </p>
            </div>

            {policy && (
              <div className="text-xs text-gray-400 border-t border-gray-100 pt-4">
                Period: <span className="font-medium text-gray-600">{policy.budget_period}</span>
                {policy.updated_at && (
                  <> &middot; Last updated: <span className="font-medium text-gray-600">{new Date(policy.updated_at).toLocaleString()}</span></>
                )}
              </div>
            )}

            {status && (
              <div
                className={`text-sm px-4 py-2.5 rounded-lg ${
                  status.type === "success"
                    ? "bg-green-50 text-green-700 border border-green-200"
                    : "bg-red-50 text-red-700 border border-red-200"
                }`}
              >
                {status.message}
              </div>
            )}

            <div className="flex justify-end">
              <button
                type="submit"
                disabled={saving}
                className="bg-blue-600 text-white px-5 py-2 rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
              >
                {saving ? "Saving..." : "Save"}
              </button>
            </div>
          </form>
        )}
      </main>
    </div>
  );
}
