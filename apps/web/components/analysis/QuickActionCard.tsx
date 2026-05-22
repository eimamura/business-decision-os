"use client";

import type { QuickAction } from "@/types/workspace";

interface QuickActionCardProps {
  action: QuickAction;
  onSelect: (prompt: string) => void;
  icon: React.ReactElement;
  iconBgClass: string;
}

export default function QuickActionCard({
  action,
  onSelect,
  icon,
  iconBgClass,
}: QuickActionCardProps): React.ReactElement {
  return (
    <button
      onClick={() => onSelect(action.prompt)}
      className="group relative flex flex-col gap-3 text-left rounded-xl bg-[rgba(15,23,42,0.72)] border border-white/10 p-4 hover:bg-[rgba(30,41,59,0.82)] hover:border-white/20 transition-all backdrop-blur-sm h-40"
    >
      <div className={`w-9 h-9 rounded-lg flex items-center justify-center shrink-0 ${iconBgClass}`}>
        {icon}
      </div>
      <div className="flex flex-col gap-0.5">
        <span className="text-sm font-semibold text-white/85 group-hover:text-white transition-colors">
          {action.title}
        </span>
        <p className="text-xs text-white/45 group-hover:text-white/60 transition-colors leading-relaxed">
          {action.description}
        </p>
      </div>
      <div className="absolute bottom-3 right-3 text-white/20 group-hover:text-white/50 transition-colors">
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M7 17L17 7M7 7h10v10" />
        </svg>
      </div>
    </button>
  );
}
