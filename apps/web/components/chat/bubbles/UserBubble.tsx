"use client";

import { useState } from "react";
import { CopyIcon, CheckIcon } from "lucide-react";
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

  const copyAction = (
    <button
      type="button"
      onClick={handleCopy}
      aria-label={copyState === "copied" ? "copied" : "copy message"}
      title={copyState === "copied" ? "Copied!" : "Copy"}
      className="text-indigo-300/40 hover:text-indigo-200 transition-colors"
    >
      {copyState === "copied" ? (
        <CheckIcon className="h-3.5 w-3.5" />
      ) : (
        <CopyIcon className="h-3.5 w-3.5" />
      )}
    </button>
  );

  return (
    <BubbleShell
      side="right"
      avatar={<span className="text-xs text-indigo-600 font-medium">U</span>}
      avatarBg="bg-indigo-100"
      timestamp={message.created_at}
      actions={copyAction}
    >
      <div className="rounded-2xl px-4 py-2.5 text-sm bg-indigo-600 text-white rounded-tr-sm">
        <p className="leading-relaxed whitespace-pre-wrap">{message.content}</p>
      </div>
    </BubbleShell>
  );
}
