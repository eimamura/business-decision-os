"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { User, Trash2, ChevronUp, ChevronDown, Database, Settings } from "lucide-react";
import { useState, useEffect, useRef } from "react";
import type { Session } from "@/types/chat";

interface ChatSidebarProps {
  sessions: Session[];
  activeSessionId?: string;
  onNewSession: () => void;
  creating: boolean;
  onDelete: (sessionId: string) => void;
}

const NAV_ITEMS = [
  {
    href: "/chat",
    label: "Chat",
    icon: (
      <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
      </svg>
    ),
  },
  {
    href: "/kpi",
    label: "KPI Dashboard",
    icon: (
      <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <line x1="18" y1="20" x2="18" y2="10" />
        <line x1="12" y1="20" x2="12" y2="4" />
        <line x1="6" y1="20" x2="6" y2="14" />
      </svg>
    ),
  },
  {
    href: "/approvals",
    label: "Approvals",
    icon: (
      <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <polyline points="9 11 12 14 22 4" />
        <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
      </svg>
    ),
  },
  {
    href: "/audit",
    label: "Audit Log",
    icon: (
      <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <polyline points="14 2 14 8 20 8" />
        <line x1="16" y1="13" x2="8" y2="13" />
        <line x1="16" y1="17" x2="8" y2="17" />
        <polyline points="10 9 9 9 8 9" />
      </svg>
    ),
  },
  {
    href: "/usage",
    label: "Usage & Cost",
    icon: (
      <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="10" />
        <path d="M12 6v6l4 2" />
      </svg>
    ),
  },
  {
    href: "/agents",
    label: "Agents & Tools",
    icon: (
      <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="4" y="4" width="6" height="6" rx="1" />
        <rect x="14" y="4" width="6" height="6" rx="1" />
        <rect x="4" y="14" width="6" height="6" rx="1" />
        <rect x="14" y="14" width="6" height="6" rx="1" />
        <path d="M7 10v4M17 10v4M10 7h4M10 17h4" />
      </svg>
    ),
  },
  {
    href: "/jobs",
    label: "Jobs",
    icon: (
      <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="2" y="7" width="20" height="14" rx="2" ry="2" />
        <path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2" />
        <line x1="12" y1="12" x2="12" y2="16" />
        <line x1="10" y1="14" x2="14" y2="14" />
      </svg>
    ),
  },
];

function formatSessionDate(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays === 0) {
    return `Today, ${date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}`;
  }
  if (diffDays === 1) {
    return `Yesterday, ${date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}`;
  }
  return date.toLocaleDateString([], { month: "short", day: "numeric", year: "numeric" });
}

export default function ChatSidebar({
  sessions,
  activeSessionId,
  onNewSession,
  creating,
  onDelete,
}: ChatSidebarProps) {
  const pathname = usePathname();
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);
  const [profileOpen, setProfileOpen] = useState(false);
  const profileRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (profileRef.current && !profileRef.current.contains(e.target as Node)) {
        setProfileOpen(false);
      }
    }
    if (profileOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [profileOpen]);

  return (
    <aside className="w-60 shrink-0 bg-surface dark:bg-[#0B1020] flex flex-col border-r border-border dark:border-white/5">
      {/* Brand */}
      <div className="px-4 py-4 border-b border-border dark:border-white/8">
        <Link
          href="/chat"
          className="text-sm font-semibold text-foreground dark:text-white tracking-tight hover:text-indigo-600 dark:hover:text-indigo-300 transition-colors"
        >
          Decision OS
        </Link>
        <p className="text-xs text-muted dark:text-white/50 mt-0.5 tracking-wide uppercase">Supply Chain Intelligence</p>
      </div>

      {/* Main Navigation */}
      <div className="px-3 pt-3 pb-2">
        <p className="px-1 mb-1.5 text-[10px] font-semibold uppercase tracking-widest text-muted dark:text-white/25">
          Main
        </p>
        <nav className="space-y-0.5">
          {NAV_ITEMS.map(({ href, label, icon }) => {
            const isActive = href === "/chat" ? pathname.startsWith("/chat") : pathname === href;
            return (
              <Link
                key={href}
                href={href}
                className={`flex items-center gap-2.5 px-2.5 py-1.5 rounded-md text-xs transition-colors ${
                  isActive
                    ? "bg-indigo-100 dark:bg-indigo-500/15 text-indigo-700 dark:text-white font-medium"
                    : "text-muted dark:text-white/45 hover:text-foreground dark:hover:text-white/75 hover:bg-surface dark:hover:bg-white/5"
                }`}
              >
                <span className={isActive ? "text-indigo-500 dark:text-indigo-400" : "text-muted dark:text-white/30"}>{icon}</span>
                {label}
              </Link>
            );
          })}
        </nav>
      </div>

      {/* Sessions */}
      <div className="px-3 pt-2 border-t border-border dark:border-white/5">
        <div className="flex items-center justify-between px-1 mb-1.5">
          <p className="text-[10px] font-semibold uppercase tracking-widest text-muted dark:text-white/25">Sessions</p>
          <button
            onClick={onNewSession}
            disabled={creating}
            title="New Session"
            className="flex items-center gap-1 text-[10px] text-indigo-500 dark:text-indigo-400/70 hover:text-indigo-600 dark:hover:text-indigo-300 disabled:opacity-40 transition-colors"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 5v14M5 12h14" />
            </svg>
            {creating ? "..." : "New"}
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto pb-2">
        {sessions.length === 0 && (
          <p className="px-4 py-3 text-xs text-muted dark:text-white/30">No sessions yet</p>
        )}
        {sessions.map((s) => {
          const isActive = s.session_id === activeSessionId;
          const isPending = pendingDeleteId === s.session_id;
          return (
            <div
              key={s.session_id}
              className="relative group/item mx-1"
              onMouseLeave={() => {
                if (isPending) setPendingDeleteId(null);
              }}
            >
              <Link
                href={`/chat/${s.session_id}`}
                className={`block px-3 py-2.5 pr-7 text-xs rounded-md transition-colors ${
                  isActive
                    ? "bg-indigo-100 dark:bg-indigo-500/15 text-indigo-700 dark:text-white"
                    : "text-muted dark:text-white/45 hover:bg-surface dark:hover:bg-white/5 hover:text-foreground dark:hover:text-white/75"
                }`}
              >
                {isActive && (
                  <span className="absolute left-1 top-0 bottom-0 w-0.5 bg-indigo-500 dark:bg-indigo-400 rounded-r" />
                )}
                <span
                  className="block font-medium leading-snug line-clamp-2"
                  title={s.title ?? s.goal ?? "New Session"}
                >
                  {s.title ?? s.goal ?? "New Session"}
                </span>
                <span className="text-[10px] text-muted dark:text-white/30 mt-0.5 block">
                  {formatSessionDate(s.created_at)}
                </span>
              </Link>
              {isPending ? (
                <button
                  type="button"
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    setPendingDeleteId(null);
                    onDelete(s.session_id);
                  }}
                  aria-label="Confirm delete"
                  title="Click to confirm delete"
                  className="absolute right-1.5 top-3 px-1 py-0.5 text-red-500 dark:text-red-400 hover:text-red-600 dark:hover:text-red-300 transition-colors"
                >
                  <Trash2 size={13} />
                </button>
              ) : (
                <button
                  type="button"
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    setPendingDeleteId(s.session_id);
                  }}
                  aria-label="Delete session"
                  title="Delete session"
                  className="absolute right-1.5 top-3 opacity-0 group-hover/item:opacity-100 px-1 py-0.5 text-muted dark:text-white/30 hover:text-foreground dark:hover:text-white/60 transition-all text-[11px] font-bold tracking-tight"
                >
                  ...
                </button>
              )}
            </div>
          );
        })}
      </div>

      {/* User area */}
      <div ref={profileRef} className="border-t border-border dark:border-white/8 px-3 py-3 shrink-0 relative">
        {profileOpen && (
          <div className="absolute bottom-full left-2 right-2 mb-1 bg-background dark:bg-[#0F1629] border border-border dark:border-white/10 rounded-lg shadow-xl overflow-hidden">
            <Link
              href="/settings"
              onClick={() => setProfileOpen(false)}
              className="flex items-center gap-2.5 px-3 py-2.5 text-xs text-muted dark:text-white/60 hover:text-foreground dark:hover:text-white hover:bg-surface dark:hover:bg-white/5 transition-colors"
            >
              <Database size={13} className="text-indigo-500 dark:text-indigo-400 shrink-0" />
              Data Generation
            </Link>
            <Link
              href="/settings"
              onClick={() => setProfileOpen(false)}
              className="flex items-center gap-2.5 px-3 py-2.5 text-xs text-muted dark:text-white/60 hover:text-foreground dark:hover:text-white hover:bg-surface dark:hover:bg-white/5 transition-colors"
            >
              <Settings size={13} className="text-muted dark:text-white/40 shrink-0" />
              Settings
            </Link>
          </div>
        )}
        <button
          onClick={() => setProfileOpen((prev) => !prev)}
          className="w-full flex items-center gap-2.5 px-1 rounded-md hover:bg-surface dark:hover:bg-white/5 transition-colors py-0.5"
        >
          <div className="w-7 h-7 rounded-full bg-indigo-100 dark:bg-indigo-600/40 border border-indigo-300 dark:border-indigo-500/30 flex items-center justify-center shrink-0">
            <User size={14} className="text-indigo-500 dark:text-indigo-300" />
          </div>
          <div className="min-w-0 flex-1 text-left">
            <p className="text-xs font-medium text-foreground dark:text-white/70 truncate">User</p>
            <p className="text-[10px] text-muted dark:text-white/35 truncate">Supply Chain Analyst</p>
          </div>
          {profileOpen
            ? <ChevronUp size={12} className="text-muted dark:text-white/30 shrink-0" />
            : <ChevronDown size={12} className="text-muted dark:text-white/30 shrink-0" />
          }
        </button>
      </div>
    </aside>
  );
}
