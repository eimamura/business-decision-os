"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { SlidersHorizontal, ChevronDown, Mic, BrainCircuit } from "lucide-react";
import ExecutionPanel from "@/components/agent/ExecutionPanel";
import LlmCallsPanel from "@/components/agent/LlmCallsPanel";
import QuickActionGrid from "@/components/analysis/QuickActionGrid";
import DailyExceptionsPanel from "@/components/DailyExceptionsPanel";
import MessageBubble from "@/components/chat/MessageBubble";
import { ExecutionProgressPanel } from "@/components/ExecutionProgressPanel";
import { useChat } from "@/hooks/useChat";
import ChatSidebar from "@/components/ChatSidebar";
import ToolScenarioBar from "@/components/ToolScenarioBar";
import ToolScenarioModal from "@/components/ToolScenarioModal";
import { useSessionsContext } from "@/app/chat/SessionsContext";

interface ChatPageProps {
  params: { sessionId: string };
}

export default function ChatPage({ params }: ChatPageProps) {
  const { sessionId } = params;
  const router = useRouter();
  const { sessions, setSessions, creating, onNewSession, onDelete, onDeleteAll, deleteAllPending } = useSessionsContext();
  const [input, setInput] = useState("");
  const [showActivity, setShowActivity] = useState(true);
  const [showLlmCalls, setShowLlmCalls] = useState(false);
  const [scenarioModalOpen, setScenarioModalOpen] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const onTitleGenerated = useCallback(
    (title: string) => {
      setSessions((prev) =>
        prev.map((s) => (s.session_id === sessionId ? { ...s, title } : s)),
      );
    },
    [sessionId, setSessions],
  );

  const { messages, isSending, usage, isLoadingMessages, loadMessages, sendMessage, sendAskUserAnswer, submitFeedback, appendAssistantReply } = useChat(
    sessionId,
    onTitleGenerated,
  );

  const activeSession = sessions.find((s) => s.session_id === sessionId);

  useEffect(() => {
    void loadMessages();
  }, [sessionId, loadMessages]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === ".") {
        e.preventDefault();
        setShowActivity((p) => !p);
        setShowLlmCalls(false);
      }
    }
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, []);

  async function handleDelete(deletedId: string): Promise<void> {
    await onDelete(deletedId);
    if (deletedId === sessionId) {
      router.push("/chat");
    }
  }

  const handleSend = useCallback(async () => {
    const text = input.trim();
    if (!text || isSending) return;
    setInput("");
    setShowActivity(true);
    await sendMessage(text);
  }, [input, isSending, sendMessage]);

  const handleScenarioApply = useCallback(async (prompt: string) => {
    if (isSending) return;
    setInput("");
    setShowActivity(true);
    await sendMessage(prompt);
  }, [isSending, sendMessage]);

  const isEmpty = !isLoadingMessages && messages.length === 0;

  return (
    <div className="flex h-screen bg-background dark:bg-[#070B14] overflow-hidden">
      {/* ChatSidebar includes both nav links and sessions list. NavSidebar is NOT rendered here to avoid double sidebars. */}
      <ChatSidebar
        sessions={sessions}
        activeSessionId={sessionId}
        onNewSession={onNewSession}
        creating={creating}
        onDelete={handleDelete}
        onDeleteAll={onDeleteAll}
        deleteAllPending={deleteAllPending}
      />

      <div className="flex-1 flex flex-col min-w-0">
        <header className="bg-surface dark:bg-[#0B1020] border-b border-border dark:border-white/8 px-5 py-3 flex items-center justify-between shrink-0">
          {!isEmpty && (
            <div className="flex items-center gap-2 min-w-0">
              <BrainCircuit size={15} className="shrink-0 text-indigo-500 dark:text-indigo-400" />
              <h1 className="text-sm font-semibold text-foreground dark:text-white/80 truncate">
                {activeSession?.title ?? activeSession?.goal ?? (
                  <span className="text-muted dark:text-white/25 font-normal font-mono text-xs">{sessionId}</span>
                )}
              </h1>
            </div>
          )}
          <div className="flex items-center gap-2">
            <button
              onClick={() => { setShowActivity((p) => !p); setShowLlmCalls(false); }}
              className={`text-xs px-3 py-1.5 rounded-md border font-medium transition-all ${
                showActivity
                  ? "bg-indigo-600 text-white border-indigo-600 dark:bg-indigo-500 dark:border-indigo-500"
                  : "bg-transparent text-muted dark:text-white/40 border-border dark:border-white/10 hover:text-foreground dark:hover:text-white/70 hover:border-muted dark:hover:border-white/20"
              }`}
            >
              Execution Trace <kbd className="ml-1 opacity-50 font-mono">⌘.</kbd>
            </button>
            <button
              onClick={() => { setShowLlmCalls((p) => !p); setShowActivity(false); }}
              className={`text-xs px-3 py-1.5 rounded-md border font-medium transition-all ${
                showLlmCalls
                  ? "bg-indigo-600 text-white border-indigo-600 dark:bg-indigo-500 dark:border-indigo-500"
                  : "bg-transparent text-muted dark:text-white/40 border-border dark:border-white/10 hover:text-foreground dark:hover:text-white/70 hover:border-muted dark:hover:border-white/20"
              }`}
            >
              LLM Calls
            </button>
          </div>
        </header>

        <main className="flex-1 flex min-h-0">
          <div className="flex-1 flex flex-col min-w-0">
            {/* Daily Exceptions strip — docked below the header, visible in both empty
                and active-conversation states. Defaults to expanded when no messages
                exist, collapsed once a conversation is active. User toggle wins within
                the component's lifetime. */}
            {!isLoadingMessages && (
              <div className="shrink-0 px-6 pt-3">
                <DailyExceptionsPanel
                  onInvestigate={(prompt) => setInput(prompt)}
                  defaultExpanded={isEmpty}
                />
              </div>
            )}

            <div className="flex-1 overflow-y-auto px-6 py-5 min-h-0 custom-scrollbar">
              {isLoadingMessages ? (
                <div className="flex flex-col gap-4 pt-4">
                  {[1, 2, 3].map((i) => (
                    <div
                      key={i}
                      className="h-4 rounded bg-border dark:bg-white/8 animate-pulse"
                      style={{ width: `${60 + i * 10}%` }}
                    />
                  ))}
                </div>
              ) : isEmpty ? (
                <div className="flex flex-col h-full gap-6">
                  {/* Empty state header */}
                  <div className="flex items-start justify-between pt-2">
                    <div className="flex flex-col gap-1.5">
                      <h2 className="text-xl font-semibold text-foreground dark:text-white/90">
                        What do you want to analyze today?
                      </h2>
                      <p className="text-sm text-muted dark:text-white/50">
                        Ask anything about your supply chain. I&apos;ll analyze data and provide actionable insights.
                      </p>
                    </div>
                    <button
                      disabled
                      title="Configure Agent (coming soon)"
                      className="shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border dark:border-white/10 bg-surface dark:bg-white/4 text-xs text-muted dark:text-white/40 cursor-not-allowed"
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
                    <MessageBubble
                      key={msg.id}
                      message={msg}
                      sessionId={sessionId}
                      onFeedback={submitFeedback}
                      onAskUserAnswered={sendAskUserAnswer}
                    />
                  ))}
                  <ExecutionProgressPanel sessionId={sessionId} />
                  <div ref={messagesEndRef} />
                </div>
              )}
            </div>

            <div className="shrink-0 border-t border-border dark:border-white/8 bg-surface dark:bg-[#0B1020] px-5 pt-3 pb-4">
              {/* Composer panel */}
              <div className="rounded-2xl bg-background dark:bg-gradient-to-b dark:from-white/[0.04] dark:to-[#070B14] border border-border dark:border-white/10 focus-within:border-indigo-500/40 focus-within:ring-1 focus-within:ring-indigo-500/15 transition-all">
                {/* Tool scenario chips for demo / reproducibility */}
                <ToolScenarioBar
                  onSelect={(prompt) => setInput(prompt)}
                  onOpenModal={() => setScenarioModalOpen(true)}
                />
                {/* Top row: textarea */}
                <textarea
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      void handleSend();
                    }
                  }}
                  placeholder="Ask about forecast, inventory, OTIF, demand changes, or recommended actions..."
                  rows={2}
                  className="w-full resize-none bg-transparent border-none outline-none px-4 pt-3 pb-2 text-sm text-foreground dark:text-white/85 placeholder:text-muted dark:placeholder:text-white/35 focus:outline-none"
                />
                {/* Bottom row: actions */}
                <div className="flex items-center justify-between px-3 pb-2.5">
                  {/* Left: Add context */}
                  <div className="flex items-center gap-1.5">
                    <button
                      disabled
                      title="Add context (coming soon)"
                      className="flex items-center justify-center w-6 h-6 rounded-md bg-surface dark:bg-white/5 border border-border dark:border-white/8 text-muted dark:text-white/30 cursor-not-allowed"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M12 5v14M5 12h14" />
                      </svg>
                    </button>
                    <span className="text-xs text-muted dark:text-white/25 select-none">Add context</span>
                  </div>
                  {/* Right: mic + send */}
                  <div className="flex items-center gap-1.5">
                    <button
                      disabled
                      title="Voice input (coming soon)"
                      className="flex items-center justify-center w-8 h-8 rounded-lg bg-surface dark:bg-white/4 border border-border dark:border-white/8 text-muted dark:text-white/25 cursor-not-allowed"
                    >
                      <Mic size={15} />
                    </button>
                    <button
                      onClick={() => void handleSend()}
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
              <p className="text-xs text-muted dark:text-white/25 text-center mt-1.5">
                AI can make mistakes. Verify important information.
              </p>
            </div>
          </div>

          {showActivity && (
            <div className="w-80 shrink-0 border-l border-border dark:border-white/8 bg-surface dark:bg-[#0B1020] overflow-hidden flex flex-col custom-scrollbar">
              <ExecutionPanel sessionId={sessionId} />
            </div>
          )}
          {showLlmCalls && (
            <div className="w-80 shrink-0 border-l border-border dark:border-white/8 bg-surface dark:bg-[#0B1020] overflow-hidden flex flex-col">
              <LlmCallsPanel />
            </div>
          )}
        </main>
      </div>

      <ToolScenarioModal
        open={scenarioModalOpen}
        onClose={() => setScenarioModalOpen(false)}
        onApply={(prompt) => void handleScenarioApply(prompt)}
      />
    </div>
  );
}
