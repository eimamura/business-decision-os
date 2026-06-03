"use client";

import { useEffect, useState } from "react";
import type { AgentNodeState, AgentNodeToolCall } from "@/types/chat";

interface AgentNodeCardProps {
  node: AgentNodeState;
}

function formatMs(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function StatusBadge({ status }: { status: "running" | "completed" | "error" }): React.JSX.Element {
  if (status === "running") {
    return (
      <span className="flex items-center gap-1 text-xs text-blue-400">
        <span className="inline-block w-2 h-2 rounded-full bg-blue-400 animate-pulse" />
        Running...
      </span>
    );
  }
  if (status === "completed") {
    return (
      <span className="flex items-center gap-1 text-xs text-green-400">
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
          <path d="M2 6l3 3 5-5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        Done
      </span>
    );
  }
  return (
    <span className="flex items-center gap-1 text-xs text-red-400">
      <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
        <path d="M3 3l6 6M9 3l-6 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
      Error
    </span>
  );
}

function ToolCallRow({ toolCall }: { toolCall: AgentNodeToolCall }): React.JSX.Element {
  return (
    <div className="flex items-center gap-2 py-1 pl-2 text-xs text-white/60">
      <svg width="11" height="11" viewBox="0 0 11 11" fill="none" aria-hidden="true" className="shrink-0 text-white/30">
        <rect x="1" y="4" width="9" height="6" rx="1" stroke="currentColor" strokeWidth="1.2" />
        <path d="M3.5 4V2.5a2 2 0 014 0V4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
      </svg>
      <span className="truncate">{toolCall.toolName}</span>
      <StatusBadge status={toolCall.status} />
      {toolCall.durationMs !== undefined && (
        <span className="ml-auto shrink-0 text-white/30">{formatMs(toolCall.durationMs)}</span>
      )}
    </div>
  );
}

export function AgentNodeCard({ node }: AgentNodeCardProps): React.JSX.Element {
  const [expanded, setExpanded] = useState(node.status === "running");
  const [elapsedMs, setElapsedMs] = useState<number>(0);

  useEffect(() => {
    if (node.status === "completed") {
      setExpanded(false);
    }
  }, [node.status]);

  useEffect(() => {
    if (node.status !== "running") return;
    const start = Date.parse(node.startedAt);
    const tick = (): void => {
      setElapsedMs(Date.now() - start);
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [node.status, node.startedAt]);

  const displayMs = node.status === "completed" ? node.durationMs : elapsedMs;

  return (
    <div
      data-testid="agent-node-card"
      className="border border-white/10 rounded-lg p-3 bg-white/[0.02] transition-all"
    >
      {/* Header row */}
      <div
        className={`flex items-center justify-between gap-2 ${node.status === "completed" ? "cursor-pointer" : ""}`}
        onClick={() => {
          if (node.status === "completed") setExpanded((p) => !p);
        }}
        role={node.status === "completed" ? "button" : undefined}
        tabIndex={node.status === "completed" ? 0 : undefined}
        onKeyDown={(e) => {
          if (node.status === "completed" && (e.key === "Enter" || e.key === " ")) {
            e.preventDefault();
            setExpanded((p) => !p);
          }
        }}
      >
        <div className="flex flex-col gap-0.5 min-w-0">
          <span className="text-sm font-semibold text-white/85 truncate">{node.agentName}</span>
          <span className="text-xs text-white/40 truncate">{node.agentRole}</span>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {displayMs !== undefined && (
            <span className="text-xs text-white/30">{formatMs(displayMs)}</span>
          )}
          <span data-testid="agent-node-card-status">
            <StatusBadge status={node.status} />
          </span>
        </div>
      </div>

      {/* Tool list */}
      {expanded && node.toolCalls.length > 0 && (
        <div className="mt-2 border-t border-white/8 pt-2 space-y-0.5">
          {node.toolCalls.map((t) => (
            <ToolCallRow key={t.toolCallId} toolCall={t} />
          ))}
        </div>
      )}
    </div>
  );
}
