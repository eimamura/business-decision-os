"use client";

import type { ChatMessage } from "@/types/chat";
import UserBubble from "./bubbles/UserBubble";
import AssistantBubble from "./bubbles/AssistantBubble";
import SqlQueryBubble from "./bubbles/SqlQueryBubble";
import AskUserBubble from "./bubbles/AskUserBubble";
import JobApprovalBubble from "./bubbles/JobApprovalBubble";
import JobFilesBubble from "./bubbles/JobFilesBubble";

interface MessageBubbleProps {
  message: ChatMessage;
  sessionId?: string;
  onFeedback?: (messageId: string, feedback: 1 | -1) => void;
  onAskUserAnswered?: (answer: string) => Promise<void>;
}

export default function MessageBubble({
  message,
  sessionId,
  onFeedback,
  onAskUserAnswered,
}: MessageBubbleProps): React.JSX.Element {
  switch (message.role) {
    case "user":
      return <UserBubble message={message} />;
    case "assistant":
      return (
        <AssistantBubble
          message={message}
          sessionId={sessionId}
          onFeedback={onFeedback}
        />
      );
    case "tool":
      return <SqlQueryBubble message={message} />;
    case "ask_user":
      return (
        <AskUserBubble
          message={message}
          sessionId={sessionId}
          onAskUserAnswered={onAskUserAnswered}
        />
      );
    case "job_approval":
      return <JobApprovalBubble message={message} />;
    case "job_files":
      return <JobFilesBubble message={message} />;
  }
}
