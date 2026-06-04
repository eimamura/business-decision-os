"use client";

import dynamic from "next/dynamic";

export interface SyntaxHighlighterProps {
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

export default DynamicSyntaxHighlighter;
