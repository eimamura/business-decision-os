"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { SlidersHorizontal, ChevronDown, Mic, BrainCircuit } from "lucide-react";
import AgentActivityPanel from "@/components/agent/AgentActivityPanel";
import QuickActionGrid from "@/components/analysis/QuickActionGrid";
import MessageBubble from "@/components/MessageBubble";
import { useChat } from "@/hooks/useChat";
import ChatSidebar from "@/components/ChatSidebar";
import ToolScenarioBar from "@/components/ToolScenarioBar";
import { fetchSessions, fetchSession, createSession, deleteSession } from "@/lib/api";
import type { Session } from "@/types/chat";

interface ChatPageProps {
  params: { sessionId: string };
}

export default function ChatPage({ params }: ChatPageProps) {
  const { sessionId } = params;
  const router = useRouter();
  const [sessions, setSessions] = useState<Session[]>([]);
  const [creating, setCreating] = useState(false);
  const [input, setInput] = useState("");
  const [showActivity, setShowActivity] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const { messages, isSending, usage, loadMessages, sendMessage, submitFeedback } = useChat(
    sessionId,
    (title) => {
      setSessions((prev) =>
        prev.map((s) => (s.session_id === sessionId ? { ...s, title } : s)),
      );
    },
  );

  const activeSession = sessions.find((s) => s.session_id === sessionId);

  useEffect(() => {
    fetchSession(sessionId)
      .then((session) => {
        if (session === null) router.replace("/chat");
      })
      .catch(() => undefined);

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
        setShowActivity((p) => !p);
      }
    }
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, []);

  async function handleDelete(deletedId: string) {
    setSessions((prev) => prev.filter((s) => s.session_id !== deletedId));
    const ok = await deleteSession(deletedId);
    if (!ok) {
      fetchSessions().then(setSessions).catch(() => undefined);
      return;
    }
    if (deletedId === sessionId) {
      router.push("/chat");
    }
  }

  async function handleNewSession() {
    setCreating(true);
    try {
      const data = await createSession("New decision session");
      router.push(`/chat/${data.session_id}`);
    } catch {
      setCreating(false);
    }
  }

  const handleSend = useCallback(async () => {
    const text = input.trim();
    if (!text || isSending) return;
    setInput("");
    setShowActivity(true);
    await sendMessage(text);
  }, [input, isSending, sendMessage]);

  const isEmpty = messages.length === 0;

  return (
    <div className="flex h-screen bg-[#070B14] overflow-hidden">
      <ChatSidebar
        sessions={sessions}
        activeSessionId={sessionId}
        onNewSession={handleNewSession}
        creating={creating}
        onDelete={handleDelete}
      />

      <div className="flex-1 flex flex-col min-w-0">
        <header className="bg-[#0B1020] border-b border-white/8 px-5 py-3 flex items-center justify-between shrink-0">
          {!isEmpty && (
            <div className="flex items-center gap-2 min-w-0">
              <BrainCircuit size={15} className="shrink-0 text-indigo-400" />
              <h1 className="text-sm font-semibold text-white/80 truncate">
                {activeSession?.title ?? activeSession?.goal ?? (
                  <span className="text-white/25 font-normal font-mono text-xs">{sessionId}</span>
                )}
              </h1>
            </div>
          )}
          <button
            onClick={() => setShowActivity((p) => !p)}
            className={`text-xs px-3 py-1.5 rounded-md border font-medium transition-all ${
              showActivity
                ? "bg-indigo-500 text-white border-indigo-500"
                : "bg-transparent text-white/40 border-white/10 hover:text-white/70 hover:border-white/20"
            }`}
          >
            Agent Activity <kbd className="ml-1 opacity-50 font-mono">⌘.</kbd>
          </button>
        </header>

        <main className="flex-1 flex min-h-0">
          <div className="flex-1 flex flex-col min-w-0">
            <div className="flex-1 overflow-y-auto px-6 py-5 min-h-0 custom-scrollbar">
              {isEmpty ? (
                <div className="flex flex-col h-full gap-6">
                  {/* Empty state header */}
                  <div className="flex items-start justify-between pt-2">
                    <div className="flex flex-col gap-1.5">
                      <h2 className="text-xl font-semibold text-white/90">
                        What do you want to analyze today?
                      </h2>
                      <p className="text-sm text-white/50">
                        Ask anything about your supply chain. I&apos;ll analyze data and provide actionable insights.
                      </p>
                    </div>
                    <button
                      disabled
                      title="Configure Agent (coming soon)"
                      className="shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-white/10 bg-white/4 text-xs text-white/40 cursor-not-allowed"
                    >
                      <SlidersHorizontal size={13} />
                      Configure Agent
                      <ChevronDown size={12} className="opacity-60" />
                    </button>
                  </div>
                  {/* Quick action cards */}
                  <QuickActionGrid onSelect={(prompt) => setInput(prompt)} />
                </div>
              ) : (
                <div className="space-y-4">
                  {messages.map((msg) => (
                    <MessageBubble key={msg.id} message={msg} onFeedback={submitFeedback} />
                  ))}
                  <div ref={messagesEndRef} />
                </div>
              )}
            </div>

            <div className="shrink-0 border-t border-white/8 bg-[#0B1020] px-5 pt-3 pb-4">
              {/* Composer panel */}
              <div className="rounded-2xl bg-gradient-to-b from-white/[0.04] to-[#070B14] border border-white/10 focus-within:border-indigo-500/40 focus-within:ring-1 focus-within:ring-indigo-500/15 transition-all">
                {/* Tool scenario chips for demo / reproducibility */}
                <ToolScenarioBar onSelect={(prompt) => setInput(prompt)} />
                {/* Top row: textarea */}
                <textarea
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      handleSend();
                    }
                  }}
                  placeholder="Ask about forecast, inventory, OTIF, demand changes, or recommended actions..."
                  rows={2}
                  className="w-full resize-none bg-transparent border-none outline-none px-4 pt-3 pb-2 text-sm text-white/85 placeholder:text-white/35 focus:outline-none"
                />
                {/* Bottom row: actions */}
                <div className="flex items-center justify-between px-3 pb-2.5">
                  {/* Left: Add context */}
                  <div className="flex items-center gap-1.5">
                    <button
                      disabled
                      title="Add context (coming soon)"
                      className="flex items-center justify-center w-6 h-6 rounded-md bg-white/5 border border-white/8 text-white/30 cursor-not-allowed"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M12 5v14M5 12h14" />
                      </svg>
                    </button>
                    <span className="text-xs text-white/25 select-none">Add context</span>
                  </div>
                  {/* Right: mic + send */}
                  <div className="flex items-center gap-1.5">
                    <button
                      disabled
                      title="Voice input (coming soon)"
                      className="flex items-center justify-center w-8 h-8 rounded-lg bg-white/4 border border-white/8 text-white/25 cursor-not-allowed"
                    >
                      <Mic size={15} />
                    </button>
                    <button
                      onClick={handleSend}
                      disabled={isSending || !input.trim()}
                      className="flex items-center gap-1.5 bg-indigo-600 text-white px-3 py-1.5 rounded-lg text-sm font-medium hover:bg-indigo-500 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <line x1="22" y1="2" x2="11" y2="13" />
                        <polygon points="22 2 15 22 11 13 2 9 22 2" />
                      </svg>
                      Send
                    </button>
                  </div>
                </div>
              </div>
              <p className="text-xs text-white/25 text-center mt-1.5">
                AI can make mistakes. Verify important information.
              </p>
            </div>
          </div>

          {showActivity && (
            <div className="w-80 shrink-0 border-l border-white/8 bg-[#0B1020] overflow-hidden flex flex-col custom-scrollbar">
              <AgentActivityPanel sessionId={sessionId} usage={usage} />
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
