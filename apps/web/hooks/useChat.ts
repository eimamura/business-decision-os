"use client";

import { useCallback } from "react";
import { useChatStateContext } from "@/app/chat/ChatStateContext";
import type { ChatMessage, SessionUsage } from "@/types/chat";

export function useChat(
  sessionId: string,
  onTitleGenerated?: (title: string) => void,
): {
  messages: ChatMessage[];
  isSending: boolean;
  usage: SessionUsage;
  isLoadingMessages: boolean;
  loadMessages: () => Promise<void>;
  sendMessage: (text: string) => Promise<void>;
  submitFeedback: (messageId: string, feedback: 1 | -1) => Promise<void>;
} {
  const {
    getSessionState,
    loadMessages: ctxLoadMessages,
    sendMessage: ctxSendMessage,
    submitFeedback: ctxSubmitFeedback,
  } = useChatStateContext();

  const state = getSessionState(sessionId);

  const loadMessages = useCallback(
    () => ctxLoadMessages(sessionId),
    [ctxLoadMessages, sessionId],
  );

  const sendMessage = useCallback(
    (text: string) => ctxSendMessage(sessionId, text, onTitleGenerated),
    [ctxSendMessage, sessionId, onTitleGenerated],
  );

  const submitFeedback = useCallback(
    (messageId: string, feedback: 1 | -1) => ctxSubmitFeedback(sessionId, messageId, feedback),
    [ctxSubmitFeedback, sessionId],
  );

  return {
    messages: state.messages,
    isSending: state.isSending,
    usage: state.usage,
    isLoadingMessages: state.isLoadingMessages,
    loadMessages,
    sendMessage,
    submitFeedback,
  };
}
