import { apiFetch } from "@/lib/api";
import type { Session } from "@/types/chat";

export async function getSessions(): Promise<Session[]> {
  const data = await apiFetch<Session[] | { items?: Session[] }>("/api/v1/sessions");
  if (Array.isArray(data)) return data;
  return (data as { items?: Session[] }).items ?? [];
}

export async function createSession(goal: string): Promise<Session> {
  return apiFetch<Session>("/api/v1/sessions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ goal }),
  });
}

export async function deleteAllSessions(): Promise<void> {
  await apiFetch("/api/v1/sessions", { method: "DELETE" });
}
