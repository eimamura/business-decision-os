"use client";

import { useState } from "react";
import { useAgentProgress } from "@/hooks/useAgentProgress";
import { AgentNodeCard } from "@/components/AgentNodeCard";

interface ExecutionProgressPanelProps {
  sessionId: string;
}

export function ExecutionProgressPanel({ sessionId }: ExecutionProgressPanelProps): React.JSX.Element | null {
  const { nodes, executionMode, isRunning } = useAgentProgress(sessionId);
  const [summaryExpanded, setSummaryExpanded] = useState(false);

  if (nodes.length === 0 && !isRunning) {
    return null;
  }

  const showSummary = !isRunning && nodes.length > 0;

  return (
    <div data-testid="execution-progress-panel" className="px-4 py-3 space-y-2">
      {isRunning && (
        <p className="text-xs font-medium text-white/50 uppercase tracking-wide">
          Executing &middot; {executionMode ?? "Processing"}
        </p>
      )}

      {isRunning && (
        <div className="space-y-2">
          {nodes.map((node) => (
            <AgentNodeCard node={node} key={node.taskId} />
          ))}
        </div>
      )}

      {showSummary && (
        <div data-testid="execution-progress-panel-summary">
          <button
            onClick={() => setSummaryExpanded((p) => !p)}
            className="flex items-center gap-1.5 text-xs text-green-400 hover:text-green-300 transition-colors"
          >
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
              <path d="M2 6l3 3 5-5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            {nodes.length} agent{nodes.length > 1 ? "s" : ""} completed
            <svg
              width="10"
              height="10"
              viewBox="0 0 10 10"
              fill="none"
              aria-hidden="true"
              className={`transition-transform ${summaryExpanded ? "rotate-180" : ""}`}
            >
              <path d="M2 3.5l3 3 3-3" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
          {summaryExpanded && (
            <div className="mt-2 space-y-2">
              {nodes.map((node) => (
                <AgentNodeCard node={node} key={node.taskId} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
