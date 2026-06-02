"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import type { ReactNode } from "react";
import SessionsContext from "./SessionsContext";
import { fetchSessions, createSession, deleteSession } from "@/lib/api";
import type { Session } from "@/types/chat";

interface ChatLayoutProps {
  children: ReactNode;
}

export default function ChatLayout({ children }: ChatLayoutProps): React.ReactElement {
  const router = useRouter();
  const [sessions, setSessions] = useState<Session[]>([]);
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    fetchSessions()
      .then(setSessions)
      .catch(() => setSessions([]));
  }, []);

  const onNewSession = useCallback(async (): Promise<void> => {
    setCreating(true);
    try {
      const data = await createSession("New decision session");
      router.push(`/chat/${data.session_id}`);
    } catch {
      setCreating(false);
    }
  }, [router]);

  const onDelete = useCallback(async (deletedId: string): Promise<void> => {
    setSessions((prev) => prev.filter((s) => s.session_id !== deletedId));
    const ok = await deleteSession(deletedId);
    if (!ok) {
      fetchSessions().then(setSessions).catch(() => undefined);
    }
    // Navigation after delete is handled by the page itself (it knows the active sessionId)
  }, []);

  return (
    <SessionsContext.Provider value={{ sessions, setSessions, creating, onNewSession, onDelete }}>
      {children}
    </SessionsContext.Provider>
  );
}
