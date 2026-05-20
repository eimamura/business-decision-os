"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import Link from "next/link";
import ReasoningPanel from "./components/ReasoningPanel";
import MessageBubble from "@/components/MessageBubble";
import { useChat } from "@/hooks/useChat";
import { fetchSessions } from "@/lib/api";
import type { Session } from "@/types/chat";

interface ChatPageProps {
  params: { sessionId: string };
}

export default function ChatPage({ params }: ChatPageProps) {
  const { sessionId } = params;
  const [sessions, setSessions] = useState<Session[]>([]);
  const [input, setInput] = useState("");
  const [showReasoning, setShowReasoning] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const { messages, isSending, usage, loadMessages, sendMessage, submitFeedback } = useChat(sessionId);

  useEffect(() => {
    fetchSessions()
      .then(setSessions)
      .catch(() => setSessions([]));

    loadMessages();
  }, [sessionId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === ".") {
        e.preventDefault();
        setShowReasoning((p) => !p);
      }
    }
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, []);

  const handleSend = useCallback(async () => {
    const text = input.trim();
    if (!text || isSending) return;
    setInput("");
    await sendMessage(text);
  }, [input, isSending, sendMessage]);

  return (
    <div className="flex h-screen bg-gray-50 overflow-hidden">
      <aside className="w-56 shrink-0 bg-white border-r border-gray-200 flex flex-col">
        <div className="px-4 py-3 border-b border-gray-200">
          <Link href="/chat" className="text-sm font-semibold text-gray-900 hover:text-blue-600">
            Business Decision OS
          </Link>
        </div>
        <div className="flex-1 overflow-y-auto py-2">
          {sessions.map((s) => (
            <Link
              key={s.session_id}
              href={`/chat/${s.session_id}`}
              className={`block px-4 py-2.5 text-xs hover:bg-gray-50 ${
                s.session_id === sessionId ? "bg-blue-50 text-blue-700 font-medium" : "text-gray-700"
              }`}
            >
              <span className="block truncate">{s.goal ?? "Session"}</span>
              <span className="text-gray-400 mt-0.5 block">
                {new Date(s.created_at).toLocaleDateString()}
              </span>
            </Link>
          ))}
        </div>
        <div className="px-4 py-3 border-t border-gray-200 space-y-1">
          <Link href="/approvals" className="block text-xs text-gray-600 hover:text-gray-900 py-1">Approvals</Link>
          <Link href="/audit" className="block text-xs text-gray-600 hover:text-gray-900 py-1">Audit</Link>
          <Link href="/kpi" className="block text-xs text-gray-600 hover:text-gray-900 py-1">KPI Dashboard</Link>
        </div>
      </aside>

      <div className="flex-1 flex flex-col min-w-0">
        <header className="bg-white border-b border-gray-200 px-5 py-3 flex items-center justify-between shrink-0">
          <h1 className="text-sm font-medium text-gray-700 truncate">
            Session: <span className="font-mono text-xs text-gray-500">{sessionId}</span>
          </h1>
          <button
            onClick={() => setShowReasoning((p) => !p)}
            className={`text-xs px-3 py-1.5 rounded-md border transition-colors ${
              showReasoning
                ? "bg-gray-900 text-white border-gray-900"
                : "bg-white text-gray-600 border-gray-300 hover:border-gray-400"
            }`}
          >
            Reasoning Panel <kbd className="ml-1 opacity-60">⌘.</kbd>
          </button>
        </header>

        <main className="flex-1 flex min-h-0">
          <div className="flex-1 flex flex-col min-w-0">
            <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
              {messages.length === 0 && (
                <div className="text-center py-16 text-gray-400">
                  <p className="text-base">Start a decision analysis</p>
                  <p className="text-sm mt-1">Type your supply chain question below.</p>
                </div>
              )}
              {messages.map((msg) => (
                <MessageBubble key={msg.id} message={msg} onFeedback={submitFeedback} />
              ))}
              {isSending && (
                <div className="flex justify-start">
                  <div className="bg-white border border-gray-200 rounded-2xl px-4 py-3">
                    <div className="flex gap-1">
                      <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                      <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                      <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            <div className="shrink-0 border-t border-gray-200 bg-white px-5 py-3">
              <div className="flex gap-3">
                <textarea
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      handleSend();
                    }
                  }}
                  placeholder="Ask a supply chain question... (Enter to send, Shift+Enter for newline)"
                  rows={3}
                  className="flex-1 resize-none rounded-xl border border-gray-300 px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
                <button
                  onClick={handleSend}
                  disabled={isSending || !input.trim()}
                  className="self-end bg-blue-600 text-white px-5 py-2.5 rounded-xl text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  Send
                </button>
              </div>
            </div>
          </div>

          {showReasoning && (
            <div className="w-80 shrink-0 border-l border-gray-800 overflow-hidden">
              <ReasoningPanel
                sessionId={sessionId}
                usage={usage}
              />
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
