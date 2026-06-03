"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeSanitize from "rehype-sanitize";
import { ClipboardIcon, CheckIcon } from "lucide-react";
import type { ChatMessage } from "@/types/chat";
import AnalysisCard, { isAnalysisCard } from "./analysis/AnalysisCard";
import FeedbackBar from "./FeedbackBar";
import JobApprovalCard from "./JobApprovalCard";
import { AskUserInput } from "./AskUserInput";

interface SyntaxHighlighterProps {
  language: string;
  children: string;
}

const DynamicSyntaxHighlighter = dynamic<SyntaxHighlighterProps>(
  () =>
    import("react-syntax-highlighter").then((mod) => {
      const { Prism } = mod;
      const { vscDarkPlus } = require("react-syntax-highlighter/dist/esm/styles/prism");

      function Wrapped({ language, children }: SyntaxHighlighterProps) {
        return (
          <Prism
            language={language}
            style={vscDarkPlus}
            customStyle={{
              margin: "0 0 0.75rem",
              padding: "12px 14px",
              background: "#1e1e1e",
              borderRadius: "0.5rem",
              fontSize: "0.8rem",
              lineHeight: "1.5",
            }}
            wrapLongLines
          >
            {children}
          </Prism>
        );
      }

      return Wrapped;
    }),
  { ssr: false }
);

interface MessageBubbleProps {
  message: ChatMessage;
  sessionId?: string;
  onFeedback?: (messageId: string, feedback: 1 | -1) => void;
  onAskUserAnswered?: (reply: string) => void;
}

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

function AssistantMarkdown({ content }: { content: string }) {
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

function SqlQueryBubble({ message }: { message: ChatMessage }) {
  const label = message.toolName === "nl_query" ? "NL → SQL" : "SQL Query";
  const [copyState, setCopyState] = useState<"idle" | "copied">("idle");

  function handleCopy(): void {
    if (!message.sql) return;
    navigator.clipboard.writeText(message.sql).then(() => {
      setCopyState("copied");
      setTimeout(() => setCopyState("idle"), 2000);
    });
  }

  return (
    <div className="flex justify-start">
      <div className="w-7 h-7 rounded-full bg-[#0c0c14] flex items-center justify-center mr-3 mt-1 shrink-0 border border-emerald-900/40">
        <span className="text-[10px] text-emerald-400">⚙</span>
      </div>
      <div className="max-w-[78%]">
        <div className="rounded-xl bg-[#0b1a15] border border-emerald-900/40 px-3 pt-2 pb-1">
          <div className="flex items-center gap-1.5 mb-1.5">
            <span className="text-xs font-mono font-bold text-emerald-500 uppercase tracking-wider">
              {label}
            </span>
            {message.sql && (
              <button
                type="button"
                onClick={handleCopy}
                className="ml-auto p-1 rounded text-emerald-500/60 hover:text-emerald-400 hover:bg-emerald-900/30 transition-colors"
                aria-label={copyState === "copied" ? "Copied!" : "Copy SQL"}
                title={copyState === "copied" ? "Copied!" : "Copy SQL"}
              >
                {copyState === "copied" ? (
                  <CheckIcon className="h-4 w-4" />
                ) : (
                  <ClipboardIcon className="h-4 w-4" />
                )}
              </button>
            )}
          </div>
          {message.sql && (
            <DynamicSyntaxHighlighter language="sql">
              {message.sql}
            </DynamicSyntaxHighlighter>
          )}
        </div>
        {message.created_at && (
          <p className="text-xs mt-1 text-white/45">
            {new Date(message.created_at).toLocaleTimeString()}
          </p>
        )}
      </div>
    </div>
  );
}

export default function MessageBubble({ message, sessionId, onFeedback, onAskUserAnswered }: MessageBubbleProps): React.JSX.Element {
  if (message.role === "ask_user") {
    const onAnswered = (result: unknown): void => {
      const reply = (result as { reply?: string } | undefined)?.reply;
      if (reply && onAskUserAnswered) {
        onAskUserAnswered(reply);
      }
    };
    return (
      <div className="flex justify-start">
        <div className="w-7 h-7 rounded-full bg-[#0c0c14] flex items-center justify-center mr-3 mt-1 shrink-0 border border-indigo-900/40">
          <span className="text-[10px] text-indigo-400">?</span>
        </div>
        <div className="max-w-[78%] w-full">
          <AskUserInput
            sessionId={sessionId ?? ""}
            askUserId={message.askUserId ?? ""}
            question={message.askUserQuestion ?? ""}
            suggestions={message.askUserSuggestions ?? []}
            onAnswered={onAnswered}
          />
        </div>
      </div>
    );
  }

  if (message.role === "job_approval") {
    return (
      <div className="flex justify-start">
        <div className="w-7 h-7 rounded-full bg-[#0c0c14] flex items-center justify-center mr-3 mt-1 shrink-0 border border-indigo-900/40">
          <span className="text-[10px] text-indigo-400">J</span>
        </div>
        <JobApprovalCard
          approvalId={message.approvalId ?? ""}
          jobId={message.jobId ?? null}
          jobType={message.jobType ?? "unknown"}
          description={message.jobDescription ?? ""}
          params={message.jobParams ?? {}}
        />
      </div>
    );
  }

  if (message.role === "job_files") {
    const files = message.jobFiles ?? [];
    return (
      <div className="flex justify-start">
        <div className="w-7 h-7 rounded-full bg-[#0c0c14] flex items-center justify-center mr-3 mt-1 shrink-0 border border-emerald-900/40">
          <span className="text-[10px] text-emerald-400">F</span>
        </div>
        <div className="max-w-[78%] rounded-xl bg-[#0b1a15] border border-emerald-900/40 px-3 py-2 text-xs">
          <p className="font-semibold text-emerald-400 mb-1.5">Job output files</p>
          <ul className="space-y-1">
            {files.map((f) => (
              <li key={f.download_url}>
                <a
                  href={f.download_url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-indigo-400 underline underline-offset-2 hover:text-indigo-300 break-all"
                >
                  {f.file_name}
                </a>
              </li>
            ))}
          </ul>
        </div>
      </div>
    );
  }

  if (message.role === "tool") {
    return <SqlQueryBubble message={message} />;
  }

  if (message.role === "assistant" && !message.isError && isAnalysisCard(message.content)) {
    return (
      <div className="flex flex-col items-start">
        <div className="flex justify-start w-full">
          <div className="w-7 h-7 rounded-full bg-[#0c0c14] flex items-center justify-center mr-3 mt-1 shrink-0">
            <span className="text-[10px] text-white font-bold tracking-tight">AI</span>
          </div>
          <AnalysisCard message={message} />
        </div>
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

  const isUser = message.role === "user";

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[78%] flex flex-col items-end">
          <div className="rounded-2xl px-4 py-2.5 text-sm bg-indigo-600 text-white rounded-tr-sm">
            <p className="leading-relaxed whitespace-pre-wrap">{message.content}</p>
          </div>
          {message.created_at && (
            <p className="text-xs mt-1 text-indigo-300">
              {new Date(message.created_at).toLocaleTimeString()}
            </p>
          )}
        </div>
        <div className="w-7 h-7 rounded-full bg-indigo-100 flex items-center justify-center ml-3 mt-1 shrink-0">
          <span className="text-xs text-indigo-600 font-medium">U</span>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-start">
      <div className="flex justify-start w-full">
        <div className="w-7 h-7 rounded-full bg-[#0c0c14] flex items-center justify-center mr-3 mt-1 shrink-0">
          <span className="text-[10px] text-white font-bold tracking-tight">AI</span>
        </div>
        <div className="max-w-[78%] flex flex-col items-start">
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
                <span className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                <span className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                <span className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
              </div>
            ) : null}
          </div>
          {message.created_at && (
            <p className="text-xs mt-1 text-white/45">
              {new Date(message.created_at).toLocaleTimeString()}
            </p>
          )}
        </div>
      </div>
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
