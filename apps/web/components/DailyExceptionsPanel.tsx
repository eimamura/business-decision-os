"use client";

import { useState, useEffect, useCallback } from "react";
import { AlertTriangle, RefreshCw, MessageSquare, ShieldAlert, ShieldCheck } from "lucide-react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ScreeningException {
  domain: string;
  severity: string;
  sku_id: string | null;
  order_ref: string | null;
  headline_metric: string;
  detail: string;
}

interface ScreeningPayload {
  exceptions: ScreeningException[];
  counts: Record<string, number>;
  truncated: boolean;
  missing_data: string[];
}

interface ScreeningRun {
  id: string | null;
  run_date: string;
  triggered_by: string;
  status: string;
  exception_count: number | null;
  severity_counts: Record<string, number> | null;
  payload: ScreeningPayload | null;
  error: string | null;
  created_at: string;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const API_BASE = "";

const DEV_HEADERS: Record<string, string> = {
  "Content-Type": "application/json",
  "X-Dev-User": "dev-user",
};

const INVESTIGATE_PROMPT = "What exceptions require human judgment today?";

const MAX_EXCEPTIONS_SHOWN = 5;

const SEVERITY_ORDER: Record<string, number> = {
  critical: 4,
  high: 3,
  medium: 2,
  low: 1,
  info: 0,
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function severityBadgeClass(severity: string): string {
  switch (severity) {
    case "critical":
      return "bg-red-500/15 text-red-400 border border-red-500/25";
    case "high":
      return "bg-orange-500/15 text-orange-400 border border-orange-500/25";
    case "medium":
      return "bg-amber-500/15 text-amber-400 border border-amber-500/25";
    default:
      return "bg-white/8 text-white/40 border border-white/10";
  }
}

function formatRunDate(runDate: string): string {
  try {
    const d = new Date(runDate + "T00:00:00Z");
    return d.toLocaleDateString("en-US", {
      weekday: "short",
      month: "short",
      day: "numeric",
      timeZone: "UTC",
    });
  } catch {
    return runDate;
  }
}

function subjectLabel(ex: ScreeningException): string {
  if (ex.sku_id) return ex.sku_id;
  if (ex.order_ref) return `#${ex.order_ref}`;
  return ex.domain;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface DailyExceptionsPanelProps {
  onInvestigate: (prompt: string) => void;
}

export default function DailyExceptionsPanel({
  onInvestigate,
}: DailyExceptionsPanelProps): React.JSX.Element | null {
  const [run, setRun] = useState<ScreeningRun | null | undefined>(undefined);
  const [runNowPending, setRunNowPending] = useState(false);
  const [fetchError, setFetchError] = useState(false);

  const fetchToday = useCallback(async (): Promise<void> => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/screenings/today`, {
        headers: DEV_HEADERS,
      });
      if (!res.ok) {
        setFetchError(true);
        return;
      }
      const data = (await res.json()) as { run: ScreeningRun | null };
      setRun(data.run);
      setFetchError(false);
    } catch {
      setFetchError(true);
    }
  }, []);

  useEffect(() => {
    void fetchToday();
  }, [fetchToday]);

  const handleRunNow = useCallback(async (): Promise<void> => {
    if (runNowPending) return;
    setRunNowPending(true);
    try {
      const res = await fetch(`${API_BASE}/api/v1/screenings/run`, {
        method: "POST",
        headers: DEV_HEADERS,
      });
      if (res.ok) {
        const data = (await res.json()) as { run: ScreeningRun };
        setRun(data.run);
        setFetchError(false);
      } else {
        // Refetch even on error — a previous run might now exist
        await fetchToday();
      }
    } catch {
      await fetchToday();
    } finally {
      setRunNowPending(false);
    }
  }, [runNowPending, fetchToday]);

  // Still loading: render nothing (avoids layout shift)
  if (run === undefined) return null;

  // Fetch failed silently: render nothing
  if (fetchError) return null;

  // -------------------------------------------------------------------------
  // Shared button classes
  // -------------------------------------------------------------------------

  const runNowClass =
    "flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border border-white/10 bg-white/4 text-white/50 hover:bg-indigo-500/15 hover:border-indigo-500/30 hover:text-indigo-300 disabled:opacity-40 disabled:cursor-not-allowed transition-colors";

  // -------------------------------------------------------------------------
  // Empty state — no run for today
  // -------------------------------------------------------------------------

  if (run === null) {
    return (
      <div
        data-testid="daily-exceptions-panel"
        className="rounded-xl border border-white/8 bg-white/[0.02] px-4 py-3 flex items-center justify-between gap-4"
      >
        <div
          data-testid="daily-exceptions-empty"
          className="flex items-center gap-2 text-sm text-white/40"
        >
          <ShieldCheck size={15} className="shrink-0 text-white/25" />
          <span>No screening run yet today. Run now to surface exceptions.</span>
        </div>
        <button
          data-testid="daily-exceptions-run-now"
          onClick={() => void handleRunNow()}
          disabled={runNowPending}
          className={runNowClass}
        >
          <RefreshCw
            size={12}
            className={runNowPending ? "animate-spin" : ""}
          />
          {runNowPending ? "Running…" : "Run now"}
        </button>
      </div>
    );
  }

  // -------------------------------------------------------------------------
  // Panel with run data
  // -------------------------------------------------------------------------

  const severityCounts = run.severity_counts ?? {};
  const criticalCount = severityCounts["critical"] ?? 0;
  const highCount = severityCounts["high"] ?? 0;
  const mediumCount = severityCounts["medium"] ?? 0;

  const exceptionList: ScreeningException[] = run.payload?.exceptions ?? [];
  const topExceptions = [...exceptionList]
    .sort(
      (a, b) =>
        (SEVERITY_ORDER[b.severity] ?? 0) - (SEVERITY_ORDER[a.severity] ?? 0)
    )
    .slice(0, MAX_EXCEPTIONS_SHOWN);

  const hasExceptions = topExceptions.length > 0;
  const totalCount = run.exception_count ?? 0;
  const truncated = run.payload?.truncated ?? false;

  return (
    <div
      data-testid="daily-exceptions-panel"
      className="rounded-xl border border-white/8 bg-white/[0.02] overflow-hidden"
    >
      {/* Header row */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-white/6">
        <div className="flex items-center gap-2">
          <AlertTriangle size={13} className="shrink-0 text-amber-400/70" />
          <span className="text-xs font-semibold text-white/70">
            Daily Exceptions
          </span>
          <span className="text-xs text-white/30">
            {formatRunDate(run.run_date)}
          </span>
        </div>

        {/* Severity count badges */}
        <div className="flex items-center gap-1.5">
          {criticalCount > 0 && (
            <span className={`text-xs font-medium px-1.5 py-0.5 rounded ${severityBadgeClass("critical")}`}>
              {criticalCount} critical
            </span>
          )}
          {highCount > 0 && (
            <span className={`text-xs font-medium px-1.5 py-0.5 rounded ${severityBadgeClass("high")}`}>
              {highCount} high
            </span>
          )}
          {mediumCount > 0 && (
            <span className={`text-xs font-medium px-1.5 py-0.5 rounded ${severityBadgeClass("medium")}`}>
              {mediumCount} medium
            </span>
          )}
          {totalCount === 0 && (
            <span className="text-xs text-white/30">
              <ShieldCheck size={13} className="inline mr-1 opacity-60" />
              No exceptions
            </span>
          )}
        </div>
      </div>

      {/* Exception rows */}
      {hasExceptions && (
        <div className="divide-y divide-white/4">
          {topExceptions.map((ex, idx) => (
            <div
              key={idx}
              className="flex items-start gap-3 px-4 py-2"
            >
              {/* Severity pill */}
              <span
                className={`shrink-0 mt-0.5 text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded ${severityBadgeClass(ex.severity)}`}
              >
                {ex.severity}
              </span>
              {/* Content */}
              <div className="flex-1 min-w-0">
                <span className="text-xs text-white/55 font-medium mr-1.5">
                  {subjectLabel(ex)}
                </span>
                <span className="text-xs text-white/35 truncate">
                  {ex.headline_metric}
                </span>
              </div>
              {/* Domain tag */}
              <span className="shrink-0 text-[10px] text-white/25">
                {ex.domain.replace(/_/g, " ")}
              </span>
            </div>
          ))}
          {(truncated || totalCount > MAX_EXCEPTIONS_SHOWN) && (
            <div className="px-4 py-1.5 text-[10px] text-white/25">
              +{totalCount - MAX_EXCEPTIONS_SHOWN} more — use Investigate to see full list
            </div>
          )}
        </div>
      )}

      {/* Footer action bar */}
      <div className="flex items-center justify-between px-4 py-2 border-t border-white/6 bg-white/[0.01]">
        <button
          data-testid="daily-exceptions-run-now"
          onClick={() => void handleRunNow()}
          disabled={runNowPending}
          className={runNowClass}
        >
          <RefreshCw
            size={12}
            className={runNowPending ? "animate-spin" : ""}
          />
          {runNowPending ? "Running…" : "Run now"}
        </button>

        {hasExceptions && (
          <button
            data-testid="daily-exceptions-investigate"
            onClick={() => onInvestigate(INVESTIGATE_PROMPT)}
            className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg bg-indigo-600/80 text-white border border-indigo-500/40 hover:bg-indigo-500 transition-colors"
          >
            <MessageSquare size={12} />
            Investigate in chat
          </button>
        )}
      </div>
    </div>
  );
}
