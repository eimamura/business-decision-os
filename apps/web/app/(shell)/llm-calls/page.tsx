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
  return "bg-surface text-muted";
}

function PromptPanel({ raw }: { raw: string | null }): React.ReactElement {
  if (raw === null) {
    return <p className="text-xs text-muted italic">(no prompt captured)</p>;
  }
  const parsed = safeParse(raw);
  if (!Array.isArray(parsed)) {
    return (
      <pre className="text-xs bg-gray-900 text-green-300 rounded p-3 overflow-x-auto whitespace-pre-wrap max-h-96 overflow-y-auto">
        {raw}
      </pre>
    );
  }
  const messages = parsed as LlmMessageBlock[];
  return (
    <div className="space-y-2">
      {messages.map((msg, i) => (
        <div key={i} className="rounded border border-border overflow-hidden">
          <div className={`px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${roleBadgeClass(msg.role)}`}>
            {msg.role}
          </div>
          <pre className="text-xs bg-gray-900 text-green-200 p-3 overflow-x-auto whitespace-pre-wrap max-h-96 overflow-y-auto">
            {typeof msg.content === "string" ? msg.content : JSON.stringify(msg.content, null, 2)}
          </pre>
        </div>
      ))}
    </div>
  );
}

function ResponsePanel({ responseText, toolCallsJson }: { responseText: string | null; toolCallsJson: string | null }): React.ReactElement {
  return (
    <div className="space-y-3">
      {responseText !== null ? (
        <pre className="text-xs bg-gray-900 text-blue-200 rounded p-3 overflow-x-auto whitespace-pre-wrap max-h-96 overflow-y-auto">
          {responseText}
        </pre>
      ) : (
        <p className="text-xs text-muted italic">(no response captured)</p>
      )}
      {toolCallsJson !== null && (
        <div>
          <p className="text-xs font-semibold text-muted mb-1">Tool Calls</p>
          <pre className="text-xs bg-gray-900 text-yellow-200 rounded p-3 overflow-x-auto whitespace-pre-wrap max-h-64 overflow-y-auto">
            {safeFormatJson(toolCallsJson)}
          </pre>
        </div>
      )}
    </div>
  );
}

export default function LlmCallsPage(): React.ReactElement {
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

  const totalCalls = rows.length;
  const avgLatency = rows.length > 0
    ? Math.round(rows.reduce((s, r) => s + (r.latency_ms ?? 0), 0) / rows.length)
    : 0;
  const totalTokens = rows.reduce((s, r) => s + r.input_tokens + r.output_tokens, 0);
  const totalCost = rows.reduce((s, r) => s + r.total_cost_usd, 0);

  return (
    <div className="min-h-screen bg-background">
      <header className="bg-background border-b border-border px-6 py-4">
        <h1 className="text-lg font-semibold text-foreground">LLM Calls</h1>
        <p className="text-xs text-muted mt-0.5">Last 100 LLM calls — compare prompts and responses for context debugging</p>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8 space-y-6">
        <div className="grid grid-cols-4 gap-4">
          <div className="bg-background rounded-xl border border-border p-4 text-center">
            <p className="text-xs text-muted mb-1">Total Calls</p>
            <p className="text-lg font-semibold text-foreground">{totalCalls.toLocaleString()}</p>
          </div>
          <div className="bg-background rounded-xl border border-border p-4 text-center">
            <p className="text-xs text-muted mb-1">Avg Latency</p>
            <p className="text-lg font-semibold text-foreground">{avgLatency.toLocaleString()} ms</p>
          </div>
          <div className="bg-background rounded-xl border border-border p-4 text-center">
            <p className="text-xs text-muted mb-1">Total Tokens</p>
            <p className="text-lg font-semibold text-foreground">{totalTokens.toLocaleString()}</p>
          </div>
          <div className="bg-background rounded-xl border border-border p-4 text-center">
            <p className="text-xs text-muted mb-1">Total Cost</p>
            <p className="text-lg font-semibold text-foreground">
              {new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 4 }).format(totalCost)}
            </p>
          </div>
        </div>

        {isLoading ? (
          <div className="space-y-3">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="h-12 bg-surface rounded-xl animate-pulse" />
            ))}
          </div>
        ) : rows.length === 0 ? (
          <div className="text-center py-16 text-muted">
            <p>No LLM calls recorded yet.</p>
          </div>
        ) : (
          <div className="bg-background rounded-xl border border-border overflow-hidden">
            <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-surface">
              <span className="text-xs text-muted">{rows.length} calls</span>
              <button
                onClick={toggleAll}
                className="text-xs text-blue-600 dark:text-blue-400 hover:underline font-medium"
              >
                {allExpanded ? "Collapse All" : "Expand All"}
              </button>
            </div>
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-surface border-b border-border">
                  <th className="text-left px-4 py-3 font-medium text-muted">Time</th>
                  <th className="text-left px-4 py-3 font-medium text-muted">Role</th>
                  <th className="text-left px-4 py-3 font-medium text-muted">Step Type</th>
                  <th className="text-left px-4 py-3 font-medium text-muted">Model</th>
                  <th className="text-right px-4 py-3 font-medium text-muted">Tools</th>
                  <th className="text-right px-4 py-3 font-medium text-muted">Tok In</th>
                  <th className="text-right px-4 py-3 font-medium text-muted">Tok Out</th>
                  <th className="text-right px-4 py-3 font-medium text-muted">Latency</th>
                  <th className="text-right px-4 py-3 font-medium text-muted">Cost</th>
                  <th className="text-center px-4 py-3 font-medium text-muted">Expand</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {rows.map((r: LlmUsageRow) => (
                  <>
                    <tr
                      key={r.id}
                      className="hover:bg-surface transition-colors cursor-pointer"
                      onClick={() => toggleExpanded(r.id)}
                    >
                      <td className="px-4 py-2.5 text-xs text-muted font-mono whitespace-nowrap">
                        {new Date(r.created_at).toLocaleString()}
                      </td>
                      <td className="px-4 py-2.5 text-xs text-foreground">{r.specialist_role ?? "-"}</td>
                      <td className="px-4 py-2.5 text-xs text-muted font-mono">{r.step_type ?? "-"}</td>
                      <td className="px-4 py-2.5 text-xs text-muted font-mono">{r.model ?? "-"}</td>
                      <td className="px-4 py-2.5 text-xs text-right font-mono">
                        {toolCallCount(r.tool_calls_json) > 0 ? (
                          <span className="text-yellow-600 dark:text-yellow-400 font-semibold">
                            {toolCallCount(r.tool_calls_json)}
                          </span>
                        ) : (
                          <span className="text-muted">—</span>
                        )}
                      </td>
                      <td className="px-4 py-2.5 text-xs text-right text-muted font-mono">
                        {r.input_tokens.toLocaleString()}
                      </td>
                      <td className="px-4 py-2.5 text-xs text-right text-muted font-mono">
                        {r.output_tokens.toLocaleString()}
                      </td>
                      <td className="px-4 py-2.5 text-xs text-right text-muted font-mono">
                        {r.latency_ms != null ? `${r.latency_ms.toLocaleString()} ms` : "-"}
                      </td>
                      <td className="px-4 py-2.5 text-xs text-right text-muted font-mono">
                        {new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 4 }).format(r.total_cost_usd)}
                      </td>
                      <td className="px-4 py-2.5 text-center">
                        <span className="text-xs text-blue-600 dark:text-blue-400 select-none">
                          {expanded.has(r.id) ? "▲" : "▼"}
                        </span>
                      </td>
                    </tr>
                    {expanded.has(r.id) && (
                      <tr key={`${r.id}-detail`} className="bg-surface">
                        <td colSpan={10} className="px-5 py-4">
                          <div className="grid grid-cols-2 gap-4">
                            <div>
                              <p className="text-xs font-semibold text-muted mb-2">Prompt</p>
                              <PromptPanel raw={r.prompt_messages_json} />
                            </div>
                            <div>
                              <p className="text-xs font-semibold text-muted mb-2">Response</p>
                              <ResponsePanel responseText={r.response_text} toolCallsJson={r.tool_calls_json} />
                            </div>
                          </div>
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
