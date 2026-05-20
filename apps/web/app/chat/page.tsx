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
    <div className="flex h-screen bg-gray-50 overflow-hidden">
      <ChatSidebar
        sessions={sessions}
        activeSessionId={undefined}
        onNewSession={handleNewSession}
        creating={creating}
        onDelete={handleDelete}
      />
      <main className="flex-1 flex items-center justify-center">
        <p className="text-gray-400 text-sm">Select a session or create a new one</p>
      </main>
    </div>
  );
}
