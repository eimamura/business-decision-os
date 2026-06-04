"use client";

import type { ChatMessage } from "@/types/chat";
import BubbleShell from "./BubbleShell";

interface JobFilesBubbleProps {
  message: ChatMessage;
}

export default function JobFilesBubble({ message }: JobFilesBubbleProps): React.JSX.Element {
  const files = message.jobFiles ?? [];

  return (
    <BubbleShell
      side="left"
      avatar={<span className="text-[10px] text-emerald-400">F</span>}
      avatarBorder="border-emerald-900/40"
    >
      <div className="max-w-[78%] rounded-xl bg-[#0b1a15] border border-emerald-900/40 px-3 py-2 text-xs">
        <p className="font-semibold text-emerald-400 mb-1.5">Job output files</p>
        <ul className="space-y-1">
          {files.map((f) => (
            <li key={f.download_url}>
              <a
                href={f.download_url}
                target="_blank"
                rel="noreferrer"
                className="text-indigo-400 underline underline-offset-2 hover:text-indigo-300 break-all"
              >
                {f.file_name}
              </a>
            </li>
          ))}
        </ul>
      </div>
    </BubbleShell>
  );
}
