"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeSanitize from "rehype-sanitize";
import type { ChatMessage } from "@/types/chat";

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
  onFeedback?: (messageId: string, feedback: 1 | -1) => void;
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
    <blockquote className="mb-3 border-l-2 border-white/20 pl-3 text-white/50 last:mb-0">
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
    <td className="border border-white/10 px-2 py-1 align-top text-white/55">
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

export default function MessageBubble({ message, onFeedback }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const [justClicked, setJustClicked] = useState<1 | -1 | null>(null);

  function handleFeedback(value: 1 | -1) {
    if (!message.messageId) return;
    setJustClicked(value);
    onFeedback?.(message.messageId, value);
  }

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      {!isUser && (
        <div className="w-7 h-7 rounded-full bg-[#0c0c14] flex items-center justify-center mr-3 mt-1 shrink-0">
          <span className="text-[10px] text-white font-bold tracking-tight">AI</span>
        </div>
      )}

      <div className={`max-w-[78%] flex flex-col ${isUser ? "items-end" : "items-start"}`}>
        <div
          className={`rounded-2xl px-4 py-2.5 text-sm ${
            isUser
              ? "bg-indigo-600 text-white rounded-tr-sm"
              : `bg-[#1a1a2a] rounded-tl-sm ${
                  message.isError ? "text-red-400" : "text-white/80"
                }`
          }`}
        >
          {message.content ? (
            isUser ? (
              <p className="leading-relaxed whitespace-pre-wrap">{message.content}</p>
            ) : (
              <div className="min-w-0 max-w-full overflow-hidden leading-relaxed">
                <AssistantMarkdown content={message.content} />
              </div>
            )
          ) : message.isStreaming ? (
            <span className="inline-block w-2 h-4 bg-indigo-400 animate-pulse" />
          ) : null}
        </div>

        {message.created_at && (
          <p className={`text-xs mt-1 ${isUser ? "text-indigo-300" : "text-white/25"}`}>
            {new Date(message.created_at).toLocaleTimeString()}
          </p>
        )}
      </div>

      {isUser && (
        <div className="w-7 h-7 rounded-full bg-indigo-100 flex items-center justify-center ml-3 mt-1 shrink-0">
          <span className="text-xs text-indigo-600 font-medium">U</span>
        </div>
      )}

      {!isUser && !message.isStreaming && message.messageId && onFeedback && (
        <div className="flex gap-2 mt-1 ml-2">
          <button
            onClick={() => {
              handleFeedback(1);
              setTimeout(() => setJustClicked(null), 600);
            }}
            className={`text-base leading-none transition-all active:scale-125 ${
              justClicked === 1 ? "scale-125" : ""
            } ${
              message.feedback === 1
                ? "text-emerald-500"
                : "text-gray-400 hover:text-emerald-500"
            }`}
            aria-label="Good answer"
          >
            👍
          </button>
          <button
            onClick={() => {
              handleFeedback(-1);
              setTimeout(() => setJustClicked(null), 600);
            }}
            className={`text-base leading-none transition-all active:scale-125 ${
              justClicked === -1 ? "scale-125" : ""
            } ${
              message.feedback === -1
                ? "text-rose-500"
                : "text-gray-400 hover:text-rose-500"
            }`}
            aria-label="Bad answer"
          >
            👎
          </button>
        </div>
      )}
    </div>
  );
}
