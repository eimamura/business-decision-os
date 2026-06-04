"use client";

import { useState, useMemo } from "react";
import { useLlmCalls } from "@/features/usage/hooks";
import type { LlmUsageRow } from "@/features/usage/api";

interface LlmMessageBlock {
  role: string;
  content: string | unknown;
}

function safeParse(raw: string | null): unknown {
  if (raw === null) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function safeFormatJson(raw: string): string {
  try {
    return JSON.stringify(JSON.parse(raw), null, 2);
  } catch {
    return raw;
  }
}

function toolCallCount(raw: string | null): number {
  if (raw === null) return 0;
  const parsed = safeParse(raw);
  return Array.isArray(parsed) ? parsed.length : 0;
}

function roleBadgeClass(role: string): string {
  if (role === "system") return "bg-green-100 text-green-700 dark:bg-green-500/15 dark:text-green-300";
  if (role === "user") return "bg-blue-100 text-blue-700 dark:bg-blue-500/15 dark:text-blue-300";
  return "bg-surface text-muted dark:text-white/40";
}

function PromptDetail({ raw }: { raw: string | null }): React.ReactElement {
  if (raw === null) return <p className="text-[10px] text-muted italic">(none)</p>;
  const parsed = safeParse(raw);
  if (!Array.isArray(parsed)) {
    return (
      <pre className="text-[10px] bg-gray-900 text-green-300 rounded p-2 whitespace-pre-wrap max-h-48 overflow-y-auto">
        {raw}
      </pre>
    );
  }
  const messages = parsed as LlmMessageBlock[];
  return (
    <div className="space-y-1.5">
      {messages.map((msg, i) => (
        <div key={i} className="rounded overflow-hidden border border-white/8">
          <div className={`px-1.5 py-px text-[9px] font-semibold uppercase tracking-wide ${roleBadgeClass(msg.role)}`}>
            {msg.role}
          </div>
          <pre className="text-[10px] bg-gray-900 text-green-200 px-2 py-1.5 whitespace-pre-wrap max-h-40 overflow-y-auto">
            {typeof msg.content === "string" ? msg.content : JSON.stringify(msg.content, null, 2)}
          </pre>
        </div>
      ))}
    </div>
  );
}

function ResponseDetail({ responseText, toolCallsJson }: { responseText: string | null; toolCallsJson: string | null }): React.ReactElement {
  return (
    <div className="space-y-2">
      {responseText !== null ? (
        <pre className="text-[10px] bg-gray-900 text-blue-200 rounded p-2 whitespace-pre-wrap max-h-48 overflow-y-auto">
          {responseText}
        </pre>
      ) : (
        <p className="text-[10px] text-muted italic">(none)</p>
      )}
      {toolCallsJson !== null && (
        <div>
          <p className="text-[10px] font-semibold text-muted mb-1">Tool Calls</p>
          <pre className="text-[10px] bg-gray-900 text-yellow-200 rounded p-2 whitespace-pre-wrap max-h-40 overflow-y-auto">
            {safeFormatJson(toolCallsJson)}
          </pre>
        </div>
      )}
    </div>
  );
}

export default function LlmCallsPanel(): React.ReactElement {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const { data: rows = [], isLoading } = useLlmCalls();

  const allExpanded = useMemo(
    () => rows.length > 0 && rows.every((r) => expanded.has(r.id)),
    [rows, expanded],
  );

  function toggleExpanded(id: string): void {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleAll(): void {
    if (allExpanded) {
      setExpanded(new Set());
    } else {
      setExpanded(new Set(rows.map((r) => r.id)));
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="shrink-0 flex items-center justify-between px-4 py-3 border-b border-border dark:border-white/8">
        <span className="text-xs font-semibold text-foreground dark:text-white/80">
          LLM Calls
          {rows.length > 0 && (
            <span className="ml-1.5 text-muted dark:text-white/30 font-normal">({rows.length})</span>
          )}
        </span>
        {rows.length > 0 && (
          <button
            onClick={toggleAll}
            className="text-[10px] text-blue-600 dark:text-blue-400 hover:underline font-medium"
          >
            {allExpanded ? "Collapse All" : "Expand All"}
          </button>
        )}
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto custom-scrollbar">
        {isLoading ? (
          <div className="p-3 space-y-2">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-10 bg-surface dark:bg-white/5 rounded animate-pulse" />
            ))}
          </div>
        ) : rows.length === 0 ? (
          <div className="flex items-center justify-center h-full text-xs text-muted dark:text-white/30 p-6 text-center">
            No LLM calls recorded yet.
          </div>
        ) : (
          <div className="divide-y divide-border dark:divide-white/5">
            {rows.map((r: LlmUsageRow) => {
              const tc = toolCallCount(r.tool_calls_json);
              const isOpen = expanded.has(r.id);
              return (
                <div key={r.id}>
                  <button
                    onClick={() => toggleExpanded(r.id)}
                    className="w-full text-left px-3 py-2.5 hover:bg-surface dark:hover:bg-white/4 transition-colors"
                  >
                    <div className="flex items-start justify-between gap-1">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-1.5 flex-wrap">
                          <span className="text-[10px] font-medium text-foreground dark:text-white/75 truncate max-w-[100px]">
                            {r.specialist_role ?? "—"}
                          </span>
                          {r.step_type && (
                            <span className="text-[9px] font-mono text-muted dark:text-white/30 bg-surface dark:bg-white/6 px-1 rounded">
                              {r.step_type}
                            </span>
                          )}
                          {tc > 0 && (
                            <span className="text-[9px] font-semibold text-yellow-600 dark:text-yellow-400">
                              {tc} tool{tc > 1 ? "s" : ""}
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-2 mt-0.5">
                          <span className="text-[10px] font-mono text-muted dark:text-white/30 truncate">
                            {r.model ?? "—"}
                          </span>
                          <span className="text-[10px] text-muted dark:text-white/25">
                            {(r.input_tokens + r.output_tokens).toLocaleString()} tok
                          </span>
                        </div>
                      </div>
                      <div className="shrink-0 flex flex-col items-end gap-0.5">
                        <span className="text-[9px] font-mono text-muted dark:text-white/25">
                          {r.latency_ms != null ? `${r.latency_ms} ms` : "—"}
                        </span>
                        <span className="text-[9px] text-blue-500 dark:text-blue-400">{isOpen ? "▲" : "▼"}</span>
                      </div>
                    </div>
                    <div className="text-[9px] text-muted dark:text-white/20 font-mono mt-0.5">
                      {new Date(r.created_at).toLocaleString()}
                    </div>
                  </button>

                  {isOpen && (
                    <div className="px-3 pb-3 space-y-3 bg-surface dark:bg-[#070B14]">
                      <div>
                        <p className="text-[10px] font-semibold text-muted dark:text-white/40 mb-1.5">Prompt</p>
                        <PromptDetail raw={r.prompt_messages_json} />
                      </div>
                      <div>
                        <p className="text-[10px] font-semibold text-muted dark:text-white/40 mb-1.5">Response</p>
                        <ResponseDetail responseText={r.response_text} toolCallsJson={r.tool_calls_json} />
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
