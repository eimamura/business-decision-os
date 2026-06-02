"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import type { ReactNode } from "react";
import SessionsContext from "./SessionsContext";
import { ChatStateProvider } from "./ChatStateContext";
import { fetchSessions, createSession, deleteSession, deleteAllSessions } from "@/lib/api";
import type { Session } from "@/types/chat";

interface ChatLayoutProps {
  children: ReactNode;
}

export default function ChatLayout({ children }: ChatLayoutProps): React.ReactElement {
  const router = useRouter();
  const [sessions, setSessions] = useState<Session[]>([]);
  const [creating, setCreating] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  useEffect(() => {
    fetchSessions()
      .then(setSessions)
      .catch(() => setSessions([]));
  }, []);

  const onNewSession = useCallback(async (): Promise<void> => {
    setCreating(true);
    try {
      const data = await createSession("New decision session");
      setCreating(false);
      router.push(`/chat/${data.session_id}`);
    } catch {
      setCreating(false);
    }
  }, [router]);

  const onDelete = useCallback(async (deletedId: string): Promise<void> => {
    const snapshot = sessions;
    setSessions((prev) => prev.filter((s) => s.session_id !== deletedId));
    const ok = await deleteSession(deletedId);
    if (!ok) {
      setSessions(snapshot);
      setDeleteError("Failed to delete session. Please try again.");
    }
    // Navigation after delete is handled by the page itself (it knows the active sessionId)
  }, [sessions]);

  const onDeleteAll = useCallback(async (): Promise<void> => {
    const snapshot = sessions;
    setSessions([]);
    try {
      await deleteAllSessions();
      router.push("/chat");
    } catch {
      setSessions(snapshot);
      setDeleteError("Failed to delete all sessions. Please try again.");
    }
  }, [sessions, router]);

  return (
    <SessionsContext.Provider value={{ sessions, setSessions, creating, onNewSession, onDelete, onDeleteAll, deleteError }}>
      <ChatStateProvider>
        {children}
      </ChatStateProvider>
    </SessionsContext.Provider>
  );
}
