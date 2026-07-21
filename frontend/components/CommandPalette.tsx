"use client";

import { useEffect, useRef, useState } from "react";
import { Search, Plus, Moon, Sun, Monitor, PanelRight, GraduationCap, X } from "lucide-react";
import { toast } from "sonner";
import { useTheme } from "next-themes";

export default function CommandPalette({
  onClose,
  onNewChat,
  onToggleTheme,
}: {
  onClose: () => void;
  onNewChat: () => void;
  onToggleTheme: () => void;
}) {
  const [query, setQuery] = useState("");
  const { setTheme, theme } = useTheme();
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const COMMANDS = [
    {
      id: "new_chat",
      label: "Start New Chat",
      category: "Navigation",
      Icon: Plus,
      action: () => {
        onNewChat();
        onClose();
      },
      shortcut: "⌘N",
    },
    {
      id: "dark_theme",
      label: "Switch to Dark Theme",
      category: "Settings",
      Icon: Moon,
      action: () => {
        setTheme("dark");
        onClose();
        toast.success("Switched to dark theme");
      },
    },
    {
      id: "light_theme",
      label: "Switch to Light Theme",
      category: "Settings",
      Icon: Sun,
      action: () => {
        setTheme("light");
        onClose();
        toast.success("Switched to light theme");
      },
    },
    {
      id: "open_dashboard",
      label: "Open Training Dashboard",
      category: "Development",
      Icon: GraduationCap,
      action: () => {
        toast("Navigating to Training Dashboard");
        onClose();
      },
    },
  ];

  const filtered = COMMANDS.filter((cmd) =>
    cmd.label.toLowerCase().includes(query.toLowerCase())
  );

  return (
    <div className="modal-overlay" onClick={onClose} style={{ display: "flex", alignItems: "flex-start", paddingTop: "10vh" }}>
      <div className="command-palette" onClick={(e) => e.stopPropagation()}>
        <div style={{ display: "flex", alignItems: "center", borderBottom: "1px solid var(--border)" }}>
          <Search size={18} style={{ marginLeft: "16px", color: "var(--text-muted)" }} />
          <input
            ref={inputRef}
            className="command-input"
            placeholder="Type a command or search..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            style={{ border: "none", width: "100%" }}
            onKeyDown={(e) => {
              if (e.key === "Escape") onClose();
            }}
          />
          <button className="icon-btn sm" onClick={onClose} style={{ marginRight: "12px" }}>
            <X size={16} />
          </button>
        </div>

        <div className="command-list">
          {filtered.length === 0 ? (
            <div style={{ padding: "16px", color: "var(--text-muted)", fontSize: "14px", textAlign: "center" }}>
              No commands found
            </div>
          ) : (
            filtered.map((cmd) => (
              <div
                key={cmd.id}
                className="command-item"
                onClick={cmd.action}
              >
                <cmd.Icon size={16} />
                <span>{cmd.label}</span>
                {cmd.shortcut && <kbd className="command-kbd">{cmd.shortcut}</kbd>}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
