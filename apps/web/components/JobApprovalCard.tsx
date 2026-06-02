"use client";

import { useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const DEV_HEADERS: Record<string, string> = {
  "Content-Type": "application/json",
  "X-Dev-User": "dev-user",
};

const MAX_PARAMS_SHOWN = 5;
const MAX_VALUE_LENGTH = 60;

type DecisionState = "idle" | "loading" | "approved" | "rejected" | "error";

export interface JobApprovalCardProps {
  approvalId: string;
  jobId: string | null;
  jobType: string;
  description: string;
  params: Record<string, unknown>;
  onDecision?: (decision: "approved" | "rejected") => void;
}

function truncate(value: string, maxLen: number): string {
  return value.length > maxLen ? `${value.slice(0, maxLen)}…` : value;
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "string") return truncate(value, MAX_VALUE_LENGTH);
  return truncate(JSON.stringify(value), MAX_VALUE_LENGTH);
}

export default function JobApprovalCard({
  approvalId,
  jobId,
  jobType,
  description,
  params,
  onDecision,
}: JobApprovalCardProps): React.JSX.Element {
  const [state, setState] = useState<DecisionState>("idle");
  const [errorMsg, setErrorMsg] = useState<string>("");

  const paramEntries = Object.entries(params).slice(0, MAX_PARAMS_SHOWN);
  const isDone = state === "approved" || state === "rejected";

  async function handleDecision(decision: "approved" | "rejected"): Promise<void> {
    setState("loading");
    setErrorMsg("");
    try {
      const res = await fetch(
        `${API_BASE}/api/v1/approvals/${approvalId}/decision`,
        {
          method: "POST",
          headers: DEV_HEADERS,
          body: JSON.stringify({ decision }),
        },
      );
      if (!res.ok) {
        const text = await res.text().catch(() => "");
        throw new Error(`Request failed (${res.status})${text ? `: ${text}` : ""}`);
      }
      setState(decision);
      onDecision?.(decision);
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "An unexpected error occurred.";
      setErrorMsg(message);
      setState("error");
    }
  }

  return (
    <div
      data-testid="job-approval-card"
      className={`rounded-xl border border-border bg-surface px-4 py-3 max-w-md w-full transition-opacity ${
        isDone ? "opacity-60" : ""
      }`}
    >
      {/* Header row: badge + title */}
      <div className="flex items-center gap-2 mb-2">
        <span className="text-xs font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full bg-indigo-500/15 text-indigo-400 border border-indigo-500/25">
          {jobType}
        </span>
        <span className="text-xs text-muted">
          {jobId ? `Job #${jobId.slice(0, 8)}` : "Pending job"}
        </span>
      </div>

      {/* Description */}
      <p className="text-sm text-foreground font-medium mb-3 leading-snug">{description}</p>

      {/* Params table */}
      {paramEntries.length > 0 && (
        <div className="mb-3 rounded-lg bg-background border border-border overflow-hidden">
          <table className="w-full text-xs">
            <tbody>
              {paramEntries.map(([key, value]) => (
                <tr key={key} className="border-b border-border last:border-b-0">
                  <td className="px-3 py-1.5 text-muted font-medium w-1/3 align-top">
                    {key}
                  </td>
                  <td className="px-3 py-1.5 text-foreground font-mono break-all">
                    {formatValue(value)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Decision outcome */}
      {state === "approved" && (
        <p data-testid="approval-status" className="text-sm font-medium text-emerald-400">Approved</p>
      )}
      {state === "rejected" && (
        <p data-testid="approval-status" className="text-sm font-medium text-red-400">Rejected</p>
      )}

      {/* Error message */}
      {state === "error" && (
        <p className="text-xs text-red-400 mb-2">{errorMsg}</p>
      )}

      {/* Action buttons — hidden once a decision is final */}
      {!isDone && (
        <div className="flex gap-2">
          <button
            data-testid="approve-btn"
            onClick={() => void handleDecision("approved")}
            disabled={state === "loading"}
            className="flex-1 bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-medium px-3 py-1.5 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {state === "loading" ? "…" : "Approve"}
          </button>
          <button
            data-testid="reject-btn"
            onClick={() => void handleDecision("rejected")}
            disabled={state === "loading"}
            className="flex-1 bg-red-600 hover:bg-red-700 text-white text-sm font-medium px-3 py-1.5 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {state === "loading" ? "…" : "Reject"}
          </button>
        </div>
      )}
    </div>
  );
}
