"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import ChatSidebar from "@/components/ChatSidebar";
import { fetchSessions, createSession, deleteSession } from "@/lib/api";
import type { Session } from "@/types/chat";

export default function ChatListPage() {
  const router = useRouter();
  const [sessions, setSessions] = useState<Session[]>([]);
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    fetchSessions()
      .then(setSessions)
      .catch(() => setSessions([]));
  }, []);

  async function handleDelete(sessionId: string) {
    setSessions((prev) => prev.filter((s) => s.session_id !== sessionId));
    const ok = await deleteSession(sessionId);
    if (!ok) {
      fetchSessions().then(setSessions).catch(() => undefined);
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

  return (
    <div className="flex h-screen bg-[#0c0c14] overflow-hidden">
      <ChatSidebar
        sessions={sessions}
        activeSessionId={undefined}
        onNewSession={handleNewSession}
        creating={creating}
        onDelete={handleDelete}
      />
      <main className="flex-1 flex flex-col items-center justify-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-white/5 flex items-center justify-center">
          <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="text-indigo-400">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
          </svg>
        </div>
        <div className="text-center">
          <p className="text-sm font-semibold text-white/70">Start a decision session</p>
          <p className="text-xs text-white/30 mt-0.5">Select a session or create a new one</p>
        </div>
      </main>
    </div>
  );
}
