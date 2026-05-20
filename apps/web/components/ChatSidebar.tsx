"use client";

import Link from "next/link";
import type { Session } from "@/types/chat";

interface ChatSidebarProps {
  sessions: Session[];
  activeSessionId?: string;
  onNewSession: () => void;
  creating: boolean;
  onDelete: (sessionId: string) => void;
}

export default function ChatSidebar({
  sessions,
  activeSessionId,
  onNewSession,
  creating,
  onDelete,
}: ChatSidebarProps) {
  return (
    <aside className="w-56 shrink-0 bg-white border-r border-gray-200 flex flex-col">
      <div className="px-4 py-3 border-b border-gray-200">
        <Link href="/chat" className="text-sm font-semibold text-gray-900 hover:text-blue-600">
          Business Decision OS
        </Link>
      </div>

      <div className="px-4 py-2 border-b border-gray-200">
        <button
          onClick={onNewSession}
          disabled={creating}
          className="w-full bg-blue-600 text-white px-3 py-1.5 rounded-lg text-xs font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
        >
          {creating ? "Creating..." : "New Session"}
        </button>
      </div>

      <div className="flex-1 overflow-y-auto py-2">
        {sessions.map((s) => (
          <div key={s.session_id} className="relative group/item">
            <Link
              href={`/chat/${s.session_id}`}
              className={`block px-4 py-2.5 pr-8 text-xs hover:bg-gray-50 ${
                s.session_id === activeSessionId
                  ? "bg-blue-50 text-blue-700 font-medium"
                  : "text-gray-700"
              }`}
            >
              <span className="block truncate">{s.goal ?? "Session"}</span>
              <span className="text-gray-400 mt-0.5 block">
                {new Date(s.created_at).toLocaleDateString()}
              </span>
            </Link>
            <button
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                onDelete(s.session_id);
              }}
              aria-label="Delete session"
              className="absolute right-1.5 top-1/2 -translate-y-1/2 opacity-0 group-hover/item:opacity-100 p-1 text-gray-400 hover:text-red-400 transition-opacity"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="3 6 5 6 21 6" />
                <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
                <path d="M10 11v6" />
                <path d="M14 11v6" />
                <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
              </svg>
            </button>
          </div>
        ))}
      </div>

      <div className="px-4 py-3 border-t border-gray-200 space-y-1">
        <Link href="/approvals" className="block text-xs text-gray-600 hover:text-gray-900 py-1">
          Approvals
        </Link>
        <Link href="/audit" className="block text-xs text-gray-600 hover:text-gray-900 py-1">
          Audit
        </Link>
        <Link href="/kpi" className="block text-xs text-gray-600 hover:text-gray-900 py-1">
          KPI Dashboard
        </Link>
      </div>
    </aside>
  );
}
