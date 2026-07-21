"use client";

import { Sparkles } from "lucide-react";
import ThemeToggle from "./ThemeToggle";

/** Slim top bar for the chat pane: title on the left, theme toggle on the right. */
export default function Header({ title }: { title?: string }) {
  return (
    <header className="topbar">
      <div className="topbar-title">
        <Sparkles size={16} className="topbar-spark" />
        <span>{title || "New chat"}</span>
      </div>
      <div className="topbar-actions">
        <ThemeToggle />
      </div>
    </header>
  );
}
