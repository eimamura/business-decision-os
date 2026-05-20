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
    <aside className="w-56 shrink-0 bg-[#0c0c14] flex flex-col">
      <div className="px-4 py-4 border-b border-white/8">
        <Link
          href="/chat"
          className="text-sm font-semibold text-white tracking-tight hover:text-indigo-300 transition-colors"
        >
          Decision OS
        </Link>
        <p className="text-[10px] text-white/30 mt-0.5 tracking-wide uppercase">Supply Chain Intelligence</p>
      </div>

      <div className="px-3 py-2.5 border-b border-white/8">
        <button
          onClick={onNewSession}
          disabled={creating}
          className="w-full flex items-center justify-center gap-1.5 bg-indigo-500 hover:bg-indigo-400 disabled:opacity-50 text-white px-3 py-1.5 rounded-md text-xs font-medium transition-colors"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 5v14M5 12h14" />
          </svg>
          {creating ? "Creating…" : "New Session"}
        </button>
      </div>

      <div className="flex-1 overflow-y-auto py-1">
        {sessions.length === 0 && (
          <p className="px-4 py-3 text-[11px] text-white/25">No sessions yet</p>
        )}
        {sessions.map((s) => {
          const isActive = s.session_id === activeSessionId;
          return (
            <div key={s.session_id} className="relative group/item">
              <Link
                href={`/chat/${s.session_id}`}
                className={`block px-4 py-2.5 pr-8 text-xs transition-colors ${
                  isActive
                    ? "bg-indigo-500/15 text-white"
                    : "text-white/50 hover:bg-white/5 hover:text-white/80"
                }`}
              >
                {isActive && (
                  <span className="absolute left-0 top-0 bottom-0 w-0.5 bg-indigo-400 rounded-r" />
                )}
                <span className="block truncate font-medium">{s.goal || "New Session"}</span>
                <span className="text-[10px] text-white/25 mt-0.5 block">
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
                className="absolute right-1.5 top-1/2 -translate-y-1/2 opacity-0 group-hover/item:opacity-100 p-1 text-white/20 hover:text-red-400 transition-all"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="3 6 5 6 21 6" />
                  <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
                  <path d="M10 11v6M14 11v6" />
                  <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
                </svg>
              </button>
            </div>
          );
        })}
      </div>

      <div className="px-4 py-3 border-t border-white/8 space-y-0.5">
        {[
          { href: "/approvals", label: "Approvals" },
          { href: "/audit", label: "Audit Log" },
          { href: "/kpi", label: "KPI Dashboard" },
        ].map(({ href, label }) => (
          <Link
            key={href}
            href={href}
            className="flex items-center gap-2 px-0 py-1.5 text-[11px] text-white/35 hover:text-white/65 transition-colors"
          >
            {label}
          </Link>
        ))}
      </div>
    </aside>
  );
}
