import type { ChatMessage, Session, SSEEvent } from "@/types/chat";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const DEV_HEADERS: Record<string, string> = {
  "Content-Type": "application/json",
  "X-Dev-User": "dev-user",
};

export async function fetchSessions(): Promise<Session[]> {
  const res = await fetch(`${API_BASE}/api/v1/sessions`, { headers: DEV_HEADERS });
  if (!res.ok) throw new Error(`fetchSessions: ${res.status}`);
  const data: unknown = await res.json();
  if (Array.isArray(data)) return data as Session[];
  const paginated = data as { items?: Session[] };
  return paginated.items ?? [];
}

export async function createSession(goal?: string): Promise<Session> {
  const res = await fetch(`${API_BASE}/api/v1/sessions`, {
    method: "POST",
    headers: DEV_HEADERS,
    body: JSON.stringify({ goal: goal ?? "" }),
  });
  if (!res.ok) throw new Error(`createSession: ${res.status}`);
  return res.json() as Promise<Session>;
}

export async function fetchMessages(sessionId: string): Promise<ChatMessage[]> {
  const res = await fetch(`${API_BASE}/api/v1/sessions/${sessionId}/messages`, {
    headers: DEV_HEADERS,
  });
  if (!res.ok) return [];
  const data: Array<{
    id: string;
    role: string;
    content: string;
    created_at?: string;
    feedback?: 1 | -1 | null;
  }> = await res.json();
  return data.map((m) => ({
    id: crypto.randomUUID(),
    messageId: m.id,
    role: m.role as MessageRole,
    content: m.content,
    created_at: m.created_at,
    feedback: m.feedback ?? undefined,
  }));
}

type MessageRole = "user" | "assistant";

export async function postMessage(sessionId: string, content: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/v1/sessions/${sessionId}/messages`, {
    method: "POST",
    headers: DEV_HEADERS,
    body: JSON.stringify({ content }),
  });
  if (!res.ok) throw new Error(`postMessage: ${res.status}`);
}

export async function setFeedback(
  sessionId: string,
  messageId: string,
  feedback: 1 | -1,
): Promise<boolean> {
  try {
    const res = await fetch(
      `${API_BASE}/api/v1/sessions/${sessionId}/messages/${messageId}/feedback`,
      {
        method: "PATCH",
        headers: DEV_HEADERS,
        body: JSON.stringify({ feedback }),
      },
    );
    return res.ok;
  } catch {
    return false;
  }
}

export async function* streamSession(
  sessionId: string,
  signal?: AbortSignal,
): AsyncGenerator<SSEEvent> {
  const res = await fetch(`${API_BASE}/api/v1/sessions/${sessionId}/stream`, {
    headers: DEV_HEADERS,
    signal,
  });
  if (!res.ok || !res.body) return;

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          const data = line.slice(6).trim();
          if (!data) continue;
          try {
            yield JSON.parse(data) as SSEEvent;
          } catch {
            // skip malformed lines
          }
        }
      }
    }
  } finally {
    reader.cancel();
  }
}
