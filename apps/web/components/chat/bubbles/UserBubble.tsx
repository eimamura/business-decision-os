"use client";

import { useState } from "react";
import { ClipboardIcon, CheckIcon } from "lucide-react";
import type { ChatMessage } from "@/types/chat";
import BubbleShell from "./BubbleShell";

interface UserBubbleProps {
  message: ChatMessage;
}

export default function UserBubble({ message }: UserBubbleProps): React.JSX.Element {
  const [copyState, setCopyState] = useState<"idle" | "copied">("idle");

  function handleCopy(): void {
    navigator.clipboard.writeText(message.content ?? "").then(() => {
      setCopyState("copied");
      setTimeout(() => setCopyState("idle"), 2000);
    });
  }

  return (
    <div className="group">
      <BubbleShell
        side="right"
        avatar={<span className="text-xs text-indigo-600 font-medium">U</span>}
        avatarBg="bg-indigo-100"
        timestamp={message.created_at}
      >
        <div className="flex items-start gap-1.5">
          <button
            type="button"
            onClick={handleCopy}
            className="self-center opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded text-indigo-300/60 hover:text-indigo-200 hover:bg-indigo-900/30"
            aria-label={copyState === "copied" ? "Copied!" : "Copy message"}
            title={copyState === "copied" ? "Copied!" : "Copy message"}
          >
            {copyState === "copied" ? (
              <CheckIcon className="h-3.5 w-3.5" />
            ) : (
              <ClipboardIcon className="h-3.5 w-3.5" />
            )}
          </button>
          <div className="rounded-2xl px-4 py-2.5 text-sm bg-indigo-600 text-white rounded-tr-sm">
            <p className="leading-relaxed whitespace-pre-wrap">{message.content}</p>
          </div>
        </div>
      </BubbleShell>
    </div>
  );
}
