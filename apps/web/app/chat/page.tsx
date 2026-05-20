"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface Session {
  session_id: string;
  status: string;
  goal?: string;
  created_at: string;
}

export default function ChatListPage() {
  const router = useRouter();
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    fetch(`${API_BASE}/api/v1/sessions`, {
      headers: { "X-Dev-User": "dev-user" },
    })
      .then((r) => r.json())
      .then((data) => setSessions(Array.isArray(data) ? data : data.items ?? []))
      .catch(() => setSessions([]))
      .finally(() => setLoading(false));
  }, []);

  async function createSession() {
    setCreating(true);
    try {
      const res = await fetch(`${API_BASE}/api/v1/sessions`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Dev-User": "dev-user",
        },
        body: JSON.stringify({ goal: "New decision session" }),
      });
      const data = await res.json();
      router.push(`/chat/${data.session_id}`);
    } catch {
      setCreating(false);
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
        <h1 className="text-lg font-semibold text-gray-900">Business Decision OS</h1>
        <nav className="flex gap-4 text-sm text-gray-600">
          <Link href="/approvals" className="hover:text-gray-900">Approvals</Link>
          <Link href="/audit" className="hover:text-gray-900">Audit</Link>
          <Link href="/kpi" className="hover:text-gray-900">KPI</Link>
          <Link href="/settings" className="hover:text-gray-900">Settings</Link>
        </nav>
      </header>
      <main className="max-w-3xl mx-auto px-6 py-10">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-semibold text-gray-900">Decision Sessions</h2>
          <button
            onClick={createSession}
            disabled={creating}
            className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
          >
            {creating ? "Creating..." : "New Session"}
          </button>
        </div>
        {loading ? (
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-16 bg-gray-200 rounded-lg animate-pulse" />
            ))}
          </div>
        ) : sessions.length === 0 ? (
          <div className="text-center py-16 text-gray-500">
            <p className="text-lg mb-2">No sessions yet</p>
            <p className="text-sm">Create a new session to start a decision analysis.</p>
          </div>
        ) : (
          <ul className="space-y-3">
            {sessions.map((s) => (
              <li key={s.session_id}>
                <Link
                  href={`/chat/${s.session_id}`}
                  className="block bg-white border border-gray-200 rounded-lg px-5 py-4 hover:border-blue-400 hover:shadow-sm transition-all"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-gray-900 truncate max-w-sm">
                      {s.goal ?? "Decision Session"}
                    </span>
                    <span
                      className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                        s.status === "active"
                          ? "bg-green-100 text-green-700"
                          : s.status === "awaiting_approval"
                          ? "bg-yellow-100 text-yellow-700"
                          : s.status === "completed"
                          ? "bg-blue-100 text-blue-700"
                          : "bg-gray-100 text-gray-600"
                      }`}
                    >
                      {s.status}
                    </span>
                  </div>
                  <p className="text-xs text-gray-400 mt-1">
                    {new Date(s.created_at).toLocaleString()}
                  </p>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </main>
    </div>
  );
}
