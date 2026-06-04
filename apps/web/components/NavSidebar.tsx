"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { User, ChevronUp, ChevronDown, Database, Settings } from "lucide-react";
import { useState, useEffect, useRef } from "react";
import { NAV_ITEMS } from "@/lib/navItems";

export default function NavSidebar(): React.ReactElement {
  const pathname = usePathname();
  const [profileOpen, setProfileOpen] = useState(false);
  const profileRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent): void {
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
      <div className="px-3 pt-3 pb-2 flex-1">
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
