"use client";

import { createContext, useCallback, useContext, useRef, useState } from "react";
import type { ReactNode } from "react";
import {
  fetchMessages,
  fetchSessionUsage,
  postMessage,
  setFeedback,
  streamSession,
  updateSessionTitle,
} from "@/lib/api";
import type { ChatMessage, SessionUsage, SseEvent } from "@/types/chat";

interface SessionState {
  messages: ChatMessage[];
  isSending: boolean;
  usage: SessionUsage;
  isLoadingMessages: boolean;
}

const DEFAULT_USAGE: SessionUsage = { inputTokens: 0, outputTokens: 0, costUsd: 0 };

const DEFAULT_STATE: SessionState = {
  messages: [],
  isSending: false,
  usage: DEFAULT_USAGE,
  isLoadingMessages: true,
};

interface ChatStateContextValue {
  getSessionState: (sessionId: string) => SessionState;
  loadMessages: (sessionId: string) => Promise<void>;
  sendMessage: (
    sessionId: string,
    text: string,
    onTitleGenerated?: (title: string) => void,
  ) => Promise<void>;
  submitFeedback: (sessionId: string, messageId: string, feedback: 1 | -1) => Promise<void>;
}

const ChatStateContext = createContext<ChatStateContextValue | null>(null);

export function useChatStateContext(): ChatStateContextValue {
  const ctx = useContext(ChatStateContext);
  if (ctx === null) {
    throw new Error("useChatStateContext must be used within ChatStateProvider");
  }
  return ctx;
}

export function ChatStateProvider({ children }: { children: ReactNode }): React.ReactElement {
  const [sessions, setSessions] = useState<Record<string, SessionState>>({});
  // Per-session refs — keyed by sessionId, never cause re-renders
  const titleSetRef = useRef<Record<string, boolean>>({});
  const isSendingRef = useRef<Record<string, boolean>>({});
  const abortMap = useRef<Record<string, AbortController>>({});

  const getSessionState = useCallback(
    (sessionId: string): SessionState => sessions[sessionId] ?? DEFAULT_STATE,
    [sessions],
  );

  const updateSession = useCallback(
    (
      sessionId: string,
      update: Partial<SessionState> | ((prev: SessionState) => SessionState),
    ): void => {
      setSessions((prev) => {
        const current = prev[sessionId] ?? { ...DEFAULT_STATE };
        const next =
          typeof update === "function" ? update(current) : { ...current, ...update };
        return { ...prev, [sessionId]: next };
      });
    },
    [],
  );

  const loadMessages = useCallback(
    async (sessionId: string): Promise<void> => {
      // Don't overwrite in-flight streaming messages
      if (isSendingRef.current[sessionId]) return;
      updateSession(sessionId, (prev) => ({ ...prev, isLoadingMessages: true }));
      try {
        const fetched = await fetchMessages(sessionId);
        if (fetched.length > 0) {
          titleSetRef.current[sessionId] = true;
        }
        updateSession(sessionId, { messages: fetched, isLoadingMessages: false });
      } catch {
        updateSession(sessionId, (prev) => ({ ...prev, isLoadingMessages: false }));
      }
    },
    [updateSession],
  );

  const sendMessage = useCallback(
    async (
      sessionId: string,
      text: string,
      onTitleGenerated?: (title: string) => void,
    ): Promise<void> => {
      if (!text.trim() || isSendingRef.current[sessionId]) return;
      isSendingRef.current[sessionId] = true;

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

      updateSession(sessionId, (prev) => ({
        ...prev,
        messages: [...prev.messages, userMsg, assistantMsg],
        isSending: true,
      }));

      try {
        abortMap.current[sessionId]?.abort();
        const controller = new AbortController();
        abortMap.current[sessionId] = controller;

        // Open SSE stream before posting — ensures no events are missed in the
        // gap between postMessage returning and the stream reader being established.
        // The backend's GET /stream blocks until a message is posted; this ordering is safe.
        const initialStream = await streamSession(sessionId, controller.signal);

        await postMessage(sessionId, text);

        // Stream with auto-reconnect and exponential backoff (T-054).
        // Retries up to 3 times on unexpected stream close (no `done` event).
        // Delays: 500ms, 1s, 2s. Honours the AbortController for navigation/new-message.
        const MAX_RETRIES = 3;
        let attempt = 0;
        let receivedDone = false;

        while (attempt <= MAX_RETRIES && !receivedDone) {
          if (attempt > 0) {
            const delay = Math.min(500 * Math.pow(2, attempt - 1), 4000);
            await new Promise<void>((resolve) => setTimeout(resolve, delay));
            if (controller.signal.aborted) return;
          }

          let stream: AsyncGenerator<SseEvent>;
          if (attempt === 0) {
            stream = initialStream;
          } else {
            try {
              stream = await streamSession(sessionId, controller.signal);
            } catch {
              attempt++;
              continue;
            }
          }

          for await (const event of stream) {
            if (event.type === "done") {
              receivedDone = true;
              updateSession(sessionId, (prev) => ({
                ...prev,
                messages: prev.messages.map((m) =>
                  m.id === assistantId
                    ? { ...m, content: event.reply ?? m.content, isStreaming: false }
                    : m,
                ),
              }));
              fetchSessionUsage(sessionId)
                .then((usage) => updateSession(sessionId, (prev) => ({ ...prev, usage })))
                .catch(() => undefined);
              if (!titleSetRef.current[sessionId] && onTitleGenerated) {
                titleSetRef.current[sessionId] = true;
                const titleText = text.slice(0, 60).trim();
                updateSessionTitle(sessionId, titleText)
                  .then(() => onTitleGenerated(titleText))
                  .catch(() => undefined);
              }
              break;
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
              updateSession(sessionId, (prev) => {
                const idx = prev.messages.findIndex((m) => m.id === assistantId);
                const msgs =
                  idx === -1
                    ? [...prev.messages, sqlMsg]
                    : [...prev.messages.slice(0, idx), sqlMsg, ...prev.messages.slice(idx)];
                return { ...prev, messages: msgs };
              });
            }

            if (event.type === "awaiting_approval" && event.tool_name === "job_dispatch") {
              const toolInput = event.tool_input as {
                job_type?: string;
                params?: Record<string, unknown>;
                description?: string;
              };
              const approvalMsg: ChatMessage = {
                id: crypto.randomUUID(),
                role: "job_approval",
                content: "",
                approvalId: event.approval_id,
                jobId: event.job_id ?? null,
                jobType: toolInput.job_type ?? "unknown",
                jobDescription: event.description,
                jobParams: toolInput.params ?? {},
                created_at: new Date().toISOString(),
              };
              updateSession(sessionId, (prev) => {
                const idx = prev.messages.findIndex((m) => m.id === assistantId);
                const msgs =
                  idx === -1
                    ? [...prev.messages, approvalMsg]
                    : [
                        ...prev.messages.slice(0, idx),
                        approvalMsg,
                        ...prev.messages.slice(idx),
                      ];
                return { ...prev, messages: msgs };
              });
            }

            if (event.type === "job_completed" && event.files.length > 0) {
              const filesMsg: ChatMessage = {
                id: crypto.randomUUID(),
                role: "job_files",
                content: "",
                jobId: event.job_id,
                jobFiles: event.files,
                created_at: new Date().toISOString(),
              };
              updateSession(sessionId, (prev) => ({
                ...prev,
                messages: [...prev.messages, filesMsg],
              }));
            }

            if (event.type === "error") {
              updateSession(sessionId, (prev) => ({
                ...prev,
                messages: prev.messages.map((m) =>
                  m.id === assistantId
                    ? {
                        ...m,
                        content: event.message ?? "An error occurred during processing.",
                        isError: true,
                        isStreaming: false,
                      }
                    : m,
                ),
              }));
              // Treat a server-side error event as terminal — do not retry.
              receivedDone = true;
              break;
            }
          }

          if (!receivedDone) {
            attempt++;
          }
        }

        if (!receivedDone) {
          // All retries exhausted — stream closed without a done/error event.
          updateSession(sessionId, (prev) => ({
            ...prev,
            messages: prev.messages.map((m) =>
              m.id === assistantId
                ? {
                    ...m,
                    content: "Network error — check your connection.",
                    isError: true,
                    isStreaming: false,
                    errorCode: "network_error" as const,
                  }
                : m,
            ),
          }));
        }
      } catch (err: unknown) {
        if (err instanceof Error && err.name === "AbortError") return;

        let errorMessage = "Error contacting the API. Please check the backend is running.";
        let errorCode: ChatMessage["errorCode"] = "unknown_error";

        if (err instanceof TypeError && err.message.includes("Failed to fetch")) {
          errorMessage = "Network error — check your connection.";
          errorCode = "network_error";
        } else if (err instanceof Error && "status" in err) {
          const status = (err as Error & { status: number }).status;
          if (status >= 500) {
            errorMessage = `Server error (${status}). The backend may be overloaded.`;
            errorCode = "server_error";
          }
        }

        updateSession(sessionId, (prev) => ({
          ...prev,
          messages: prev.messages.map((m) =>
            m.id === assistantId
              ? {
                  ...m,
                  content: errorMessage,
                  isError: true,
                  isStreaming: false,
                  errorCode,
                }
              : m,
          ),
        }));
      } finally {
        isSendingRef.current[sessionId] = false;
        updateSession(sessionId, (prev) => ({
          ...prev,
          isSending: false,
          messages: prev.messages.map((m) =>
            m.id === assistantId ? { ...m, isStreaming: false } : m,
          ),
        }));
      }
    },
    [updateSession],
  );

  const submitFeedback = useCallback(
    async (sessionId: string, messageId: string, feedback: 1 | -1): Promise<void> => {
      updateSession(sessionId, (prev) => ({
        ...prev,
        messages: prev.messages.map((m) =>
          m.messageId === messageId ? { ...m, feedback } : m,
        ),
      }));
      await setFeedback(sessionId, messageId, feedback);
    },
    [updateSession],
  );

  return (
    <ChatStateContext.Provider
      value={{ getSessionState, loadMessages, sendMessage, submitFeedback }}
    >
      {children}
    </ChatStateContext.Provider>
  );
}
