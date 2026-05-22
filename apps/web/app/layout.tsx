import "./globals.css";
import { Inter } from "next/font/google";
import { ReactNode } from "react";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata = {
  title: "Business Decision OS",
  description: "Supply chain decision intelligence",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${inter.variable} font-sans min-h-screen bg-[#070B14] text-white antialiased`}>
        {children}
      </body>
    </html>
  );
}
