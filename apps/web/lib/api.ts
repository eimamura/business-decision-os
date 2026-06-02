import { SseEventSchema } from "@/types/chat";
import type { ChatMessage, Session, SessionUsage, SseEvent } from "@/types/chat";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const DEV_HEADERS: Record<string, string> = {
  "Content-Type": "application/json",
  "X-Dev-User": "dev-user",
};

export async function fetchSession(sessionId: string): Promise<Session | null> {
  const res = await fetch(`${API_BASE}/api/v1/sessions/${sessionId}`, { headers: DEV_HEADERS });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`fetchSession: ${res.status}`);
  return res.json() as Promise<Session>;
}

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

export async function deleteSession(sessionId: string): Promise<boolean> {
  const res = await fetch(`${API_BASE}/api/v1/sessions/${sessionId}`, {
    method: "DELETE",
    headers: DEV_HEADERS,
  });
  return res.ok;
}

export async function deleteAllSessions(): Promise<number> {
  const res = await fetch(`${API_BASE}/api/v1/admin/sessions`, {
    method: "DELETE",
    headers: DEV_HEADERS,
  });
  if (!res.ok) throw new Error(`deleteAllSessions: ${res.status}`);
  const data = await res.json() as { deleted: number };
  return data.deleted;
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

function invalidSseEvent(): SseEvent {
  return {
    type: "error",
    code: "invalid_sse_event",
    message: "Invalid SSE event received.",
    recoverable: true,
    timestamp: new Date().toISOString(),
  };
}

export async function fetchSessionEvents(sessionId: string): Promise<SseEvent[]> {
  try {
    const res = await fetch(
      `${API_BASE}/api/v1/sessions/${sessionId}/events`,
      { headers: DEV_HEADERS },
    );
    if (!res.ok) return [];
    const rows: Array<{ event_type: string; payload: unknown; created_at: string }> =
      await res.json();
    const events: SseEvent[] = [];
    for (const row of rows) {
      const result = SseEventSchema.safeParse(row.payload);
      if (result.success) events.push(result.data);
    }
    return events;
  } catch {
    return [];
  }
}

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

export async function updateSessionTitle(sessionId: string, title: string): Promise<void> {
  const truncated = title.slice(0, 60).trim();
  if (!truncated) return;
  const res = await fetch(`${API_BASE}/api/v1/sessions/${sessionId}/title`, {
    method: "PATCH",
    headers: DEV_HEADERS,
    body: JSON.stringify({ title: truncated }),
  });
  if (!res.ok) throw new Error(`updateSessionTitle: ${res.status}`);
}

// streamSession eagerly opens the HTTP connection (by awaiting the fetch) before
// returning the async generator. This ensures the stream reader is registered
// before any events are emitted — safe to call before postMessage.
// The backend's GET /stream blocks until a message is posted, so this ordering
// is correct: open stream → post message → iterate events.
export async function streamSession(
  sessionId: string,
  signal?: AbortSignal,
): Promise<AsyncGenerator<SseEvent>> {
  const res = await fetch(`${API_BASE}/api/v1/sessions/${sessionId}/stream`, {
    headers: DEV_HEADERS,
    signal,
  });
  if (!res.ok || !res.body) {
    return (async function* empty(): AsyncGenerator<SseEvent> {})();
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  async function* generate(): AsyncGenerator<SseEvent> {
    try {
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const blocks = buffer.split("\n\n");
        buffer = blocks.pop() ?? "";

        for (const block of blocks) {
          if (!block.trim()) continue;
          // Collect all data: lines from this block and join them
          const dataLines = block
            .split("\n")
            .filter((line) => line.startsWith("data: "))
            .map((line) => line.slice(6));
          if (dataLines.length === 0) continue;
          const data = dataLines.join("");
          try {
            const parsed: unknown = JSON.parse(data);
            const event = SseEventSchema.safeParse(parsed);
            yield event.success ? event.data : invalidSseEvent();
          } catch {
            // skip malformed blocks
          }
        }
      }
    } finally {
      reader.cancel();
    }
  }

  return generate();
}

export async function fetchSessionUsage(sessionId: string): Promise<SessionUsage> {
  try {
    const res = await fetch(`${API_BASE}/api/v1/sessions/${sessionId}/usage`, {
      headers: DEV_HEADERS,
    });
    if (!res.ok) return { inputTokens: 0, outputTokens: 0, costUsd: 0 };
    const data = await res.json() as { input_tokens: number; output_tokens: number; total_cost_usd: number };
    return {
      inputTokens: data.input_tokens,
      outputTokens: data.output_tokens,
      costUsd: data.total_cost_usd,
    };
  } catch {
    return { inputTokens: 0, outputTokens: 0, costUsd: 0 };
  }
}
