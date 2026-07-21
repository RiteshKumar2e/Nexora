import type { Metadata } from "next";
import "katex/dist/katex.min.css";
import "highlight.js/styles/github.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "Nexora — AI Assistant",
  description:
    "A clean, fast AI assistant with a light, focused interface.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" data-theme="light">
      <body>{children}</body>
    </html>
  );
}
