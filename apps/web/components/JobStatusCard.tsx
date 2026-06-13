"use client";

import { useEffect, useRef, useState } from "react";

const DEV_HEADERS: Record<string, string> = {
  "Content-Type": "application/json",
  "X-Dev-User": "dev-user",
};

const POLL_INTERVAL_MS = 2000;
const TERMINAL_STATUSES = new Set(["completed", "failed", "cancelled"]);

type JobStatus = "queued" | "running" | "completed" | "failed" | "cancelled";

const STATUS_LABELS: Record<JobStatus, string> = {
  queued: "Queued",
  running: "Running",
  completed: "Completed",
  failed: "Failed",
  cancelled: "Cancelled",
};

const STATUS_COLORS: Record<JobStatus, string> = {
  queued: "text-amber-400",
  running: "text-indigo-400",
  completed: "text-emerald-400",
  failed: "text-red-400",
  cancelled: "text-muted",
};

export interface JobStatusCardProps {
  jobId: string;
  jobType: string;
  initialStatus: JobStatus;
  /** Called when job reaches a terminal status so the chat can reload messages. */
  onJobComplete?: () => void;
}

export default function JobStatusCard({
  jobId,
  jobType,
  initialStatus,
  onJobComplete,
}: JobStatusCardProps): React.JSX.Element {
  const [status, setStatus] = useState<JobStatus>(initialStatus);
  const onJobCompleteRef = useRef(onJobComplete);
  onJobCompleteRef.current = onJobComplete;
  const calledCompleteRef = useRef(false);

  useEffect(() => {
    if (TERMINAL_STATUSES.has(initialStatus)) {
      return;
    }

    let cancelled = false;

    async function poll(): Promise<void> {
      while (!cancelled) {
        await new Promise<void>((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
        if (cancelled) break;

        try {
          const res = await fetch(`/api/v1/jobs/${jobId}`, { headers: DEV_HEADERS });
          if (!res.ok) break;
          const data = await res.json() as { status?: string };
          const next = (data.status ?? "queued") as JobStatus;
          if (!cancelled) {
            setStatus(next);
            if (TERMINAL_STATUSES.has(next)) {
              if (!calledCompleteRef.current) {
                calledCompleteRef.current = true;
                onJobCompleteRef.current?.();
              }
              break;
            }
          }
        } catch {
          // Polling failure is non-fatal — retry next interval
        }
      }
    }

    void poll();
    return () => {
      cancelled = true;
    };
  }, [jobId, initialStatus]);

  const isTerminal = TERMINAL_STATUSES.has(status);
  const isRunning = status === "running" || status === "queued";

  return (
    <div
      data-testid="job-status-card"
      className="rounded-xl border border-border bg-surface px-4 py-3 max-w-md w-full"
    >
      <div className="flex items-center gap-2 mb-1">
        <span className="text-xs font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full bg-indigo-500/15 text-indigo-400 border border-indigo-500/25">
          {jobType}
        </span>
        <span className="text-xs text-muted font-mono truncate">
          {jobId.slice(0, 8)}
        </span>
      </div>

      <div className="flex items-center gap-2 mt-2">
        {isRunning && (
          <span className="flex gap-0.5">
            <span
              className="w-1 h-1 bg-indigo-400 rounded-full animate-bounce"
              style={{ animationDelay: "0ms" }}
            />
            <span
              className="w-1 h-1 bg-indigo-400 rounded-full animate-bounce"
              style={{ animationDelay: "150ms" }}
            />
            <span
              className="w-1 h-1 bg-indigo-400 rounded-full animate-bounce"
              style={{ animationDelay: "300ms" }}
            />
          </span>
        )}
        {isTerminal && status === "completed" && (
          <span className="text-emerald-400" aria-hidden="true">&#10003;</span>
        )}
        {isTerminal && status === "failed" && (
          <span className="text-red-400" aria-hidden="true">&#x2715;</span>
        )}
        <span
          data-testid="job-status-value"
          className={`text-sm font-medium ${STATUS_COLORS[status]}`}
        >
          {STATUS_LABELS[status]}
        </span>
      </div>
    </div>
  );
}
