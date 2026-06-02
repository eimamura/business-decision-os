import "./globals.css";
import { Inter } from "next/font/google";
import { ReactNode } from "react";
import MockModeBanner from "@/components/MockModeBanner";
import ThemeToggle from "@/components/ThemeToggle";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata = {
  title: "Business Decision OS",
  description: "Supply chain decision intelligence",
};

/**
 * Inline script that runs synchronously before first paint.
 * Reads localStorage.theme or falls back to prefers-color-scheme to
 * apply (or not apply) the `dark` class to <html> without FOUC.
 */
const themeInitScript = `
(function () {
  try {
    var stored = localStorage.getItem('theme');
    var prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    if (stored === 'dark' || (!stored && prefersDark)) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  } catch (_) {}
})();
`.trim();

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      {/* eslint-disable-next-line @next/next/no-sync-scripts */}
      <head>
        {/* biome-ignore lint/security/noDangerouslySetInnerHtml: intentional inline script to avoid FOUC on theme init */}
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body
        className={`${inter.variable} font-sans min-h-screen bg-background text-foreground antialiased`}
      >
        <MockModeBanner />
        <div className="relative">
          <div className="fixed top-3 right-3 z-50">
            <ThemeToggle />
          </div>
          {children}
        </div>
      </body>
    </html>
  );
}
