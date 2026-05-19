import "./globals.css";
import { ReactNode } from "react";

export const metadata = {
  title: "Business Decision OS",
  description: "Supply chain decision intelligence",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-gray-50 text-gray-900">{children}</body>
    </html>
  );
}
