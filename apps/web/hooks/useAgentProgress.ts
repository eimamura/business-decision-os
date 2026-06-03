"use client";

import { useChatStateContext } from "@/app/chat/ChatStateContext";
import type { AgentNodeState } from "@/types/chat";

export interface AgentProgressState {
  nodes: AgentNodeState[];
  executionMode: string | undefined;
  isRunning: boolean;
}

export function useAgentProgress(sessionId: string): AgentProgressState {
  const { getSessionState } = useChatStateContext();
  const { agentNodes, executionMode, isSending } = getSessionState(sessionId);
  return {
    nodes: agentNodes,
    executionMode,
    isRunning: isSending,
  };
}
