"use client";

import { useState } from "react";
import Link from "next/link";
import { useApprovals, useApprovalDecision, useApprovalRevision } from "@/features/approvals/hooks";
import type { Approval } from "@/features/approvals/api";

const RISK_STYLES = {
  low: "bg-green-100 text-green-700 dark:bg-green-500/15 dark:text-green-300",
  medium: "bg-yellow-100 text-yellow-700 dark:bg-yellow-500/15 dark:text-yellow-300",
  high: "bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-300",
};

const STATUS_STYLES: Record<string, string> = {
  pending: "bg-blue-100 text-blue-700 dark:bg-blue-500/15 dark:text-blue-300",
  approved: "bg-green-100 text-green-700 dark:bg-green-500/15 dark:text-green-300",
  rejected: "bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-300",
  needs_revision: "bg-orange-100 text-orange-700 dark:bg-orange-500/15 dark:text-orange-300",
  expired: "bg-surface text-muted dark:bg-gray-100 dark:text-gray-600",
};

export default function ApprovalsPage(): React.ReactElement {
  const [actionId, setActionId] = useState<string | null>(null);
  const [revisionId, setRevisionId] = useState<string | null>(null);
  const [revisionReason, setRevisionReason] = useState("");
  const [weights, setWeights] = useState<Record<string, string>>({});
  const [statusFilter, setStatusFilter] = useState("pending");

  const { data: approvals = [], isLoading: loading } = useApprovals(statusFilter);
  const decisionMutation = useApprovalDecision();
  const revisionMutation = useApprovalRevision();

  function decide(id: string, decision: "approved" | "rejected"): void {
    setActionId(id);
    decisionMutation.mutate({ id, decision }, { onSettled: () => setActionId(null) });
  }

  function requestRevision(id: string): void {
    if (!revisionReason.trim()) return;
    setActionId(id);
    const parsedWeights: Record<string, number> = {};
    for (const [k, v] of Object.entries(weights)) {
      const n = parseFloat(v);
      if (!isNaN(n)) parsedWeights[k] = n;
    }
    revisionMutation.mutate(
      {
        id,
        payload: {
          decision: "needs_revision",
          reason: revisionReason,
          kpi_weights: Object.keys(parsedWeights).length > 0 ? parsedWeights : undefined,
        },
      },
      {
        onSuccess: () => {
          setRevisionId(null);
          setRevisionReason("");
          setWeights({});
        },
        onSettled: () => setActionId(null),
      },
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <header className="bg-background border-b border-border px-6 py-4 flex items-center justify-between">
        <h1 className="text-lg font-semibold text-foreground">Approval Queue</h1>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="text-sm border border-border rounded-lg px-3 py-1.5 bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="pending">Pending</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
          <option value="needs_revision">Needs Revision</option>
          <option value="expired">Expired</option>
        </select>
      </header>

      <main className="max-w-4xl mx-auto px-6 py-8">
        {loading ? (
          <div className="space-y-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-28 bg-surface rounded-xl animate-pulse" />
            ))}
          </div>
        ) : approvals.length === 0 ? (
          <div className="text-center py-16 text-muted">
            <p>No {statusFilter} approvals.</p>
          </div>
        ) : (
          <ul className="space-y-4">
            {approvals.map((a: Approval) => (
              <li key={a.id} className="bg-background rounded-xl border border-border p-5">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex flex-wrap items-center gap-2 mb-2">
                      <span
                        className={`text-xs px-2.5 py-0.5 rounded-full font-medium ${RISK_STYLES[a.risk_level]}`}
                      >
                        {a.risk_level} risk
                      </span>
                      <span
                        className={`text-xs px-2.5 py-0.5 rounded-full font-medium ${STATUS_STYLES[a.status]}`}
                      >
                        {a.status}
                      </span>
                      <Link
                        href={`/recommendations/${a.recommendation_id}`}
                        className="text-xs text-blue-600 hover:underline"
                      >
                        View Recommendation
                      </Link>
                    </div>
                    {a.summary && (
                      <p className="text-sm text-foreground mb-2">{a.summary}</p>
                    )}
                    <p className="text-xs text-muted">
                      Created {new Date(a.created_at).toLocaleString()}
                      {a.expires_at && ` · Expires ${new Date(a.expires_at).toLocaleString()}`}
                    </p>
                  </div>

                  {a.status === "pending" && (
                    <div className="flex gap-2 shrink-0">
                      <button
                        onClick={() => decide(a.id, "approved")}
                        disabled={actionId === a.id}
                        className="bg-green-600 text-white px-4 py-1.5 rounded-lg text-sm font-medium hover:bg-green-700 disabled:opacity-50"
                      >
                        Approve
                      </button>
                      <button
                        onClick={() => decide(a.id, "rejected")}
                        disabled={actionId === a.id}
                        className="bg-red-600 text-white px-4 py-1.5 rounded-lg text-sm font-medium hover:bg-red-700 disabled:opacity-50"
                      >
                        Reject
                      </button>
                      <button
                        onClick={() => setRevisionId(a.id)}
                        disabled={actionId === a.id}
                        className="bg-orange-100 text-orange-700 dark:bg-orange-500/15 dark:text-orange-300 px-4 py-1.5 rounded-lg text-sm font-medium hover:bg-orange-200 dark:hover:bg-orange-500/25 disabled:opacity-50"
                      >
                        Revise
                      </button>
                    </div>
                  )}
                </div>

                {revisionId === a.id && (
                  <div className="mt-4 border-t border-border pt-4 space-y-3">
                    <h4 className="text-sm font-medium text-foreground">Request Revision</h4>
                    <textarea
                      value={revisionReason}
                      onChange={(e) => setRevisionReason(e.target.value)}
                      placeholder="Reason for revision..."
                      rows={2}
                      className="w-full resize-none text-sm border border-border rounded-lg px-3 py-2 bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                    <div className="space-y-2">
                      <p className="text-xs font-medium text-muted">Weight Override (optional)</p>
                      {["service_level", "inventory_cost", "stockout_risk", "working_capital"].map((kpi) => (
                        <div key={kpi} className="flex items-center gap-3">
                          <label className="text-xs text-muted w-36 capitalize">
                            {kpi.replace(/_/g, " ")}
                          </label>
                          <input
                            type="number"
                            min="0"
                            max="1"
                            step="0.01"
                            value={weights[kpi] ?? ""}
                            onChange={(e) => setWeights((p) => ({ ...p, [kpi]: e.target.value }))}
                            placeholder="0.0 – 1.0"
                            className="w-24 text-xs border border-border rounded px-2 py-1 bg-background text-foreground focus:outline-none focus:ring-1 focus:ring-blue-500"
                          />
                        </div>
                      ))}
                    </div>
                    <div className="flex gap-2">
                      <button
                        onClick={() => requestRevision(a.id)}
                        disabled={!revisionReason.trim() || actionId === a.id}
                        className="bg-orange-600 text-white px-4 py-1.5 rounded-lg text-sm font-medium hover:bg-orange-700 disabled:opacity-50"
                      >
                        Submit Revision
                      </button>
                      <button
                        onClick={() => { setRevisionId(null); setRevisionReason(""); setWeights({}); }}
                        className="text-sm text-muted hover:text-foreground px-3 py-1.5"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </main>
    </div>
  );
}
