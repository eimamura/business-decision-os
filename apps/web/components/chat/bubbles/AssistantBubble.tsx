"use client";

import { useState, useCallback } from "react";
import { CopyIcon, CheckIcon } from "lucide-react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeSanitize from "rehype-sanitize";
import type { ChatMessage } from "@/types/chat";
import AnalysisCard, { isAnalysisCard } from "@/components/analysis/AnalysisCard";
import FeedbackBar from "@/components/FeedbackBar";
import BubbleShell from "./BubbleShell";
import DynamicSyntaxHighlighter from "./DynamicSyntaxHighlighter";

const markdownComponents: Components = {
  p: ({ children }) => <p className="mb-3 last:mb-0">{children}</p>,
  a: ({ children, href }) => (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="text-indigo-400 underline underline-offset-2 hover:text-indigo-300"
    >
      {children}
    </a>
  ),
  ul: ({ children }) => (
    <ul className="mb-3 ml-5 list-disc space-y-1 last:mb-0">{children}</ul>
  ),
  ol: ({ children }) => (
    <ol className="mb-3 ml-5 list-decimal space-y-1 last:mb-0">{children}</ol>
  ),
  li: ({ children }) => <li className="pl-1">{children}</li>,
  blockquote: ({ children }) => (
    <blockquote className="mb-3 border-l-2 border-white/20 pl-3 text-white/65 last:mb-0">
      {children}
    </blockquote>
  ),
  code: ({ children, className, node }) => {
    const language = /language-(\w+)/.exec(className ?? "")?.[1];
    const code = String(children).replace(/\n$/, "");
    const spansMultipleLines =
      node?.position?.start.line !== node?.position?.end.line;

    if (language || code.includes("\n") || spansMultipleLines) {
      return (
        <DynamicSyntaxHighlighter language={language ?? "text"}>
          {code}
        </DynamicSyntaxHighlighter>
      );
    }

    return (
      <code className="font-mono bg-white/8 px-1.5 py-0.5 rounded text-xs text-indigo-300">
        {children}
      </code>
    );
  },
  pre: ({ children }) => <div className="overflow-x-auto">{children}</div>,
  table: ({ children }) => (
    <div className="mb-3 overflow-x-auto last:mb-0">
      <table className="min-w-full border-collapse text-left text-xs">
        {children}
      </table>
    </div>
  ),
  th: ({ children }) => (
    <th className="border border-white/10 bg-white/5 px-2 py-1 font-semibold text-white/70">
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="border border-white/10 px-2 py-1 align-top text-white/70">
      {children}
    </td>
  ),
};

function AssistantMarkdown({ content }: { content: string }): React.JSX.Element {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      rehypePlugins={[rehypeSanitize]}
      components={markdownComponents}
    >
      {content}
    </ReactMarkdown>
  );
}

interface AssistantBubbleProps {
  message: ChatMessage;
  sessionId?: string;
  onFeedback?: (messageId: string, feedback: 1 | -1) => void;
}

export default function AssistantBubble({
  message,
  onFeedback,
}: AssistantBubbleProps): React.JSX.Element {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(async (): Promise<void> => {
    await navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [message.content]);

  const copyAction =
    !message.isStreaming && !!message.content && !message.isError ? (
      <button
        type="button"
        onClick={handleCopy}
        aria-label={copied ? "copied" : "copy response"}
        title={copied ? "Copied!" : "Copy"}
        className="text-white/30 hover:text-white/65 transition-colors"
      >
        {copied ? (
          <CheckIcon className="h-3.5 w-3.5" />
        ) : (
          <CopyIcon className="h-3.5 w-3.5" />
        )}
      </button>
    ) : undefined;

  const avatar = (
    <span className="text-[10px] text-white font-bold tracking-tight">AI</span>
  );

  if (!message.isError && isAnalysisCard(message.content)) {
    return (
      <div className="flex flex-col items-start">
        <BubbleShell side="left" avatar={avatar} timestamp={message.created_at} actions={copyAction}>
          <AnalysisCard message={message} />
        </BubbleShell>
        {!message.isStreaming && message.messageId && onFeedback && (
          <FeedbackBar
            messageId={message.messageId}
            feedback={message.feedback}
            onFeedback={onFeedback}
          />
        )}
      </div>
    );
  }

  return (
    <div className="flex flex-col items-start">
      <BubbleShell
        side="left"
        avatar={avatar}
        timestamp={message.created_at}
        actions={copyAction}
      >
        <div
          className={`rounded-2xl px-4 py-2.5 text-sm bg-[#1a1a2a] rounded-tl-sm ${
            message.isError ? "text-red-400" : "text-white/80"
          }`}
        >
          {message.content ? (
            <div className="min-w-0 max-w-full overflow-hidden leading-relaxed">
              <AssistantMarkdown content={message.content} />
            </div>
          ) : message.isStreaming ? (
            <div className="flex gap-1.5 items-center py-0.5">
              <span
                className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce"
                style={{ animationDelay: "0ms" }}
              />
              <span
                className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce"
                style={{ animationDelay: "150ms" }}
              />
              <span
                className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce"
                style={{ animationDelay: "300ms" }}
              />
            </div>
          ) : null}
        </div>
      </BubbleShell>
      {!message.isStreaming && message.messageId && onFeedback && (
        <FeedbackBar
          messageId={message.messageId}
          feedback={message.feedback}
          onFeedback={onFeedback}
        />
      )}
    </div>
  );
}
