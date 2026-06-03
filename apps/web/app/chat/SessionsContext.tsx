"use client";

import { createContext, useContext } from "react";
import type { Session } from "@/types/chat";

export interface SessionsContextValue {
  sessions: Session[];
  setSessions: React.Dispatch<React.SetStateAction<Session[]>>;
  creating: boolean;
  onNewSession: () => Promise<void>;
  onDelete: (sessionId: string) => Promise<void>;
  onDeleteAll: () => Promise<void>;
  deleteAllPending: boolean;
  deleteError: string | null;
}

const SessionsContext = createContext<SessionsContextValue | null>(null);

export function useSessionsContext(): SessionsContextValue {
  const ctx = useContext(SessionsContext);
  if (ctx === null) {
    throw new Error("useSessionsContext must be used within SessionsProvider (chat layout)");
  }
  return ctx;
}

export default SessionsContext;
