"use client";

import { createContext, useCallback, useContext, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  fetchMessages,
  fetchSessionEvents,
  fetchSessionUsage,
  postAskUserAnswer,
  postMessage,
  setFeedback,
  streamSession,
  updateSessionTitle,
} from "@/lib/api";
import { queryKeys } from "@/lib/queryKeys";
import type { AgentNodeState, AgentNodeToolCall, ChatMessage, SessionUsage, SseEvent } from "@/types/chat";
import type { GraphRunNode } from "@/types/workspace";

/**
 * Inspects persisted session events and returns a synthetic ask_user ChatMessage if the
 * session is currently paused waiting for user input (awaiting_input is the last terminal
 * event and there is no response_ready after it).
 */
function _extractPendingAskUser(
  events: SseEvent[],
  existingMessages: ChatMessage[],
): ChatMessage | null {
  if (existingMessages.some((m) => m.role === "ask_user")) return null;

  let lastAskUser: Extract<SseEvent, { type: "ask_user_required" }> | null = null;
  let lastAwaitingInputTs: string | null = null;
  let lastResponseReadyTs: string | null = null;

  for (const ev of events) {
    if (ev.type === "ask_user_required") lastAskUser = ev;
    if (ev.type === "awaiting_input") lastAwaitingInputTs = ev.timestamp;
    if (ev.type === "response_ready") lastResponseReadyTs = ev.timestamp;
  }

  if (!lastAskUser || !lastAwaitingInputTs) return null;
  if (lastResponseReadyTs && lastResponseReadyTs > lastAwaitingInputTs) return null;

  return {
    id: lastAskUser.ask_user_id,
    role: "ask_user",
    content: "",
    askUserId: lastAskUser.ask_user_id,
    askUserQuestion: lastAskUser.question,
    askUserSuggestions: lastAskUser.suggestions,
    created_at: lastAskUser.timestamp,
  };
}

const AGENT_DISPLAY_NAMES: Record<string, string> = {
  demand: "Demand Analyst",
  inventory: "Inventory Specialist",
  replenishment: "Replenishment Planner",
  data_engineer: "Data Engineer",
  risk: "Risk Analyst",
  supply_chain: "Supply Chain Analyst",
};

interface SessionState {
  messages: ChatMessage[];
  isSending: boolean;
  usage: SessionUsage;
  isLoadingMessages: boolean;
  graphRun: GraphRunNode[];
  sessionStartedAt: string | null;
  sessionEndedAt: string | null;
}

const DEFAULT_USAGE: SessionUsage = { inputTokens: 0, outputTokens: 0, costUsd: 0 };

const DEFAULT_STATE: SessionState = {
  messages: [],
  isSending: false,
  usage: DEFAULT_USAGE,
  isLoadingMessages: true,
  graphRun: [],
  sessionStartedAt: null,
  sessionEndedAt: null,
};

type DerivedSessionState = SessionState & {
  agentNodes: AgentNodeState[];
  executionMode: string | undefined;
};

interface ChatStateContextValue {
  getSessionState: (sessionId: string) => DerivedSessionState;
  loadMessages: (sessionId: string) => Promise<void>;
  sendMessage: (
    sessionId: string,
    text: string,
    onTitleGenerated?: (title: string) => void,
  ) => Promise<void>;
  sendAskUserAnswer: (sessionId: string, answer: string) => Promise<void>;
  submitFeedback: (sessionId: string, messageId: string, feedback: 1 | -1) => Promise<void>;
  appendAssistantReply: (sessionId: string, reply: string) => void;
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
  const queryClient = useQueryClient();
  const [sessions, setSessions] = useState<Record<string, SessionState>>({});
  const titleSetRef = useRef<Record<string, boolean>>({});
  const isSendingRef = useRef<Record<string, boolean>>({});
  const abortMap = useRef<Record<string, AbortController>>({});
  const hasStreamedRef = useRef<Record<string, boolean>>({});

  const getSessionState = useCallback(
    (sessionId: string): DerivedSessionState => {
      const base = sessions[sessionId] ?? DEFAULT_STATE;
      const { graphRun } = base;

      const agentNodes: AgentNodeState[] = graphRun
        .filter((n) => n.kind === "agent")
        .map((n) => ({
          taskId: n.runId,
          agentName:
            AGENT_DISPLAY_NAMES[n.name] ??
            n.name.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
          agentRole: n.name,
          status: (n.status === "failed" ? "error" : n.status) as AgentNodeState["status"],
          startedAt: n.startedAt,
          durationMs: n.durationMs,
          inputSummary:
            typeof n.meta?.input_summary === "string" ? n.meta.input_summary : undefined,
          toolCalls: graphRun
            .filter((t) => t.kind === "tool" && t.parentRunId === n.runId)
            .map((t) => ({
              toolCallId: t.runId,
              toolName: t.name,
              status: (t.status === "failed" ? "error" : t.status) as AgentNodeToolCall["status"],
              durationMs: t.durationMs,
            })),
        }));

      const routeNode = graphRun.find(
        (n) =>
          n.kind === "orchestrator" && n.name === "select_mode" && n.status !== "running",
      );
      const executionMode =
        typeof routeNode?.meta?.mode === "string" ? routeNode.meta.mode : undefined;

      return { ...base, agentNodes, executionMode };
    },
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

  /** Rebuild a GraphRunNode map from persisted session events. */
  const _hydrateGraphRunFromEvents = useCallback(
    (sessionId: string, events: SseEvent[]): void => {
      const nodeMap = new Map<string, GraphRunNode>();
      let sessionStartedAt: string | null = null;
      let sessionEndedAt: string | null = null;
      let lastTerminalWasAwaitingInput = false;
      for (const ev of events) {
        if (ev.type === "response_ready") {
          sessionEndedAt = ev.timestamp;
          lastTerminalWasAwaitingInput = false;
          continue;
        }
        if (ev.type === "awaiting_input") {
          lastTerminalWasAwaitingInput = true;
          continue;
        }
        if (ev.type !== "graph_node") continue;
        if (ev.event === "start") {
          if (!sessionStartedAt) sessionStartedAt = ev.timestamp;
          nodeMap.set(ev.run_id, {
            runId: ev.run_id,
            parentRunId: ev.parent_run_id ?? undefined,
            kind: ev.kind,
            name: ev.name,
            status: "running",
            startedAt: ev.timestamp,
          });
        } else {
          const existing = nodeMap.get(ev.run_id);
          nodeMap.set(ev.run_id, {
            ...(existing ?? {
              runId: ev.run_id,
              parentRunId: ev.parent_run_id ?? undefined,
              kind: ev.kind,
              name: ev.name,
              startedAt: ev.timestamp,
              status: "running" as const,
            }),
            status: ev.status === "error" ? "failed" : "completed",
            completedAt: ev.timestamp,
            durationMs: ev.duration_ms ?? undefined,
            meta: ev.meta != null && Object.keys(ev.meta).length > 0 ? ev.meta : undefined,
            output: ev.output ?? undefined,
            tokenCost: ev.token_cost
              ? {
                  inputTokens: ev.token_cost.input_tokens,
                  outputTokens: ev.token_cost.output_tokens,
                  costUsd: ev.token_cost.cost_usd,
                }
              : undefined,
          });
        }
      }
      // When session paused at awaiting_input, LangGraph's interrupt() skips on_chain_end
      // for the interrupted node — so it stays "running" in the map. Promote to "completed".
      if (lastTerminalWasAwaitingInput) {
        for (const [id, node] of nodeMap) {
          if (node.status === "running") nodeMap.set(id, { ...node, status: "completed" });
        }
      }

      // Only hydrate from DB when the session is not actively streaming events via SSE.
      // If isSending is true, the SSE stream is the authoritative source and DB hydration
      // would race against in-flight SSE events.
      if ((nodeMap.size > 0 || sessionEndedAt !== null) && !isSendingRef.current[sessionId]) {
        updateSession(sessionId, (prev) => ({
          ...prev,
          graphRun: Array.from(nodeMap.values()),
          sessionStartedAt: sessionStartedAt ?? prev.sessionStartedAt,
          sessionEndedAt: sessionEndedAt ?? prev.sessionEndedAt,
        }));
      }
    },
    [updateSession],
  );

  const loadMessages = useCallback(
    async (sessionId: string): Promise<void> => {
      // Skip message loading when a send is already in flight to avoid overwriting
      // optimistic UI state (the in-flight assistant bubble, etc.).
      if (isSendingRef.current[sessionId]) return;

      updateSession(sessionId, (prev) => ({ ...prev, isLoadingMessages: true }));
      try {
        // Fetch messages and events in parallel so we can inject a pending ask_user bubble
        // (stored only in events, not in the messages table) before updating state.
        const [fetched, events] = await Promise.all([
          fetchMessages(sessionId),
          fetchSessionEvents(sessionId).catch((): SseEvent[] => []),
        ]);

        _hydrateGraphRunFromEvents(sessionId, events);

        if (fetched.length > 0) {
          titleSetRef.current[sessionId] = true;
        }

        const pendingAskUser = _extractPendingAskUser(events, fetched);
        const messages = pendingAskUser ? [...fetched, pendingAskUser] : fetched;
        updateSession(sessionId, { messages, isLoadingMessages: false });
      } catch {
        updateSession(sessionId, (prev) => ({ ...prev, isLoadingMessages: false }));
      }
    },
    [updateSession, _hydrateGraphRunFromEvents],
  );

  const _handleGraphNodeEvent = useCallback(
    (sessionId: string, event: Extract<SseEvent, { type: "graph_node" }>): void => {
      updateSession(sessionId, (prev) => {
        if (event.event === "start") {
          if (prev.graphRun.some((n) => n.runId === event.run_id)) return prev;
          const newNode: GraphRunNode = {
            runId: event.run_id,
            parentRunId: event.parent_run_id ?? undefined,
            kind: event.kind,
            name: event.name,
            status: "running",
            startedAt: event.timestamp,
          };
          return {
            ...prev,
            graphRun: [...prev.graphRun, newNode],
            sessionStartedAt: prev.sessionStartedAt ?? event.timestamp,
          };
        } else {
          const idx = prev.graphRun.findIndex((n) => n.runId === event.run_id);
          const base: GraphRunNode =
            idx !== -1
              ? prev.graphRun[idx]
              : {
                  runId: event.run_id,
                  parentRunId: event.parent_run_id ?? undefined,
                  kind: event.kind,
                  name: event.name,
                  startedAt: event.timestamp,
                  status: "running",
                };
          const updatedNode: GraphRunNode = {
            ...base,
            status: event.status === "error" ? "failed" : "completed",
            completedAt: event.timestamp,
            durationMs: event.duration_ms ?? undefined,
            meta:
              event.meta != null && Object.keys(event.meta).length > 0
                ? event.meta
                : base.meta,
            output: event.output ?? base.output,
            tokenCost: event.token_cost
              ? {
                  inputTokens: event.token_cost.input_tokens,
                  outputTokens: event.token_cost.output_tokens,
                  costUsd: event.token_cost.cost_usd,
                }
              : base.tokenCost,
          };
          const graphRun =
            idx !== -1
              ? prev.graphRun.map((n, i) => (i === idx ? updatedNode : n))
              : [...prev.graphRun, updatedNode];
          return { ...prev, graphRun };
        }
      });
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
      hasStreamedRef.current[sessionId] = false;

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
        graphRun: [],
        sessionStartedAt: null,
        sessionEndedAt: null,
      }));

      if (!titleSetRef.current[sessionId] && onTitleGenerated) {
        titleSetRef.current[sessionId] = true;
        const titleText = text.slice(0, 60).trim();
        updateSessionTitle(sessionId, titleText)
          .then(() => onTitleGenerated(titleText))
          .catch(() => undefined);
      }

      try {
        abortMap.current[sessionId]?.abort();
        const controller = new AbortController();
        abortMap.current[sessionId] = controller;

        const initialStream = await streamSession(sessionId, controller.signal);
        await postMessage(sessionId, text);

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
            if (event.type === "text_delta") {
              hasStreamedRef.current[sessionId] = true;
              updateSession(sessionId, (prev) => ({
                ...prev,
                messages: prev.messages.map((m) =>
                  m.id === assistantId
                    ? { ...m, content: (m.content ?? "") + event.delta, isStreaming: true }
                    : m,
                ),
              }));
            }

            if (event.type === "graph_node") {
              _handleGraphNodeEvent(sessionId, event);
            }

            if (event.type === "response_ready") {
              updateSession(sessionId, (prev) => ({
                ...prev,
                sessionEndedAt: event.timestamp,
              }));
            }

            if (
              event.type === "graph_node" &&
              event.event === "end" &&
              event.kind === "tool" &&
              (event.name === "sql_query" || event.name === "nl_query") &&
              typeof event.output?.executed_query === "string"
            ) {
              const sqlMsg: ChatMessage = {
                id: crypto.randomUUID(),
                role: "tool",
                content: "",
                toolName: event.name,
                sql: event.output.executed_query,
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

            if (event.type === "done") {
              const didStream = hasStreamedRef.current[sessionId] ?? false;
              receivedDone = true;
              updateSession(sessionId, (prev) => ({
                ...prev,
                messages: prev.messages.map((m) =>
                  m.id === assistantId
                    ? {
                        ...m,
                        content: didStream ? m.content : (event.reply ?? m.content),
                        isStreaming: false,
                      }
                    : m,
                ),
                isSending: false,
              }));
              fetchSessionUsage(sessionId)
                .then((usage) => updateSession(sessionId, (prev) => ({ ...prev, usage })))
                .catch(() => undefined);
              void queryClient.invalidateQueries({ queryKey: queryKeys.sessions.all });
              hasStreamedRef.current[sessionId] = false;
              break;
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
              void queryClient.invalidateQueries({ queryKey: ["approvals"] });
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
              void queryClient.invalidateQueries({ queryKey: ["jobs"] });
            }

            if (event.type === "ask_user_required") {
              const askUserMsg: ChatMessage = {
                id: crypto.randomUUID(),
                role: "ask_user",
                content: "",
                askUserId: event.ask_user_id,
                askUserQuestion: event.question,
                askUserSuggestions: event.suggestions,
                created_at: new Date().toISOString(),
              };
              updateSession(sessionId, (prev) => {
                const idx = prev.messages.findIndex((m) => m.id === assistantId);
                const msgs =
                  idx === -1
                    ? [...prev.messages, askUserMsg]
                    : [
                        ...prev.messages.slice(0, idx),
                        askUserMsg,
                        ...prev.messages.slice(idx),
                      ];
                return { ...prev, messages: msgs };
              });
            }

            if (event.type === "awaiting_input") {
              receivedDone = true;
              updateSession(sessionId, (prev) => ({
                ...prev,
                messages: prev.messages.filter((m) => m.id !== assistantId),
                // LangGraph's interrupt() skips on_chain_end for the interrupted node,
                // so wait_for_answer (and any other running node) never receives a
                // graph_node end event. Transition all still-running nodes to "completed"
                // so the spinner doesn't spin indefinitely.
                graphRun: prev.graphRun.map((n) =>
                  n.status === "running" ? { ...n, status: "completed" as const } : n,
                ),
              }));
              break;
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
              receivedDone = true;
              break;
            }
          }

          if (!receivedDone) {
            attempt++;
          }
        }

        if (!receivedDone) {
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
    [updateSession, _handleGraphNodeEvent],
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

  const sendAskUserAnswer = useCallback(
    async (sessionId: string, answer: string): Promise<void> => {
      if (isSendingRef.current[sessionId]) return;
      isSendingRef.current[sessionId] = true;
      hasStreamedRef.current[sessionId] = false;

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
        messages: [...prev.messages, assistantMsg],
        isSending: true,
        // Do NOT clear graphRun here — the trace from the first execution half
        // (classify_intent → prepare_ask_user → wait_for_answer) should remain
        // visible while the resumed graph continues running.
      }));

      try {
        abortMap.current[sessionId]?.abort();
        const controller = new AbortController();
        abortMap.current[sessionId] = controller;

        const initialStream = await streamSession(sessionId, controller.signal);
        await postAskUserAnswer(sessionId, answer);

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
            if (event.type === "text_delta") {
              hasStreamedRef.current[sessionId] = true;
              updateSession(sessionId, (prev) => ({
                ...prev,
                messages: prev.messages.map((m) =>
                  m.id === assistantId
                    ? { ...m, content: (m.content ?? "") + event.delta, isStreaming: true }
                    : m,
                ),
              }));
            }

            if (event.type === "graph_node") {
              _handleGraphNodeEvent(sessionId, event);
            }

            if (event.type === "response_ready") {
              updateSession(sessionId, (prev) => ({
                ...prev,
                sessionEndedAt: event.timestamp,
              }));
            }

            if (
              event.type === "graph_node" &&
              event.event === "end" &&
              event.kind === "tool" &&
              (event.name === "sql_query" || event.name === "nl_query") &&
              typeof event.output?.executed_query === "string"
            ) {
              const sqlMsg: ChatMessage = {
                id: crypto.randomUUID(),
                role: "tool",
                content: "",
                toolName: event.name,
                sql: event.output.executed_query,
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

            if (event.type === "done") {
              const didStream = hasStreamedRef.current[sessionId] ?? false;
              receivedDone = true;
              updateSession(sessionId, (prev) => ({
                ...prev,
                messages: prev.messages.map((m) =>
                  m.id === assistantId
                    ? {
                        ...m,
                        content: didStream ? m.content : (event.reply ?? m.content),
                        isStreaming: false,
                      }
                    : m,
                ),
                isSending: false,
              }));
              fetchSessionUsage(sessionId)
                .then((usage) => updateSession(sessionId, (prev) => ({ ...prev, usage })))
                .catch(() => undefined);
              void queryClient.invalidateQueries({ queryKey: queryKeys.sessions.all });
              hasStreamedRef.current[sessionId] = false;
              break;
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
              receivedDone = true;
              break;
            }
          }

          if (!receivedDone) {
            attempt++;
          }
        }

        if (!receivedDone) {
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
        updateSession(sessionId, (prev) => ({
          ...prev,
          messages: prev.messages.map((m) =>
            m.id === assistantId
              ? {
                  ...m,
                  content:
                    "Error contacting the API. Please check the backend is running.",
                  isError: true,
                  isStreaming: false,
                  errorCode: "unknown_error" as const,
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
    [updateSession, _handleGraphNodeEvent],
  );

  const appendAssistantReply = useCallback(
    (sessionId: string, reply: string): void => {
      const msg: ChatMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: reply,
        created_at: new Date().toISOString(),
      };
      updateSession(sessionId, (prev) => ({
        ...prev,
        messages: [...prev.messages, msg],
      }));
    },
    [updateSession],
  );

  return (
    <ChatStateContext.Provider
      value={{
        getSessionState,
        loadMessages,
        sendMessage,
        sendAskUserAnswer,
        submitFeedback,
        appendAssistantReply,
      }}
    >
      {children}
    </ChatStateContext.Provider>
  );
}
