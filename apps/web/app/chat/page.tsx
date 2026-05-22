"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { fetchSessions, createSession } from "@/lib/api";

export default function ChatListPage(): React.JSX.Element {
  const router = useRouter();
  const [error, setError] = useState(false);
  const started = useRef(false);

  function start() {
    setError(false);
    fetchSessions()
      .then((sessions) => {
        if (sessions.length > 0) {
          router.replace(`/chat/${sessions[0].session_id}`);
        } else {
          return createSession("New decision session")
            .then((data) => router.replace(`/chat/${data.session_id}`));
        }
      })
      .catch(() => setError(true));
  }

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    start();
  }, []);

  if (error) {
    return (
      <div className="flex h-screen bg-[#0c0c14] items-center justify-center flex-col gap-3">
        <p className="text-sm text-white/50">Failed to start session</p>
        <button
          onClick={start}
          className="text-xs px-3 py-1.5 rounded-md bg-indigo-600 text-white hover:bg-indigo-500"
        >
          Try again
        </button>
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-[#0c0c14] items-center justify-center">
      <p className="text-sm text-white/30">Starting session…</p>
    </div>
  );
}
