"use client";

import type { ChatMessage } from "@/types/chat";
import JobStatusCard from "@/components/JobStatusCard";
import BubbleShell from "./BubbleShell";

interface JobStatusBubbleProps {
  message: ChatMessage;
  onJobComplete?: () => void;
}

export default function JobStatusBubble({
  message,
  onJobComplete,
}: JobStatusBubbleProps): React.JSX.Element {
  return (
    <BubbleShell
      side="left"
      avatar={<span className="text-[10px] text-indigo-400">J</span>}
      avatarBorder="border-indigo-900/40"
    >
      <JobStatusCard
        jobId={message.jobId ?? ""}
        jobType={message.jobType ?? "unknown"}
        initialStatus={message.jobStatus ?? "queued"}
        onJobComplete={onJobComplete}
      />
    </BubbleShell>
  );
}
