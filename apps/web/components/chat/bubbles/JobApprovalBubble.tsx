"use client";

import type { ChatMessage } from "@/types/chat";
import JobApprovalCard from "@/components/JobApprovalCard";
import BubbleShell from "./BubbleShell";

interface JobApprovalBubbleProps {
  message: ChatMessage;
  /** Fires when the user approves the job so the chat can render a status card. */
  onJobApproved?: (jobId: string, jobType: string) => void;
}

export default function JobApprovalBubble({
  message,
  onJobApproved,
}: JobApprovalBubbleProps): React.JSX.Element {
  function handleDecision(decision: "approved" | "rejected"): void {
    if (decision === "approved" && message.jobId && message.jobType) {
      onJobApproved?.(message.jobId, message.jobType);
    }
  }

  return (
    <BubbleShell
      side="left"
      avatar={<span className="text-[10px] text-indigo-400">J</span>}
      avatarBorder="border-indigo-900/40"
    >
      <JobApprovalCard
        approvalId={message.approvalId ?? ""}
        jobId={message.jobId ?? null}
        jobType={message.jobType ?? "unknown"}
        description={message.jobDescription ?? ""}
        params={message.jobParams ?? {}}
        onDecision={handleDecision}
      />
    </BubbleShell>
  );
}
