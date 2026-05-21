"use client";

import { useCallback, useRef, useState } from "react";
import { fetchMessages, postMessage, setFeedback, streamSession } from "@/lib/api";
import type { ChatMessage, SessionUsage } from "@/types/chat";

export function useChat(sessionId: string): {
  messages: ChatMessage[];
  isSending: boolean;
  usage: SessionUsage;
  loadMessages: () => Promise<void>;
  sendMessage: (text: string) => Promise<void>;
  submitFeedback: (messageId: string, feedback: 1 | -1) => Promise<void>;
} {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isSending, setIsSending] = useState(false);
  const [usage, setUsage] = useState<SessionUsage>({ inputTokens: 0, outputTokens: 0, costUsd: 0 });
  const abortRef = useRef<AbortController | null>(null);

  const loadMessages = useCallback(async () => {
    const fetched = await fetchMessages(sessionId);
    setMessages(fetched);
  }, [sessionId]);

  const sendMessage = useCallback(async (text: string) => {
    if (!text.trim() || isSending) return;

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: text,
      created_at: new Date().toISOString(),
    };

    const assistantId = crypto.randomUUID();
    const assistantMsg: ChatMessage = {
      id: assistantId,
      role: "assistant",
      content: "",
      isStreaming: true,
      created_at: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMsg, assistantMsg]);
    setIsSending(true);

    try {
      await postMessage(sessionId, text);

      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      for await (const event of streamSession(sessionId, controller.signal)) {
        if (event.type === "done") {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? {
                    ...m,
                    content: event.reply ?? m.content,
                    messageId: event.message_id ?? m.messageId,
                    isStreaming: false,
                  }
                : m,
            ),
          );
          break;
        }

        if (event.type === "step_completed" && event.tokens != null) {
          const half = Math.floor(event.tokens / 2);
          setUsage((prev) => ({
            inputTokens: prev.inputTokens + half,
            outputTokens: prev.outputTokens + (event.tokens! - half),
            costUsd: prev.costUsd + (event.cost_usd ?? 0),
          }));
        }

        if (
          event.type === "tool_completed" &&
          (event.tool_name === "sql_query" || event.tool_name === "nl_query") &&
          event.executed_query
        ) {
          const sqlMsg: ChatMessage = {
            id: crypto.randomUUID(),
            role: "tool",
            content: "",
            toolName: event.tool_name,
            sql: event.executed_query,
            created_at: new Date().toISOString(),
          };
          setMessages((prev) => {
            const idx = prev.findIndex((m) => m.id === assistantId);
            if (idx === -1) return [...prev, sqlMsg];
            return [...prev.slice(0, idx), sqlMsg, ...prev.slice(idx)];
          });
        }

        if (event.type === "error") {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? {
                    ...m,
                    content: event.message ?? "An error occurred during processing.",
                    isError: true,
                    isStreaming: false,
                  }
                : m,
            ),
          );
          break;
        }
      }
    } catch (err: unknown) {
      if (err instanceof Error && err.name === "AbortError") return;
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? {
                ...m,
                content: "Error contacting the API. Please check the backend is running.",
                isError: true,
                isStreaming: false,
              }
            : m,
        ),
      );
    } finally {
      setIsSending(false);
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId ? { ...m, isStreaming: false } : m,
        ),
      );
    }
  }, [sessionId, isSending]);

  const submitFeedback = useCallback(async (messageId: string, feedback: 1 | -1) => {
    setMessages((prev) =>
      prev.map((m) => (m.messageId === messageId ? { ...m, feedback } : m)),
    );
    await setFeedback(sessionId, messageId, feedback);
  }, [sessionId]);

  return { messages, isSending, usage, loadMessages, sendMessage, submitFeedback };
}
