"use client";

import { useState } from "react";
import { ClipboardIcon, CheckIcon } from "lucide-react";
import type { ChatMessage } from "@/types/chat";
import BubbleShell from "./BubbleShell";
import DynamicSyntaxHighlighter from "./DynamicSyntaxHighlighter";

interface SqlQueryBubbleProps {
  message: ChatMessage;
}

export default function SqlQueryBubble({ message }: SqlQueryBubbleProps): React.JSX.Element {
  const label = message.toolName === "nl_query" ? "NL → SQL" : "SQL Query";
  const [copyState, setCopyState] = useState<"idle" | "copied">("idle");

  function handleCopy(): void {
    if (!message.sql) return;
    navigator.clipboard.writeText(message.sql).then(() => {
      setCopyState("copied");
      setTimeout(() => setCopyState("idle"), 2000);
    });
  }

  return (
    <BubbleShell
      side="left"
      avatar={<span className="text-[10px] text-emerald-400">⚙</span>}
      avatarBorder="border-emerald-900/40"
      timestamp={message.created_at}
    >
      <div className="rounded-xl bg-[#0b1a15] border border-emerald-900/40 px-3 pt-2 pb-1">
        <div className="flex items-center gap-1.5 mb-1.5">
          <span className="text-xs font-mono font-bold text-emerald-500 uppercase tracking-wider">
            {label}
          </span>
          {message.sql && (
            <button
              type="button"
              onClick={handleCopy}
              className="ml-auto p-1 rounded text-emerald-500/60 hover:text-emerald-400 hover:bg-emerald-900/30 transition-colors"
              aria-label={copyState === "copied" ? "Copied!" : "Copy SQL"}
              title={copyState === "copied" ? "Copied!" : "Copy SQL"}
            >
              {copyState === "copied" ? (
                <CheckIcon className="h-4 w-4" />
              ) : (
                <ClipboardIcon className="h-4 w-4" />
              )}
            </button>
          )}
        </div>
        {message.sql && (
          <DynamicSyntaxHighlighter language="sql">
            {message.sql}
          </DynamicSyntaxHighlighter>
        )}
      </div>
    </BubbleShell>
  );
}
