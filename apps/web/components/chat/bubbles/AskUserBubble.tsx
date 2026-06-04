"use client";

import type { ChatMessage } from "@/types/chat";
import { AskUserInput } from "@/components/AskUserInput";
import BubbleShell from "./BubbleShell";

interface AskUserBubbleProps {
  message: ChatMessage;
  sessionId?: string;
  onAskUserAnswered?: (answer: string) => Promise<void>;
}

export default function AskUserBubble({
  message,
  sessionId,
  onAskUserAnswered,
}: AskUserBubbleProps): React.JSX.Element {
  return (
    <BubbleShell
      side="left"
      avatar={<span className="text-[10px] text-indigo-400">?</span>}
      avatarBorder="border-indigo-900/40"
      maxWidth="max-w-[78%] w-full"
    >
      <AskUserInput
        sessionId={sessionId ?? ""}
        askUserId={message.askUserId ?? ""}
        question={message.askUserQuestion ?? ""}
        suggestions={message.askUserSuggestions ?? []}
        onSubmit={onAskUserAnswered ?? (async () => undefined)}
      />
    </BubbleShell>
  );
}
