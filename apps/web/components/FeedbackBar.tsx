"use client";

import { ThumbsDown, ThumbsUp } from "lucide-react";

interface FeedbackBarProps {
  messageId: string;
  feedback?: 1 | -1;
  onFeedback: (messageId: string, value: 1 | -1) => void;
}

export default function FeedbackBar({
  messageId,
  feedback,
  onFeedback,
}: FeedbackBarProps): React.ReactElement {
  return (
    <div className="mt-2 mb-4 flex items-center gap-2 pl-10 text-xs text-slate-500">
      <span className="font-normal">Was this helpful?</span>

      <button
        onClick={() => onFeedback(messageId, 1)}
        aria-label="Helpful"
        className={`flex h-7 w-7 items-center justify-center rounded-full border transition-all ${
          feedback === 1
            ? "border-emerald-400/40 bg-emerald-500/10 text-emerald-300"
            : "border-slate-700/70 bg-slate-900/40 text-slate-400 hover:border-emerald-400/40 hover:bg-emerald-500/10 hover:text-emerald-300"
        }`}
      >
        <ThumbsUp size={14} strokeWidth={1.8} />
      </button>

      <button
        onClick={() => onFeedback(messageId, -1)}
        aria-label="Not helpful"
        className={`flex h-7 w-7 items-center justify-center rounded-full border transition-all ${
          feedback === -1
            ? "border-rose-400/40 bg-rose-500/10 text-rose-300"
            : "border-slate-700/70 bg-slate-900/40 text-slate-400 hover:border-rose-400/40 hover:bg-rose-500/10 hover:text-rose-300"
        }`}
      >
        <ThumbsDown size={14} strokeWidth={1.8} />
      </button>
    </div>
  );
}
