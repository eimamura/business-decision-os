"use client";

import type { ChatMessage } from "@/types/chat";
import JobApprovalCard from "@/components/JobApprovalCard";
import BubbleShell from "./BubbleShell";

interface JobApprovalBubbleProps {
  message: ChatMessage;
}

export default function JobApprovalBubble({ message }: JobApprovalBubbleProps): React.JSX.Element {
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
      />
    </BubbleShell>
  );
}
