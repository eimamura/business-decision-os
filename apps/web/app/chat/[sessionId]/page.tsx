"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import ReasoningPanel from "./components/ReasoningPanel";
import MessageBubble from "@/components/MessageBubble";
import { useChat } from "@/hooks/useChat";
import ChatSidebar from "@/components/ChatSidebar";
import { fetchSessions, createSession, deleteSession } from "@/lib/api";
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
  const [showReasoning, setShowReasoning] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const { messages, isSending, usage, loadMessages, sendMessage, submitFeedback } = useChat(sessionId);

  const activeSession = sessions.find((s) => s.session_id === sessionId);

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
    await sendMessage(text);
  }, [input, isSending, sendMessage]);

  return (
    <div className="flex h-screen bg-[#0c0c14] overflow-hidden">
      <ChatSidebar
        sessions={sessions}
        activeSessionId={sessionId}
        onNewSession={handleNewSession}
        creating={creating}
        onDelete={handleDelete}
      />

      <div className="flex-1 flex flex-col min-w-0">
        <header className="bg-[#13131e] border-b border-white/8 px-5 py-3 flex items-center justify-between shrink-0">
          <h1 className="text-sm font-semibold text-white/80 truncate">
            {activeSession?.goal || <span className="text-white/25 font-normal font-mono text-xs">{sessionId}</span>}
          </h1>
          <button
            onClick={() => setShowReasoning((p) => !p)}
            className={`text-xs px-3 py-1.5 rounded-md border font-medium transition-all ${
              showReasoning
                ? "bg-indigo-500 text-white border-indigo-500"
                : "bg-transparent text-white/40 border-white/10 hover:text-white/70 hover:border-white/20"
            }`}
          >
            Reasoning <kbd className="ml-1 opacity-50 font-mono">⌘.</kbd>
          </button>
        </header>

        <main className="flex-1 flex min-h-0">
          <div className="flex-1 flex flex-col min-w-0">
            <div className="flex-1 overflow-y-auto px-6 py-5 space-y-4">
              {messages.length === 0 && (
                <div className="flex flex-col items-center justify-center h-full pb-16 text-center gap-2">
                  <p className="text-sm font-medium text-white/40">Start a decision analysis</p>
                  <p className="text-xs text-white/20">Ask a supply chain question below.</p>
                </div>
              )}
              {messages.map((msg) => (
                <MessageBubble key={msg.id} message={msg} onFeedback={submitFeedback} />
              ))}
              <div ref={messagesEndRef} />
            </div>

            <div className="shrink-0 border-t border-white/8 bg-[#13131e] px-5 py-3">
              <div className="flex gap-2 items-end">
                <textarea
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      handleSend();
                    }
                  }}
                  placeholder="Ask a supply chain question…"
                  rows={2}
                  className="flex-1 resize-none rounded-xl bg-[#0c0c14] border border-white/10 px-4 py-2.5 text-sm text-white/85 placeholder:text-white/25 focus:outline-none focus:border-indigo-500/50 focus:ring-2 focus:ring-indigo-500/15 transition-all"
                />
                <button
                  onClick={handleSend}
                  disabled={isSending || !input.trim()}
                  className="shrink-0 flex items-center gap-1.5 bg-indigo-600 text-white px-4 py-2.5 rounded-xl text-sm font-medium hover:bg-indigo-500 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="22" y1="2" x2="11" y2="13" />
                    <polygon points="22 2 15 22 11 13 2 9 22 2" />
                  </svg>
                  Send
                </button>
              </div>
            </div>
          </div>

          {showReasoning && (
            <div className="w-80 shrink-0 border-l border-white/8 bg-[#13131e] overflow-hidden">
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
