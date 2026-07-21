"use client";

import { PanelLeft, Sparkles, SquarePen } from "lucide-react";
import ThemeToggle from "./ThemeToggle";

/** Slim top bar for the chat pane. When the sidebar is collapsed it also exposes
 *  buttons to reopen it and to start a new chat. */
export default function Header({
  title,
  sidebarOpen,
  onOpenSidebar,
  onNewChat,
}: {
  title?: string;
  sidebarOpen: boolean;
  onOpenSidebar: () => void;
  onNewChat: () => void;
}) {
  return (
    <header className="topbar">
      <div className="topbar-left">
        {!sidebarOpen && (
          <>
            <button className="icon-btn" title="Open sidebar" onClick={onOpenSidebar}>
              <PanelLeft size={18} />
            </button>
            <button className="icon-btn" title="New chat" onClick={onNewChat}>
              <SquarePen size={18} />
            </button>
          </>
        )}
        <div className="topbar-title">
          <Sparkles size={16} className="topbar-spark" />
          <span>{title || "New chat"}</span>
        </div>
      </div>
      <div className="topbar-actions">
        <ThemeToggle />
      </div>
    </header>
  );
}
